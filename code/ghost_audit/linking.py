"""Grounded historical resource associations. No reference answers or verdicts."""
from collections import defaultdict
import json
import re

from .core import eligible, tokens


LINK_TYPES = ["IDENTITY_SNAPSHOT", "HISTORICAL_IDENTIFIER", "IDENTITY_CHANGE", "EXACT_IDENTIFIER",
              "CORRELATED_TRACE", "CATALOG_IDENTITY_LINK", "EXPLICIT_RESOURCE_RELATIONSHIP",
              "SAME_RESOURCE_OBSERVATION"]
RELATION_FIELDS = {
    "source_resource_id": ("source_system_id", "source_system", True, "SOURCE_OF"),
    "parent_resource_id": ("parent_system_id", "parent_system", True, "PARENT_OF"),
    "account_resource_id": ("account_system_id", "account_system", True, "ACCOUNT_REFERENCE"),
    "target_resource_id": ("target_system_id", "target_system", False, "TARGET_REFERENCE"),
    "destination_resource_id": ("destination_system_id", "destination_system", False, "DESTINATION_REFERENCE"),
    "related_resource_id": ("related_system_id", "related_system", False, "RELATED_RESOURCE"),
}
TEXT_FIELDS = {"message_text", "message_excerpt", "body"}


def resource(system, rid):
    return {"kind": "RESOURCE", "system_id": system, "resource_id": rid}


def identifier(alias):
    value = alias["value"]
    if alias["field"] == "phone": value = re.sub(r"\D", "", value)
    elif alias["field"] != "user_id": value = value.casefold()
    return {"kind": "IDENTIFIER", "field": alias["field"], "value": value}


def _matches(value, alias, text=False):
    if not isinstance(value, str): return False
    if text:
        if alias["field"] == "user_id":
            return bool(re.search(r"(?<!\w)" + re.escape(alias["value"]) + r"(?!\w)", value))
        key = "phone:" + re.sub(r"\D", "", alias["value"]) if alias["field"] == "phone" else alias["value"].casefold()
        return key in tokens(value)
    return identifier({"field": alias["field"], "value": value}) == identifier(alias)


def matches(record, aliases, prefix=""):
    from .public_index import DIRECT_KEYS, IDENTIFIER_KEYS
    found = []
    for key, value in record.items():
        path = prefix + key
        if isinstance(value, dict) and key in {"document", "profile", "subject_selector"}:
            found.extend(matches(value, aliases, path + "/"))
        elif key in DIRECT_KEYS | IDENTIFIER_KEYS | TEXT_FIELDS | {"subject_selector"} or any(
                word in key for word in ("email", "phone", "hash")):
            for alias in aliases:
                if _matches(value, alias, key in TEXT_FIELDS): found.append((path, alias))
    return found


def link_subject(index, identity, cutoff):
    from .public_index import identity_conflict
    aliases = [a for a in identity["aliases"] if eligible(a.get("available_at", cutoff), cutoff)]
    subject = {"kind": "SUBJECT", "user_id": identity["user_id"]}
    edges, edge_keys, rejected = [], set(), []
    def add(start, end, kind, proof, **details):
        edge = {"from": start, "to": end, "direction": "FROM_TO", "link_type": kind,
                "proof": proof, **details}
        key = json.dumps(edge, sort_keys=True)
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append(edge)

    def provenance(row):
        return {"evidence_id": row["evidence_id"], "source_location": row["source_location"],
                "captured_at": row["capture_at"], "observed_at": row["observed_at"]}

    for alias in aliases:
        add(subject, identifier(alias), "IDENTITY_SNAPSHOT" if alias.get("source") == "user_identities.csv" else "HISTORICAL_IDENTIFIER",
            [{"evidence_id": alias.get("source", "resolved_identity"), "source_location": alias.get("source", "resolved_identity"),
              "captured_at": alias.get("available_at", cutoff), "observed_at": alias.get("available_at", cutoff)}])
    for event in index.history:
        if event["user_id"] != identity["user_id"] or not eligible(event["event_time"], cutoff): continue
        if event["field_name"] not in {"email", "phone", "email_hash"}: continue
        if event["old_value"] and event["new_value"]:
            add(identifier({"field": event["field_name"], "value": event["old_value"]}),
                identifier({"field": event["field_name"], "value": event["new_value"]}), "IDENTITY_CHANGE",
                [{"evidence_id": event["audit_id"], "source_location": "user_audit_log.csv#audit_id=" + event["audit_id"],
                  "captured_at": event["event_time"], "observed_at": event["event_time"]}])

    observations = [o for o in index.observations if eligible(o["capture_at"], cutoff) and eligible(o["observed_at"], cutoff)]
    records = {(o["evidence_id"], o["source_location"], o["system_id"], o["resource_id"]): o
               for o in getattr(index, "link_records", []) if eligible(o["capture_at"], cutoff) and eligible(o["observed_at"], cutoff)}
    records.update({(o["evidence_id"], o["source_location"], o["system_id"], o["resource_id"]): o for o in observations})
    records = list(records.values())
    by_key, by_id = defaultdict(list), defaultdict(set)
    for row in records:
        if row["resource_id"]:
            key = row["system_id"], row["resource_id"]
            by_key[key].append(row)
            by_id[row["resource_id"]].add(key)
    known = {}
    for row in records:
        if not row["resource_id"] or identity_conflict(row["record"], identity): continue
        found = matches(row["record"], aliases)
        if not found: continue
        key = row["system_id"], row["resource_id"]
        known[key] = row.get("category")
        for field, alias in found:
            trace = [p for p in row.get("trace_proof", []) if matches(p["fields"], [alias])]
            add(identifier(alias), resource(*key), "CORRELATED_TRACE" if trace else "EXACT_IDENTIFIER",
                ([{k: p[k] for k in ("evidence_id", "source_location", "captured_at", "observed_at")} for p in trace]
                 + [provenance(row)]) if trace else [provenance(row)], matched_field=field)

    catalog_claims = []
    all_subjects = {r["user_id"] for r in index.identities}
    for event in index.activity:
        if event["event_type"] != "LINK_RESOURCE_IDENTITY" or not eligible(event["event_time"], cutoff): continue
        if not any(_matches(event["details"], a, True) for a in aliases): continue
        # This event explicitly asserts attribution; arbitrary event co-occurrence is not a link.
        other = {uid for uid in all_subjects if uid != identity["user_id"] and uid.casefold() in tokens(event["details"])}
        if other: continue
        key = event["target_system"], event["resource_id"]
        if not key[1]: continue
        catalog_claims.append(event)
        categories = {r.get("category") for r in by_key[key] if r.get("category")}
        known[key] = next(iter(categories)) if len(categories) == 1 else None
        add(subject, resource(*key), "CATALOG_IDENTITY_LINK", [{"evidence_id": event["activity_id"],
            "source_location": "system_activity.csv#activity_id=" + event["activity_id"],
            "captured_at": event["event_time"], "observed_at": event["event_time"]}])

    relations = []
    for row in records:
        if not row["resource_id"] or identity_conflict(row["record"], identity): continue
        here = row["system_id"], row["resource_id"]
        declarations = [(field, row["record"][field], row["record"].get(system_field) or row["record"].get(system_alias), reverse, kind)
                        for field, (system_field, system_alias, reverse, kind) in RELATION_FIELDS.items()
                        if isinstance(row["record"].get(field), str) and row["record"][field]]
        for field, rid, system, reverse, kind in declarations:
            targets = {(system, rid)} if system else by_id.get(rid, set())
            target = next(iter(targets)) if len(targets) == 1 else ("", rid)
            source, dest = (target, here) if reverse else (here, target)
            relations.append((source, dest, field, kind, row))
    changed = True
    while changed:
        changed = False
        for source, dest, field, kind, row in relations:
            if source not in known and dest not in known: continue
            target = dest if source in known else source
            conflicting = [o for o in by_key[target] if identity_conflict(o["record"], identity)]
            if conflicting:
                rejected.append({"link_type": kind, "resource": resource(*target), "reason": "Conflicting subject claim",
                                 "proof": [provenance(row)]})
                continue
            add(resource(*source), resource(*dest), "EXPLICIT_RESOURCE_RELATIONSHIP", [provenance(row)],
                relationship_type=kind, declared_field=field,
                traversed_direction="FORWARD" if source in known else "REVERSE")
            if target not in known:
                categories = {o.get("category") for o in by_key[target] if o.get("category")}
                known[target] = next(iter(categories)) if len(categories) == 1 else None
                changed = True
    selected = []
    for obs in observations:
        key = obs["system_id"], obs["resource_id"]
        if not obs["resource_id"] and not identity_conflict(obs["record"], identity) and matches(obs["record"], aliases):
            selected.append(obs)
            continue
        if key in known and not identity_conflict(obs["record"], identity):
            selected.append(obs)
            add(resource(*key), {"kind": "OBSERVATION", "evidence_id": obs["evidence_id"],
                                "source_location": obs["source_location"]}, "SAME_RESOURCE_OBSERVATION", [provenance(obs)])
    search_aliases = aliases + [{"field": "resource_id", "value": rid} for system, rid in known if rid]
    candidates = set(index.search(search_aliases, cutoff)) | {o["evidence_id"] for o in selected}
    eligible_sources = [{"file_id": fid, "captured_at": meta["captured_at"],
                         **index.source_assessments.get(fid, {"status": "UNINSPECTED_SOURCE"})}
                        for fid, meta in sorted(index.manifest.items()) if eligible(meta["captured_at"], cutoff)]
    incomplete = [s for s in eligible_sources if s["status"] not in {"LINK_SEARCH_SUPPORTED"}]
    unassociated = {}
    from .public_index import DIRECT_KEYS, IDENTIFIER_KEYS
    for obs in observations:
        key = obs["system_id"], obs["resource_id"]
        if key in known or any(identity_conflict(row["record"], identity) for row in by_key[key]): continue
        identifier_free = not any(value for field, value in obs["record"].items()
                                  if field in DIRECT_KEYS | IDENTIFIER_KEYS or any(t in field for t in ("email", "phone", "hash")))
        if obs["state"] in {"ANONYMIZED", "ABSENT", "REDACTED"} or identifier_free:
            unassociated[key] = {"resource": resource(*key), "reason": "No grounded historical subject association",
                                "subject_membership": "UNKNOWN", "search_scope_id": "subject_link_search",
                                "state_evidence": provenance(obs)}
    audit = {"search_scope_id": "subject_link_search", "searched_link_types": LINK_TYPES,
             "eligible_sources": eligible_sources, "eligible_activity_rows_searched": sum(eligible(e["event_time"], cutoff) for e in index.activity),
             "eligible_identity_history_rows_searched": sum(e["user_id"] == identity["user_id"] and eligible(e["event_time"], cutoff) for e in index.history),
             "status": "EXHAUSTED_SUPPORTED_SEARCH" if not incomplete else "SUPPORTED_SEARCH_EXHAUSTED_WITH_ADAPTER_GAPS",
             "adapter_gaps": incomplete, "unassociated_resources": list(unassociated.values()), "rejected_links": rejected,
             "contradictions": ["Conflicting historical subject association: " + system + "/" + rid
                                for system, rid in sorted(known)
                                if any(identity_conflict(o["record"], identity) for o in by_key[system, rid]) ]}
    return selected, sorted(candidates), known, edges, audit, catalog_claims
