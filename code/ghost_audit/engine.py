"""Shared deterministic policy, scope, and output rules for tools and diagnostics."""
from collections import defaultdict
import re
from .core import Rejected, eligible, timestamp
from .public_index import case_view, linked

DIRECT_FIELDS = ("full_name", "name", "email", "phone", "email_hash", "requester_name",
                 "requester_email", "requester_phone")
ACTION_BY_CATEGORY = {"DATA_FLOW": "DISABLE"}
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


def retention_proof(obs, cutoff, observations=()):
    """Record-scoped condition proof; observation/capture times are never creation dates."""
    key = obs["system_id"], obs["resource_id"], obs["category"]
    def subjects(o):
        record = o["record"]
        return {record[k] for k in ("user_id", "customer_reference", "subject_reference", "subject_ref", "correlation_key")
                if isinstance(record.get(k), str) and "@" not in record[k]
                and record[k] not in {"null", "None", "NULL"}}
    anchor = subjects(obs)
    sources = [o for o in (obs, *observations)
               if (o["system_id"], o["resource_id"], o["category"]) == key
               and (not anchor or not subjects(o) or anchor == subjects(o))
               and eligible(o.get("capture_at", o.get("observed_at", cutoff)), cutoff)
               and eligible(o.get("observed_at", cutoff), cutoff)]
    fields = ("retention_until", "retained_until", "retention_from", "event_recorded_at", "created_at",
              "hold_active", "legal_hold_active", "hold_started_at", "hold_until", "hold_released_at")
    values = {field: {o["record"][field] for o in sources if o["record"].get(field) is not None}
              for field in fields}
    proof = sorted({(o.get("evidence_id", ""), o.get("source_location", "")) for o in sources
                    if any(o["record"].get(field) is not None for field in fields)})
    result = {"resource_id": obs["resource_id"], "status": "INSUFFICIENT",
              "proof": [{"evidence_id": fid, "source_location": location} for fid, location in proof]}
    dates = values["retention_until"] | values["retained_until"]
    active = values["hold_active"] | values["legal_hold_active"]
    if any(len(v) > 1 for v in values.values()) or len(dates) > 1 or len(active) > 1:
        return {**result, "status": "CONTRADICTORY", "reason": "Conflicting record-scoped retention assertions"}
    def one(field): return next(iter(values[field]), None)
    try:
        # Explicit event/creation times validate chronology but do not supply a duration.
        creation = one("event_recorded_at") or one("created_at")
        if creation and not eligible(creation, cutoff):
            return {**result, "status": "CONTRADICTORY", "reason": "Record creation is later than audit_at"}
        if obs["category"] == "LEGAL_HOLD_RECORD":
            if not active:
                return {**result, "reason": "A retain-until date or ordinary retention reason does not establish an active legal hold"}
            if not active <= {True, False}:
                return {**result, "reason": "Legal hold activity must be supplied explicitly"}
            start, end, released = one("hold_started_at"), one("hold_until"), one("hold_released_at")
            if start and end and not eligible(start, end):
                return {**result, "status": "CONTRADICTORY", "reason": "Legal hold ends before it starts"}
            if active == {False} or released and eligible(released, cutoff) or end and not eligible(cutoff, end):
                return {**result, "status": "EXPIRED", "reason": "Legal hold is inactive or expired; no fallback treatment supplied"}
            if start and not eligible(start, cutoff):
                return {**result, "reason": "Legal hold has not started at audit_at"}
        else:
            if not dates:
                return {**result, "reason": "Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented"}
            end = next(iter(dates))
            start = one("retention_from") or creation
            if start and not eligible(start, end):
                return {**result, "status": "CONTRADICTORY", "reason": "Retention deadline precedes its start"}
            if not eligible(cutoff, end):
                return {**result, "status": "EXPIRED", "reason": "Retention requirement expired; no fallback treatment supplied"}
            if start and not eligible(start, cutoff):
                return {**result, "reason": "Retention requirement has not started at audit_at"}
    except (Rejected, ValueError, TypeError):
        return {**result, "reason": "Retention timestamp is invalid or lacks a timezone"}
    return {**result, "status": "ACTIVE", "reason": "Explicit record-scoped requirement is active at audit_at"}


def _policy(rule_map, obs, cutoff, condition_observations=()):
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
        proof = retention_proof(obs, cutoff, condition_observations)
        return (action, None) if proof["status"] == "ACTIVE" else \
            (None, "Retention period unproved: " + obs["resource_id"] + " — " + proof["reason"])
    if category == "LEGAL_HOLD_RECORD":
        proof = retention_proof(obs, cutoff, condition_observations)
        return (action, None) if proof["status"] == "ACTIVE" else \
            (None, "Active legal hold unproved: " + obs["resource_id"] + " — " + proof["reason"])
    if category == "BACKUP_ARCHIVE":
        return ("BLOCK", None) if action == "RETAIN" and condition == "Restore access can be blocked" else \
            (None, "Unsupported backup retention condition: " + condition)
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
    operations = ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW",
                  "REPORT_RESTORE_RISK", "DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD",
                  "REDACT_RECORD", "ANONYMIZE_RECORD", "VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT",
                  "VERIFY_RECORD_REDACTED", "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED",
                  "VERIFY_RESTORE_BLOCKED"]
    steps.sort(key=lambda s: (operations.index(s["operation"]), s["system_id"], s["resource_id"]))
    for number, step in enumerate(steps, 1): step["step_no"] = number
    return {"case_id": case_id, "deletion_status": status, "steps_json": steps}


def assess(index, request, identity, inspected, activity_inspected):
    """Assess only inspected case-scoped observations. Used by every execution path."""
    cutoff = request["audit_at"]
    all_obs, candidates, known, links = case_view(index, identity, cutoff)
    observations = [o for o in all_obs if o["evidence_id"] in inspected]
    contexts = [c for c in index.contexts if c["evidence_id"] in inspected
                and eligible(c["capture_at"], cutoff) and eligible(c["observed_at"], cutoff)
                and linked(c["record"], identity)]
    gaps = ["Uninspected candidate: " + fid for fid in candidates if fid not in inspected]
    for fid in set(candidates) & set(inspected):
        if not any(o["evidence_id"] == fid for o in observations + contexts):
            gaps.append(("Visual resource assessment unresolved: " if fid in index.visual_observations
                         else "Identity hit lacks parsed resource observation: ") + fid)
    contradictions, latest = [], {}
    for obs in observations:
        if not obs["resource_id"]:
            gaps.append("Resource identity unproved: " + obs["system_id"] + "/" + obs["category"])
            continue
        key = obs["system_id"], obs["resource_id"], _scope_kind(obs)
        old = latest.get(key)
        if old and old["observed_at"] == obs["observed_at"] and old["state"] != obs["state"]:
            contradictions.append("Conflicting same-scope observations: " + repr(key))
        if not old or (timestamp(obs["observed_at"]), obs["evidence_id"]) > \
                (timestamp(old["observed_at"]), old["evidence_id"]): latest[key] = obs
    grouped = defaultdict(list)
    for (system, rid, scope), obs in latest.items(): grouped[system, rid].append(obs)
    rules, resources, facts, conditions, retention_checks = defaultdict(list), [], [], [], []
    for rule in index.rules: rules[rule["data_category"]].append(rule)
    for key, scoped in sorted(grouped.items()):
        state_order = {"UNKNOWN": 6, "ACTIVE": 5, "PRESENT": 4, "DISABLED": 3,
                       "BLOCKED": 3, "REDACTED": 2, "ANONYMIZED": 2, "ABSENT": 1}
        obs = max(scoped, key=lambda o: (state_order.get(o["state"], 6), timestamp(o["observed_at"]), o["evidence_id"]))
        if obs["category"] in {"SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"}:
            retention_checks.append(retention_proof(obs, cutoff, observations))
        action, gap = _policy(rules, obs, cutoff, observations)
        if gap: gaps.append(gap)
        if not action: continue
        if obs["state"] == "UNKNOWN": gaps.append("Resource state unproved: " + obs["resource_id"])
        compliant = _compliant(action, obs)
        if not compliant and action in FINDING and obs["state"] != FINDING[action][1]:
            gaps.append("Policy treatment lacks violation-state proof: " + obs["resource_id"])
        if action == "RETAIN" and not compliant:
            gaps.append("Required retained record unavailable: " + obs["resource_id"])
            continue
        resources.append({"obs": obs, "action": action, "compliant": compliant})
        conditions.append({"resource_id": obs["resource_id"], "category": obs["category"],
                           "required_action": action, "proved": not bool(gap)})
        facts.append({"system_id": obs["system_id"], "resource_id": obs["resource_id"],
            "category": obs["category"], "state": obs["state"], "action": action, "compliant": compliant,
            "evidence_id": obs["evidence_id"], "source_location": obs["source_location"],
            "observed_at": obs["observed_at"]})
    for (system, rid), category in known.items():
        if (system, rid) not in grouped: gaps.append("Grounded resource lacks state proof: " + system + "/" + rid)
    identity_values = {a["value"].casefold() for a in identity["aliases"]}
    from .core import tokens
    claims = [e for e in index.activity if eligible(e["event_time"], cutoff) and
              ((e["target_system"], e["resource_id"]) in known or identity_values & tokens(e["details"]))]
    for claim in claims:
        key = claim["target_system"], claim["resource_id"]
        if key not in grouped and claim["event_type"] != "LINK_RESOURCE_IDENTITY":
            gaps.append("Activity links resource without state proof: " + claim["resource_id"])
    if not activity_inspected: gaps.append("Activity inspection required")
    if not resources: gaps.append("No identity-linked resource state")
    deferred = [fid for fid in index.opaque if eligible(index.manifest[fid]["captured_at"], cutoff)]
    # A scoped proof needs no unrelated service census or particular file format.
    # Missing matches never create ABSENT observations; those require a readback
    # or a grounded exact ID checked against a complete SQL table.
    coverage = {"resource_count": len(resources), "candidate_sources": len(candidates),
        "inspected_candidate_sources": len(set(candidates) & set(inspected)),
        "relevant_evidence_scopes": sorted({o["scope"] for o in observations}),
        "applicable_policy_conditions_checked": len(conditions),
        "complete_scope_certified": bool(resources) and not gaps and not contradictions and not deferred,
        "proof_boundary": "Eligible exact identity/resource links and inspected source scopes; no absence from unmatched data"}
    status = "INCOMPLETE" if any(not r["compliant"] for r in resources) else "COMPLETE" if resources else None
    if status == "COMPLETE" and deferred:
        gaps.append("Unextracted evidence prevents a COMPLETE determination")
    output = _make_output(request["case_id"], resources) if not gaps and not contradictions else None
    return {"resources": resources, "facts": facts, "observations": observations, "activity_claims": claims,
            "classification_status": status, "output": output,
            "ledger": {"identifiers_searched": identity["aliases"], "candidates": candidates,
                "eligible_sources_inspected": sorted(inspected), "activity_inspected": activity_inspected,
                "discovered_resources": sorted({rid for system, rid in known if rid}),
                "discovered_processes": sorted({r["obs"]["resource_id"] for r in resources if r["action"] in {"DISABLE", "BLOCK"}} |
                    {e["resource_id"] for e in claims if any(word in e["event_type"] for word in ("FLOW", "RESTORE", "BACKUP", "IMPORT"))}),
                "remaining_gaps": sorted(set(gaps)), "unresolved_contradictions": sorted(set(contradictions)),
                "deferred_sources": deferred, "identity_links": links,
                "contextual_evidence": contexts,
                "applicable_policy_conditions": conditions, "retention_assessments": retention_checks,
                "coverage": coverage}}


