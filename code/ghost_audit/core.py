"""Deterministic evidence boundary. No reference-answer access or model SDK."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
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

    def __init__(self, dataset):
        self.dataset = Path(dataset).resolve()
        self.manifest = {r["file_id"]: r for r in rows(self.dataset / "evidence_files.csv")}
        self.identities = rows(self.dataset / "user_identities.csv")
        self.history = rows(self.dataset / "user_audit_log.csv")
        self.activity = rows(self.dataset / "system_activity.csv")
        self.rules = rows(self.dataset / "deletion_rules.csv")
        self.contents, self.postings, self.opaque = {}, {}, []
        self.digest = hashlib.sha256()
        for fid, meta in sorted(self.manifest.items()):
            path = (self.dataset / meta["file_path"]).resolve()
            if not path.is_relative_to(self.dataset / "evidence"):
                raise Rejected("Manifest path escapes evidence directory")
            blob = path.read_bytes()
            self.digest.update(fid.encode() + blob)
            if path.suffix not in {".sql", ".json", ".log", ".txt"}:
                self.opaque.append(fid)
                continue
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


def matches(row, identity):
    direct_refs = [row[k] for k in ("user_id", "customer_reference") if row.get(k)]
    if direct_refs:
        return all(value == identity["user_id"] for value in direct_refs)
    for alias in identity["aliases"]:
        field, value = alias["field"], alias["value"]
        if field in {"email", "email_hash"} and row.get(field, "").casefold() == value.casefold():
            return True
        if field == "phone" and row.get(field):
            if re.sub(r"\D", "", row[field]) == re.sub(r"\D", "", value):
                return True
    return False


def profile_snapshot(text, meta, identity, cutoff, deadline, known_resources=()):
    """Read complete profile tables in an isolated in-memory SQLite database.

    This first adapter accepts only explicit point-in-time profile snapshots.
    Other SQL schemas are unresolved, not guessed from resource-ID prefixes.
    """
    if not eligible(meta["captured_at"], cutoff):
        raise Rejected("Evidence captured after audit_at")
    marker = re.search(r"-- Captured at: (\S+)", text)
    if not marker or marker[1] != meta["captured_at"]:
        raise Rejected("Unsupported or inconsistent SQL snapshot timestamp")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    blocked = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}
    db.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action in blocked else sqlite3.SQLITE_OK)
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        db.executescript(text)
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if not tables or any(not re.fullmatch(r"customer_profiles_(primary|regional_replica|reporting_replica|failover_replica)", t) for t in tables):
            raise Rejected("SQL contains unsupported table schemas")
        observations = []
        table_rows = {}
        for table in tables:
            table_rows[table] = [dict(r) for r in db.execute('SELECT * FROM "' + table + '"')]
            for row in table_rows[table]:
                if not eligible(row["updated_at"], meta["captured_at"]):
                    raise Rejected("Row update is later than snapshot capture")
                if matches(row, identity):
                    observations.append({"system_id": "account_service", "resource_id": row["resource_id"],
                                         "category": "USER_PROFILE", "state": "PRESENT", "table": table,
                                         "observed_at": meta["captured_at"], "evidence_id": meta["file_id"],
                                         "record": row})
        # Absence is scoped to a complete table and an already-grounded resource ID.
        known = {o["resource_id"] for o in observations} | set(known_resources)
        for resource in sorted(known):
            for table, records in table_rows.items():
                if not any(r["resource_id"] == resource for r in records):
                    observations.append({"system_id": "account_service", "resource_id": resource,
                                         "category": "USER_PROFILE", "state": "ABSENT", "table": table,
                                         "observed_at": meta["captured_at"], "evidence_id": meta["file_id"],
                                         "record": None})
        return observations
    except sqlite3.Error as exc:
        raise Rejected(f"SQL adapter rejected snapshot: {exc}") from exc
    finally:
        db.close()


class Investigation:
    def __init__(self, index, request, limits=Limits()):
        self.index, self.request, self.limits = index, request, limits
        self.started = time.monotonic()
        self.tool_calls = self.proposal_attempts = 0
        self.identity = None
        self.observations = []
        self.claims = []
        self.trace = []
        self.result = None
        self.halt_reason = None
        self.ledger = {"identifiers_searched": [], "eligible_sources_inspected": [],
                       "discovered_resources": [], "discovered_processes": [],
                       "unresolved_contradictions": [], "remaining_gaps": ["Identity and evidence not searched"],
                       "deferred_sources": [], "candidates": [], "activity_inspected": False}

    def call(self, name, args):
        if self.result:
            raise Rejected("Investigation already has an accepted decision")
        if self.halt_reason:
            raise Rejected(self.halt_reason)
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
                value = self.identity
            elif name == "search_evidence" and not args:
                if not self.identity:
                    raise Rejected("Resolve identity first")
                identifiers = self.identity["aliases"] + [
                    {"field": "resource_id", "value": rid, "source": "validated SQL observation"}
                    for rid in self.ledger["discovered_resources"]]
                ids = self.index.search(identifiers, self.request["audit_at"])
                self.ledger["identifiers_searched"] = identifiers
                self.ledger["candidates"] = ids
                persistent_gaps = [gap for gap in self.ledger["remaining_gaps"]
                    if gap.startswith(("Activity links", "Process-state"))]
                self.ledger["remaining_gaps"] = persistent_gaps + ["Uninspected candidate: " + fid for fid in ids
                    if fid not in self.ledger["eligible_sources_inspected"]]
                self.ledger["deferred_sources"] = [fid for fid in self.index.opaque
                    if eligible(self.index.manifest[fid]["captured_at"], self.request["audit_at"])]
                value = {"candidates": [self.index.manifest[fid] for fid in ids],
                         "deferred_sources": self.ledger["deferred_sources"]}
            elif name == "inspect_profile_snapshot" and set(args) == {"evidence_id"}:
                fid = args["evidence_id"]
                if fid not in self.ledger["candidates"]:
                    raise Rejected("Evidence must be an eligible identity-linked search candidate")
                observations = profile_snapshot(self.index.contents[fid], self.index.manifest[fid], self.identity,
                                         self.request["audit_at"], started + self.limits.tool_seconds,
                                         self.ledger["discovered_resources"])
                if not observations:
                    raise Rejected("No grounded profile observations")
                value = {"observations": observations, "policy_rules": self.index.rules}
                self.observations = [o for o in self.observations if o["evidence_id"] != fid] + observations
                self.ledger["eligible_sources_inspected"] = sorted(set(self.ledger["eligible_sources_inspected"] + [fid]))
                self.ledger["remaining_gaps"] = [x for x in self.ledger["remaining_gaps"] if x != "Uninspected candidate: " + fid]
                self.ledger["discovered_resources"] = sorted({o["resource_id"] for o in self.observations})
                searched_resources = {a["value"] for a in self.ledger["identifiers_searched"] if a["field"] == "resource_id"}
                if not set(self.ledger["discovered_resources"]).issubset(searched_resources):
                    self.ledger["remaining_gaps"].append("Search newly discovered resource IDs")
            elif name == "inspect_activity" and not args:
                known = set(self.ledger["discovered_resources"])
                if not known:
                    raise Rejected("Discover grounded resources first")
                identity_tokens = {a["value"].casefold() for a in self.identity["aliases"]
                                   if a["field"] != "phone"}
                self.claims = [r for r in self.index.activity
                               if (r["resource_id"] in known or identity_tokens & tokens(r["details"]))
                               and eligible(r["event_time"], self.request["audit_at"])]
                for claim in self.claims:
                    if claim["resource_id"] not in known:
                        gap = "Activity links an unsupported resource: " + claim["resource_id"]
                        if gap not in self.ledger["remaining_gaps"]:
                            self.ledger["remaining_gaps"].append(gap)
                    if any(word in claim["event_type"] for word in ("FLOW", "BACKUP", "RESTORE", "IMPORT")):
                        self.ledger["discovered_processes"].append(claim["resource_id"])
                        self.ledger["remaining_gaps"].append("Process-state adapter required: " + claim["activity_id"])
                self.ledger["activity_inspected"] = True
                value = {"claims_not_state_proof": self.claims,
                         "note": "A past SYNC_RECORD success does not establish an active data flow."}
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
            else:
                raise Rejected("Unknown tool or invalid arguments")
            if time.monotonic() - started > self.limits.tool_seconds:
                self.result = None
                self.halt_reason = "Tool timeout exhausted"
                raise Rejected(self.halt_reason)
            self.trace.append({"tool": name, "arguments": args, "result": value, "accepted": True})
            return value
        except Rejected as exc:
            self.trace.append({"tool": name, "arguments": args, "error": str(exc), "accepted": False})
            raise

    def validate_proposal(self, proposal):
        expected = {"authorized", "request_quote", "deletion_status", "resources"}
        if set(proposal) != expected or type(proposal["authorized"]) is not bool:
            raise Rejected("Invalid proposal fields")
        resource_fields = {"system_id", "resource_id", "state", "required_action", "evidence_id"}
        if not isinstance(proposal["resources"], list) or any(
            not isinstance(r, dict) or set(r) != resource_fields or any(not isinstance(v, str) for v in r.values())
            for r in proposal["resources"]
        ):
            raise Rejected("Invalid resource proposal schema")
        quote = proposal["request_quote"]
        if not isinstance(quote, str) or not quote.strip() or quote not in self.request["request_text"]:
            raise Rejected("Authorization must cite an exact request-text span")
        if not proposal["authorized"]:
            if proposal["deletion_status"] != "NOT_APPLICABLE" or proposal["resources"]:
                raise Rejected("Non-deletion intent requires NOT_APPLICABLE and no resources")
            return {"case_id": self.request["case_id"], "deletion_status": "NOT_APPLICABLE", "steps_json": []}
        if not self.identity or not self.ledger["identifiers_searched"] or not self.ledger["activity_inspected"]:
            raise Rejected("Identity search and activity inspection are required")
        if self.ledger["remaining_gaps"] or self.ledger["unresolved_contradictions"]:
            raise Rejected("Unresolved investigation gaps")
        compiled = self.required_resources()
        if not compiled:
            raise Rejected("No evidence-backed resources; cannot infer completion")
        if sorted(proposal["resources"], key=lambda r: (r.get("system_id", ""), r.get("resource_id", ""))) != compiled:
            raise Rejected("Resource proposal disagrees with observed state, citation, or supplied policy")
        status = "INCOMPLETE" if any(r["state"] == "PRESENT" for r in compiled) else "COMPLETE"
        if proposal["deletion_status"] != status:
            raise Rejected(f"Proposed status conflicts with evidence: required {status}")
        if status == "COMPLETE" and self.ledger["deferred_sources"]:
            raise Rejected("Uninspected evidence formats prevent a COMPLETE determination")
        return compile_output(self.request["case_id"], status, compiled)

    def required_resources(self):
        rules = [r for r in self.index.rules if r["data_category"] == "USER_PROFILE"
                 and r["condition"] == "Always"]
        if len(rules) != 1 or rules[0]["required_action"] != "DELETE":
            raise Rejected("Unsupported or conflicting policy for profile adapter")
        # Latest per replica, never latest across replicas. Ties with different states block.
        latest = {}
        for obs in self.observations:
            key = obs["system_id"], obs["resource_id"], obs["table"]
            old = latest.get(key)
            if old and timestamp(old["observed_at"]) == timestamp(obs["observed_at"]) and old["state"] != obs["state"]:
                self.ledger["unresolved_contradictions"] = ["Conflicting same-time observations: " + repr(key)]
                raise Rejected("Contradictory same-scope observations")
            if not old or (timestamp(obs["observed_at"]), obs["evidence_id"]) > (timestamp(old["observed_at"]), old["evidence_id"]):
                latest[key] = obs
        resources = {}
        for (system, resource, _), obs in latest.items():
            resources.setdefault((system, resource), []).append(obs)
        result = []
        for (system, resource), observations in sorted(resources.items()):
            present = [o for o in observations if o["state"] == "PRESENT"]
            if not present and len({o["evidence_id"] for o in observations}) != 1:
                raise Rejected("Absence requires a single full-scope snapshot in this adapter")
            proof = sorted(present or observations, key=lambda o: (o["evidence_id"], o["table"]))[0]
            result.append({"system_id": system, "resource_id": resource, "state": "PRESENT" if present else "ABSENT",
                           "required_action": rules[0]["required_action"], "evidence_id": proof["evidence_id"]})
        return result

    def report(self):
        return {"request": self.request, "identity": self.identity, "limits": asdict(self.limits),
                "tool_calls": self.tool_calls, "proposal_attempts": self.proposal_attempts,
                "internal_state": "SUPPORTED_SCOPE_RESOLVED" if self.result else "UNRESOLVED",
                "halt_reason": self.halt_reason,
                "global_coverage": "UNRESOLVED_DEFERRED_FORMATS" if self.ledger["deferred_sources"] else "SUPPORTED_ADAPTERS_ONLY",
                "scope": "SQL customer profile primary/replica snapshots; other adapters deferred",
                "indexed_evidence_sha256": self.index.digest.hexdigest(),
                "ledger": self.ledger, "observations": self.observations, "activity_claims": self.claims,
                "trace": self.trace, "output": self.result}


def compile_output(case_id, status, resources):
    steps = []
    def add(phase, resource, operation, state, evidence):
        steps.append({"step_no": 0, "phase": phase, "system_id": resource["system_id"],
                      "resource_id": resource["resource_id"], "operation": operation,
                      "state": state, "evidence_id": evidence})
    for r in resources:
        if r["state"] == "PRESENT":
            add("FINDING", r, "REPORT_REMAINING_RECORD", "PRESENT", r["evidence_id"])
            add("REMEDIATION", r, "DELETE_RECORD", "ABSENT", "")
        add("VERIFICATION", r, "VERIFY_RECORD_ABSENT", "ABSENT", r["evidence_id"] if status == "COMPLETE" else "")
    phase_order = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
    # This adapter has one operation per phase. New policy adapters must extend operation rank.
    steps.sort(key=lambda s: (phase_order[s["phase"]], s["system_id"], s["resource_id"]))
    for number, step in enumerate(steps, 1):
        step["step_no"] = number
    return {"case_id": case_id, "deletion_status": status, "steps_json": steps}


def write_csv(path, result):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerow({**result, "steps_json": json.dumps(result["steps_json"], separators=(",", ":"))})
