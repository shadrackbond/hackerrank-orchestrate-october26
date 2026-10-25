"""Deterministic evidence boundary. No reference-answer access or model SDK."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


class Rejected(ValueError):
    pass


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise Rejected("Timestamp must include a timezone")
    return parsed


def eligible(value, cutoff):
    return timestamp(value) <= timestamp(cutoff)


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def tokens(text):
    # Exact tokens, including full emails and IDs; never substring/name matching.
    found = set(re.findall(r"[\w.+%\-]+@[\w.\-]+|[\w]+", text.casefold()))
    found.update("phone:" + re.sub(r"\D", "", p) for p in re.findall(r"\+\d[\d ()-]{6,}\d", text))
    return found


def explicit_deletion_signal(text):
    """High-confidence authorization veto for contradictory non-deletion proposals.

    The model still interprets intent in general; this rejects only requests that
    explicitly ask to delete/erase/close or verify the already deleted state.
    """
    value = text.casefold()
    if re.search(r"\b(?:do not|don't|never|no quiero)\s+(?:delete|erase|remove|eliminar)", value):
        return False
    if re.search(r"\b(?:delet|eras|purge|elimin|supprim|effac)\w*\b|削除", value):
        return True
    if re.search(r"\b(?:confirm|verify|check|audit)\b", value) and re.search(
        r"\b(?:profile|account|personal data|remaining records)\b.{0,90}"
        r"\b(?:gone|removed|cannot identify|no longer identify)\b", value):
        return True
    return False


@dataclass(frozen=True)
class Limits:
    tool_calls: int = 10
    proposal_attempts: int = 3
    tool_seconds: float = 10
    case_seconds: float = 180


class EvidenceIndex:
    """One immutable text index shared by all cases in this process.

    Only manifest files are read. Public answers are deliberately not inputs.
    Nontext sources remain explicit coverage gaps.
    """

    def __init__(self, dataset, visual_cache=None, image_model=None):
        self.dataset = Path(dataset).resolve()
        self.manifest = {r["file_id"]: r for r in rows(self.dataset / "evidence_files.csv")}
        self.identities = rows(self.dataset / "user_identities.csv")
        self.history = rows(self.dataset / "user_audit_log.csv")
        self.activity = rows(self.dataset / "system_activity.csv")
        self.rules = rows(self.dataset / "deletion_rules.csv")
        self.contents, self.postings, self.opaque = {}, {}, []
        self.visual_observations = {}
        self.visual_cache = Path(visual_cache).resolve() if visual_cache else None
        self.image_model = image_model
        self.digest = hashlib.sha256()
        for fid, meta in sorted(self.manifest.items()):
            path = (self.dataset / meta["file_path"]).resolve()
            if not path.is_relative_to(self.dataset / "evidence"):
                raise Rejected("Manifest path escapes evidence directory")
            blob = path.read_bytes()
            self.digest.update(fid.encode() + blob)
            if path.suffix in {".pdf", ".png"}:
                if not self.visual_cache:
                    self.opaque.append(fid)
                    continue
                from .extraction import VERSION, source_cache_path
                cache_path = source_cache_path(self.visual_cache, blob, path.suffix.lower(), image_model)
                if not cache_path.exists():
                    self.opaque.append(fid)
                    continue
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("version") != VERSION or cached.get("content_sha256") != hashlib.sha256(blob).hexdigest():
                    self.opaque.append(fid)
                    continue
                observations = [{"text": segment["text"], "file_id": fid,
                                 "observation_at": meta["captured_at"],
                                 "source_location": meta["file_path"] + "#" + segment["location"],
                                 "extractor": cached["extractor"]}
                                for segment in cached["segments"]]
                self.visual_observations[fid] = observations
                text = "\n".join(item["text"] for item in observations)
            else:
                text = blob.decode("utf-8")
            self.contents[fid] = text
            for token in tokens(text):
                self.postings.setdefault(token, set()).add(fid)
    def identity(self, email, cutoff):
        candidates = []
        for current in self.identities:
            uid = current["user_id"]
            events = [e for e in self.history if e["user_id"] == uid
                      and eligible(e["event_time"], cutoff)]
            # A later current snapshot must not leak future identifiers backward.
            aliases = []
            if eligible(current["updated_at"], cutoff):
                aliases += [{"field": k, "value": current[k], "source": "user_identities.csv",
                             "available_at": current["updated_at"]}
                            for k in ("user_id", "email", "phone", "email_hash") if current.get(k)]
            for event in events:
                if event["field_name"] in {"email", "phone", "email_hash"}:
                    aliases += [{"field": event["field_name"], "value": event[k],
                                 "source": event["audit_id"], "available_at": event["event_time"]}
                                for k in ("old_value", "new_value") if event[k]]
            if any(a["field"] == "email" and a["value"].casefold() == email.casefold()
                   for a in aliases):
                if not any(a["field"] == "user_id" for a in aliases):
                    aliases.append({"field": "user_id", "value": uid,
                                    "source": events[0]["audit_id"],
                                    "available_at": events[0]["event_time"]})
                candidates.append({"user_id": uid, "aliases": aliases})
        if len(candidates) != 1:
            raise Rejected(f"Identity unresolved: {len(candidates)} candidate subjects")
        return candidates[0]

    def search(self, identifiers, cutoff):
        found = set()
        for alias in identifiers:
            value = alias["value"].casefold()
            if alias["field"] == "phone":
                value = "phone:" + re.sub(r"\D", "", value)
            found |= self.postings.get(value, set())
        return sorted(fid for fid in found if eligible(self.manifest[fid]["captured_at"], cutoff))



class Investigation:
    """Bounded case tools over the single general index and policy engine."""
    def __init__(self, index, request, limits=Limits()):
        from .public_index import PublicIndex
        self.index = PublicIndex.from_index(index)
        self.request, self.limits = request, limits
        self.started = time.monotonic()
        self.identity = self.result = self.halt_reason = None
        self.tool_calls = self.proposal_attempts = 0
        self.trace, self.observations, self.claims = [], [], []
        self.inspected = set()
        self.semantic_reviews, self.semantic_observations = [], []
        self.activity_inspected = False
        self.assessment = None
        self.ledger = {"identifiers_searched": [], "candidates": [], "eligible_sources_inspected": [],
            "remaining_gaps": ["Identity and evidence not searched"], "unresolved_contradictions": [],
            "deferred_sources": [], "discovered_resources": [], "discovered_processes": [],
            "activity_inspected": False}

    def _refresh(self):
        if self.identity:
            from .engine import assess
            self.assessment = assess(self.index, self.request, self.identity, self.inspected, self.activity_inspected,
                                     self.semantic_observations)
            self.ledger = self.assessment["ledger"]
            self.observations = self.assessment["observations"]
            self.claims = self.assessment["activity_claims"]

    def _search_index(self):
        self._refresh()

    def _inspect_activity(self):
        if not self.identity: raise Rejected("Resolve identity first")
        self.activity_inspected = True
        self._refresh()
        return {"claims_not_state_proof": self.claims, "remaining_gaps": self.ledger["remaining_gaps"]}

    def call(self, name, args):
        if self.result: raise Rejected("Investigation already has an accepted decision")
        if self.halt_reason: raise Rejected(self.halt_reason)
        if time.monotonic() - self.started >= self.limits.case_seconds:
            self.halt_reason = "Case timeout exhausted"
            raise Rejected(self.halt_reason)
        if self.tool_calls >= self.limits.tool_calls:
            self.halt_reason = "Tool-call budget exhausted"
            raise Rejected(self.halt_reason)
        self.tool_calls += 1
        started = time.monotonic()
        try:
            if name == "resolve_identity" and not args:
                self.identity = self.index.identity(self.request["email"], self.request["audit_at"])
                self._search_index()
                value = {"identity": self.identity, "candidates": [self.index.manifest[fid]
                    for fid in self.ledger["candidates"]], "deferred_sources": self.ledger["deferred_sources"]}
            elif name == "search_evidence" and not args:
                if not self.identity: raise Rejected("Resolve identity first")
                self._search_index()
                value = {"candidates": [self.index.manifest[fid] for fid in self.ledger["candidates"]],
                         "remaining_gaps": self.ledger["remaining_gaps"]}
            elif name in {"inspect_evidence", "inspect_profile_snapshot", "inspect_visual_evidence"} and set(args) == {"evidence_id"}:
                fid = args["evidence_id"]
                if not self.identity or fid not in self.ledger["candidates"]:
                    raise Rejected("Evidence must be an eligible identity-linked search candidate")
                errors = [g for g in self.index.adapter_gaps if g.startswith("Adapter rejected " + fid + ":")]
                if errors: raise Rejected(errors[0])
                self.inspected.add(fid)
                self._refresh()
                # Existing inspection names are compatibility aliases to this same adapter.
                value = {"observations": [o for o in self.observations if o["evidence_id"] == fid],
                    "resource_links": [e for e in self.ledger.get("association_search", {}).get("links", [])
                                       if any(p["evidence_id"] == fid for p in e["proof"])],
                    "contextual_evidence": [c for c in self.ledger.get("contextual_evidence", []) if c["evidence_id"] == fid],
                    "policy_rules": self.index.rules, "resources": self.required_resources(),
                    "linked_candidates": [self.index.manifest[item] for item in self.ledger["candidates"]],
                    "remaining_gaps": self.ledger["remaining_gaps"]}
                if not value["observations"] and fid in self.index.visual_observations:
                    value["transcription_not_policy_proof"] = self.index.visual_observations[fid]
            elif name == "inspect_activity" and not args:
                value = self._inspect_activity()
            elif name == "read_semantic_evidence" and set(args) == {"evidence_id"}:
                from .semantic import evidence_units
                fid = args["evidence_id"]
                value = {"evidence_id": fid, "capture_at": self.index.manifest.get(fid, {}).get("captured_at"),
                         "units": evidence_units(self, fid), "policy_rules": self.index.rules}
            elif name == "propose_semantic_assessment":
                if self.proposal_attempts >= self.limits.proposal_attempts:
                    self.halt_reason = "Proposal-attempt budget exhausted"
                    raise Rejected(self.halt_reason)
                self.proposal_attempts += 1
                from .semantic import validate_assessment
                review = validate_assessment(self, args)
                self.semantic_reviews.append(review)
                if review["observation"]:
                    observation = review["observation"]
                    self.semantic_observations = [o for o in self.semantic_observations if
                        (o["system_id"], o["resource_id"], o["evidence_id"]) !=
                        (observation["system_id"], observation["resource_id"], observation["evidence_id"])] + [observation]
                    self._refresh()
                value = {"assessment": review, "resources": self.required_resources(),
                         "remaining_gaps": self.ledger["remaining_gaps"]}
            elif name == "propose_decision":
                if self.proposal_attempts >= self.limits.proposal_attempts:
                    self.halt_reason = "Proposal-attempt budget exhausted"
                    raise Rejected(self.halt_reason)
                self.proposal_attempts += 1
                value = self.validate_proposal(args)
                self.result = value
                if not args["authorized"]:
                    self.ledger["remaining_gaps"] = []
                    self.ledger["inspection_not_authorized"] = True
            else: raise Rejected("Unknown tool or invalid arguments")
            if time.monotonic() - started > self.limits.tool_seconds:
                self.result = None
                self.halt_reason = "Tool timeout exhausted"
                raise Rejected(self.halt_reason)
            self.trace.append({"tool": name, "arguments": args, "result": value, "accepted": True})
            return value
        except Rejected as exc:
            self.trace.append({"tool": name, "arguments": args, "error": str(exc), "accepted": False})
            raise

    def required_resources(self):
        if not self.assessment: return []
        return sorted([{"system_id": r["obs"]["system_id"], "resource_id": r["obs"]["resource_id"],
            "state": r["obs"]["state"], "required_action": r["action"],
            "evidence_id": r["obs"]["evidence_id"]} for r in self.assessment["resources"]],
            key=lambda r: (r["system_id"], r["resource_id"]))

    def decision_proposal(self):
        """Deterministic diagnostic helper; never a claim of model judgment."""
        if not self.assessment: raise Rejected("Identity and evidence not inspected")
        return {"authorized": True, "request_quote": self.request["request_text"],
                "deletion_status": self.assessment["classification_status"], "resources": self.required_resources()}

    def validate_proposal(self, proposal):
        if set(proposal) != {"authorized", "request_quote", "deletion_status", "resources"} or type(proposal["authorized"]) is not bool:
            raise Rejected("Invalid proposal fields")
        fields = {"system_id", "resource_id", "state", "required_action", "evidence_id"}
        if not isinstance(proposal["resources"], list) or any(not isinstance(r, dict) or set(r) != fields
            or any(not isinstance(v, str) for v in r.values()) for r in proposal["resources"]):
            raise Rejected("Invalid resource proposal schema")
        quote = proposal["request_quote"]
        if not isinstance(quote, str) or not quote.strip() or quote not in self.request["request_text"]:
            raise Rejected("Authorization must cite an exact request-text span")
        if not proposal["authorized"]:
            if explicit_deletion_signal(self.request["request_text"]):
                raise Rejected("Request explicitly authorizes a deletion audit; non-deletion proposal conflicts with request")
            if proposal["deletion_status"] != "NOT_APPLICABLE" or proposal["resources"]:
                raise Rejected("Non-deletion intent requires NOT_APPLICABLE and no resources")
            return {"case_id": self.request["case_id"], "deletion_status": "NOT_APPLICABLE", "steps_json": []}
        if not self.identity or not self.activity_inspected:
            raise Rejected("Identity search and activity inspection are required")
        if self.ledger["remaining_gaps"] or self.ledger["unresolved_contradictions"]:
            raise Rejected("Unresolved investigation gaps: " + "; ".join(self.ledger["remaining_gaps"]))
        if sorted(proposal["resources"], key=lambda r: (r["system_id"], r["resource_id"])) != self.required_resources():
            raise Rejected("Resource proposal disagrees with observed state, citation, or supplied policy")
        required = self.assessment["classification_status"]
        if proposal["deletion_status"] != required:
            raise Rejected("Proposed status conflicts with evidence: required " + str(required))
        if required == "COMPLETE" and (self.ledger["deferred_sources"] or not self.ledger["coverage"]["complete_scope_certified"]):
            raise Rejected("Unsupported evidence scope prevents a COMPLETE determination")
        output = self.assessment["output"]
        if output is None: raise Rejected("No accepted evidence-backed decision")
        return output

    def report(self):
        return {"case_id": self.request["case_id"], "request": self.request, "identity": self.identity,
            "limits": asdict(self.limits), "tool_calls": self.tool_calls, "proposal_attempts": self.proposal_attempts,
            "internal_state": "SUPPORTED_SCOPE_RESOLVED" if self.result else "UNRESOLVED",
            "halt_reason": self.halt_reason, "ledger": self.ledger, "observations": self.observations,
            "facts": self.assessment["facts"] if self.assessment else [],
            "classification_status": self.assessment["classification_status"] if self.assessment else None,
            "activity_claims": self.claims, "trace": self.trace, "output": self.result,
            "semantic_reviews": self.semantic_reviews,
            "runtime_seconds": time.monotonic() - self.started,
            "indexed_evidence_sha256": self.index.digest.hexdigest(),
            "coverage_summary": {"plan_completeness_certified": bool(self.assessment and self.assessment["output"])}}

def write_csv(path, result):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerow({**result, "steps_json": json.dumps(result["steps_json"], separators=(",", ":"))})
