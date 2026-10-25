"""Bounded public-case runner; answers are not loaded by this module."""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path

from .core import Rejected, eligible, rows, timestamp, explicit_deletion_signal
from .public_index import PublicIndex, linked


DIRECT_FIELDS = ("full_name", "name", "email", "phone", "email_hash", "requester_name",
                 "requester_email", "requester_phone")
ACTION_BY_CATEGORY = {"DATA_FLOW": "DISABLE", "BACKUP_ARCHIVE": "BLOCK"}
VERIFY = {"DELETE": ("VERIFY_RECORD_ABSENT", "ABSENT"),
          "REDACT": ("VERIFY_RECORD_REDACTED", "REDACTED"),
          "ANONYMIZE": ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
          "RETAIN": ("VERIFY_RECORD_PRESENT", "PRESENT"),
          "DISABLE": ("VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
          "BLOCK": ("VERIFY_RESTORE_BLOCKED", "BLOCKED")}
REMEDIATE = {"DELETE": ("DELETE_RECORD", "ABSENT"),
             "REDACT": ("REDACT_RECORD", "REDACTED"),
             "ANONYMIZE": ("ANONYMIZE_RECORD", "ANONYMIZED"),
             "DISABLE": ("DISABLE_DATA_FLOW", "DISABLED"),
             "BLOCK": ("BLOCK_RESTORE", "BLOCKED")}
FINDING = {"DELETE": ("REPORT_REMAINING_RECORD", "PRESENT"),
           "REDACT": ("REPORT_EXPOSED_PII", "PRESENT"),
           "ANONYMIZE": ("REPORT_EXPOSED_PII", "PRESENT"),
           "DISABLE": ("REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
           "BLOCK": ("REPORT_RESTORE_RISK", "ACTIVE")}


def deletion_intent(text):
    """Clear multilingual deletion language. Ambiguity stays unresolved."""
    value = text.casefold()
    if explicit_deletion_signal(text): return True
    if re.search(r"\b(?:do not|don't|never|no quiero)\s+(?:delete|erase|remove|eliminar)", value):
        return False
    if re.search(r"\b(?:access|export|correct|update|marketing|unsubscribe|opt.out)\b", value) and not re.search(
        r"\b(?:delet|eras|remov|clos|purge|elimin|suppress|supprim|effac)\w*\b|削除", value):
        return False
    if re.search(r"\b(?:delet|eras|remov|clos|purge|elimin|suppress|supprim|effac)\w*\b|削除", value):
        return True
    return None


def _scope_kind(obs):
    scope = obs["scope"].split(":", 1)[-1]
    table = re.search(r"#table=([^,]+)", obs["source_location"])
    if table:
        return "sql:" + table[1]
    if scope.startswith("log:"):
        return "readback:" + obs["system_id"]
    if scope.startswith("visual"):
        return "visual:" + obs["system_id"]
    # JSON exports of the same service and category form one observation scope.
    return "export:" + obs["system_id"] + ":" + obs["category"]


def _policy(rule_map, obs, cutoff):
    category = obs["category"]
    if category in ACTION_BY_CATEGORY:
        return ACTION_BY_CATEGORY[category], None
    candidates = rule_map.get(category, [])
    if not candidates:
        return None, "Unsupported policy category: " + category
    if len(candidates) != 1:
        return None, "Multiple applicable policy rules need condition resolution: " + category
    rule = candidates[0]
    condition, action = rule["condition"], rule["required_action"]
    record = obs["record"]
    if condition == "Always": return action, None
    if category == "ANALYTICS_PROFILE" or category == "PRODUCT_TELEMETRY":
        return action, None
    if category == "SUPPORT_MESSAGE":
        return action, None if any(record.get(k) for k in ("message_text", "message_excerpt")) else \
            "Shared-context condition unproved: " + obs["resource_id"]
    if category == "SUPPORT_ATTACHMENT":
        return action, None if record.get("subject_only") is True else \
            "Subject-only attachment condition unproved: " + obs["resource_id"]
    if category == "EMAIL_DELIVERY_LOG":
        return action, None if record.get("email") else "Email-containing condition unproved"
    if category == "SECURITY_AUDIT_LOG":
        until = record.get("retention_until")
        return (action, None) if until and eligible(cutoff, until) else \
            (None, "Retention period unproved: " + obs["resource_id"])
    if category == "LEGAL_HOLD_RECORD":
        until = record.get("retained_until") or record.get("retention_until")
        return (action, None) if until and eligible(cutoff, until) else \
            (None, "Active legal hold unproved: " + obs["resource_id"])
    if category == "BACKUP_ARCHIVE":
        return "BLOCK", None
    if category == "ACCOUNT_TOMBSTONE":
        stable = record.get("user_id") or record.get("subject_reference")
        return (action, None) if isinstance(stable, str) and stable.startswith("user_") else \
            (None, "Tombstone stable reference unproved")
    return None, "Unsupported policy condition: " + condition


def _compliant(action, obs):
    state, record = obs["state"], obs["record"]
    if action == "DELETE": return state == "ABSENT"
    if action == "DISABLE": return state == "DISABLED"
    if action == "BLOCK": return state == "BLOCKED"
    if action == "RETAIN": return state == "PRESENT"
    if action == "ANONYMIZE": return state == "ANONYMIZED"
    if action == "REDACT":
        if state == "REDACTED": return True
        if obs["category"] == "ACCOUNT_TOMBSTONE":
            return not any(record.get(k) for k in DIRECT_FIELDS)
        return False
    return False


def _step(phase, obs, operation, state, evidence_id):
    return {"step_no": 0, "phase": phase, "system_id": obs["system_id"],
            "resource_id": obs["resource_id"], "operation": operation,
            "state": state, "evidence_id": evidence_id}


def _make_output(case_id, resources):
    status = "INCOMPLETE" if any(not r["compliant"] for r in resources) else "COMPLETE"
    steps = []
    violations = [r for r in resources if not r["compliant"]]
    for r in sorted(violations, key=lambda r: (r["obs"]["system_id"], r["obs"]["resource_id"])):
        op, state = FINDING[r["action"]]
        steps.append(_step("FINDING", r["obs"], op, state, r["obs"]["evidence_id"]))
    priority = {"DISABLE": 0, "BLOCK": 1, "DELETE": 2, "REDACT": 3, "ANONYMIZE": 4}
    for r in sorted(violations, key=lambda r: (priority[r["action"]], r["obs"]["system_id"],
                                              r["obs"]["resource_id"])):
        op, state = REMEDIATE[r["action"]]
        steps.append(_step("REMEDIATION", r["obs"], op, state, ""))
    for r in sorted(resources, key=lambda r: (r["obs"]["system_id"], r["obs"]["resource_id"])):
        op, state = VERIFY[r["action"]]
        steps.append(_step("VERIFICATION", r["obs"], op, state,
                           r["obs"]["evidence_id"] if status == "COMPLETE" else ""))
    for number, step in enumerate(steps, 1): step["step_no"] = number
    return {"case_id": case_id, "deletion_status": status, "steps_json": steps}


def investigate(index, request, case_seconds=10):
    started = time.monotonic()
    cutoff = request["audit_at"]
    ledger = {"identifiers_searched": [], "eligible_sources_inspected": [],
              "discovered_resources": [], "discovered_processes": [],
              "unresolved_contradictions": [], "remaining_gaps": [],
              "applicable_policy_conditions": [], "relevant_evidence_scopes": []}
    result = {"case_id": request["case_id"], "internal_state": "UNRESOLVED",
              "output": None, "identity": None, "ledger": ledger, "facts": [],
              "runtime_seconds": None, "model_usage": {"calls": 0, "input_tokens": 0,
                                                        "cached_input_tokens": 0, "output_tokens": 0}}
    try:
        authorized = deletion_intent(request["request_text"])
        if authorized is None:
            ledger["remaining_gaps"].append("Deletion authorization ambiguous; requires model judgment")
            return result
        if not authorized:
            result["internal_state"] = "RESOLVED"
            result["output"] = {"case_id": request["case_id"], "deletion_status": "NOT_APPLICABLE", "steps_json": []}
            return result
        identity = index.identity(request["email"], cutoff)
        result["identity"] = identity
        ledger["identifiers_searched"] = identity["aliases"]
        direct = [o for o in index.observations
                  if eligible(o["capture_at"], cutoff) and eligible(o["observed_at"], cutoff)
                  and linked(o["record"], identity)]
        resource_ids = {o["resource_id"] for o in direct if o["resource_id"]}
        # A source-resource reference is an explicit edge, unlike neighboring
        # rows in the same export or a similar-looking email.
        for observation in direct:
            source_id = observation["record"].get("source_resource_id")
            if source_id: resource_ids.add(source_id)
        # A readback of an absent resource can be linked by a trace's lookup key;
        # propagation is limited to that validated resource ID, never a name prefix.
        related = [o for rid in resource_ids for o in index.by_resource[rid]
                   if eligible(o["capture_at"], cutoff) and eligible(o["observed_at"], cutoff)]
        observations = list({(o["evidence_id"], o["source_location"]): o for o in direct + related}.values())
        ledger["discovered_resources"] = sorted(resource_ids)
        ledger["eligible_sources_inspected"] = sorted({o["evidence_id"] for o in observations})
        ledger["relevant_evidence_scopes"] = sorted({o["scope"] for o in observations})
        candidates = index.search(identity["aliases"], cutoff)
        for fid in candidates:
            if fid not in ledger["eligible_sources_inspected"]:
                if fid in index.visual_observations:
                    ledger["remaining_gaps"].append("Visual resource assessment unresolved: " + fid)
                elif fid in index.opaque:
                    ledger["remaining_gaps"].append("Unextracted source: " + fid)
                else:
                    ledger["remaining_gaps"].append("Identity hit lacks parsed resource observation: " + fid)
        # Use the latest state per resource and independently scoped replica/readback.
        latest = {}
        for obs in observations:
            if not obs["resource_id"]: continue
            key = obs["system_id"], obs["resource_id"], _scope_kind(obs)
            old = latest.get(key)
            if old and obs["observed_at"] == old["observed_at"] and obs["state"] != old["state"]:
                ledger["unresolved_contradictions"].append("Same-time state conflict: " + repr(key))
            if not old or (timestamp(obs["observed_at"]), obs["evidence_id"]) > \
                    (timestamp(old["observed_at"]), old["evidence_id"]): latest[key] = obs
        grouped = defaultdict(list)
        for (system, rid, _), obs in latest.items(): grouped[system, rid].append(obs)
        rule_map = defaultdict(list)
        for rule in index.rules: rule_map[rule["data_category"]].append(rule)
        resources = []
        for key, scoped in sorted(grouped.items()):
            # Presence or an active process in any current scope prevails.
            state_order = {"ACTIVE": 5, "PRESENT": 4, "DISABLED": 3,
                           "BLOCKED": 3, "REDACTED": 2, "ANONYMIZED": 2, "ABSENT": 1}
            obs = max(scoped, key=lambda o: (state_order.get(o["state"], 0),
                                             timestamp(o["observed_at"]), o["evidence_id"]))
            action, gap = _policy(rule_map, obs, cutoff)
            if gap: ledger["remaining_gaps"].append(gap)
            if not action: continue
            compliant = _compliant(action, obs)
            resources.append({"obs": obs, "action": action, "compliant": compliant})
            ledger["applicable_policy_conditions"].append({"resource_id": obs["resource_id"],
                "category": obs["category"], "required_action": action,
                "condition": rule_map[obs["category"]][0]["condition"] if rule_map[obs["category"]] else "process-state"})
            result["facts"].append({"system_id": obs["system_id"], "resource_id": obs["resource_id"],
                "category": obs["category"], "state": obs["state"], "action": action,
                "compliant": compliant, "evidence_id": obs["evidence_id"],
                "source_location": obs["source_location"], "observed_at": obs["observed_at"]})
            if action in {"DISABLE", "BLOCK"}: ledger["discovered_processes"].append(obs["resource_id"])
        if not resources: ledger["remaining_gaps"].append("No identity-linked resource state")
        census_systems = {"account_service", "search_service", "analytics_platform",
                          "support_platform", "integration_service", "backup_service",
                          "security_service"}
        scoped_systems = {system for scope, system, collection, at in index.scopes
                          if eligible(at, cutoff) and scope.split(":", 1)[0] in
                          ledger["eligible_sources_inspected"]}
        subject_scope_systems = {r["obs"]["system_id"] for r in resources}
        full_snapshot_sources = {scope.split(":", 1)[0] for scope, system, collection, at in index.scopes
                                 if scope.endswith(":snapshot_scope") and eligible(at, cutoff)
                                 and scope.split(":", 1)[0] in ledger["eligible_sources_inspected"]}
        # Point lookup exports list several services, but do not prove that each
        # service was queried for this subject. COMPLETE needs a subject-linked
        # observation in every required system plus a complete inventory scope.
        ledger["coverage"] = {"resource_count": len(resources),
                              "candidate_sources": len(candidates),
                              "inspected_candidate_sources": len(set(candidates) & set(ledger["eligible_sources_inspected"])),
                              "relevant_scope_systems": sorted(scoped_systems),
                              "subject_observed_systems": sorted(subject_scope_systems),
                              "full_snapshot_sources": sorted(full_snapshot_sources),
                              "applicable_policy_conditions_checked": len(ledger["applicable_policy_conditions"]),
                              "complete_scope_certified": bool(full_snapshot_sources) and
                                census_systems <= scoped_systems and census_systems <= subject_scope_systems and
                                not ledger["remaining_gaps"] and not ledger["unresolved_contradictions"]}
        if resources and all(r["compliant"] for r in resources) and not ledger["coverage"]["complete_scope_certified"]:
            ledger["remaining_gaps"].append("COMPLETE requires a census across relevant evidence scopes")
        if time.monotonic() - started > case_seconds:
            ledger["remaining_gaps"].append("Case time budget exhausted")
        if not ledger["remaining_gaps"] and not ledger["unresolved_contradictions"]:
            result["output"] = _make_output(request["case_id"], resources)
            result["internal_state"] = "RESOLVED"
    except Rejected as exc:
        ledger["remaining_gaps"].append(str(exc))
    finally:
        result["runtime_seconds"] = time.monotonic() - started
    return result


def run_public(dataset, visual_cache, run_dir, case_seconds=10):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    index = PublicIndex(dataset, visual_cache)
    requests = rows(Path(dataset) / "sample_deletion_requests.csv")
    results = [investigate(index, request, case_seconds) for request in requests]
    (run_dir / "investigations.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    (run_dir / "index_summary.json").write_text(json.dumps({"observations": len(index.observations),
        "scopes": len(index.scopes), "adapter_gaps": index.adapter_gaps,
        "evidence_digest": index.digest.hexdigest()}, indent=2) + "\n")
    with (run_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, ["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for result in sorted(results, key=lambda r: r["case_id"]):
            if result["output"]:
                item = result["output"]
                writer.writerow({"case_id": item["case_id"], "deletion_status": item["deletion_status"],
                                 "steps_json": json.dumps(item["steps_json"], separators=(",", ":"))})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[2] / "dataset")
    parser.add_argument("--visual-cache", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--case-seconds", type=float, default=10)
    args = parser.parse_args()
    results = run_public(args.dataset, args.visual_cache, args.run_dir, args.case_seconds)
    print(json.dumps({"attempted": len(results), "resolved": sum(r["output"] is not None for r in results),
                      "unresolved": sum(r["output"] is None for r in results)}))


if __name__ == "__main__": main()
