"""Independent delivery checks over accepted, evidence-backed case reports."""
from .core import Rejected, eligible
from .engine import FINDING, REMEDIATE, VERIFY

FIELDS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}
RANK = {op: n for n, op in enumerate([
    "REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK",
    "DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD",
    "VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED", "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"])}


def validate_report(report):
    output = report.get("output")
    if not output:
        raise Rejected("No accepted decision; unresolved cases cannot be serialized")
    if set(output) != {"case_id", "deletion_status", "steps_json"} or output["case_id"] != report["case_id"]:
        raise Rejected("Invalid case output fields or identity")
    status, steps = output["deletion_status"], output["steps_json"]
    if status not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"} or not isinstance(steps, list):
        raise Rejected("Invalid status or steps")
    if status == "NOT_APPLICABLE":
        if steps: raise Rejected("Non-deletion output must have no steps")
        return output
    ledger = report["ledger"]
    if ledger["remaining_gaps"] or ledger["unresolved_contradictions"]:
        raise Rejected("Unresolved evidence or policy conditions")
    if status == "COMPLETE" and not ledger["coverage"]["complete_scope_certified"]:
        raise Rejected("Compliant scope is not proved")
    facts = {(f["system_id"], f["resource_id"]): f for f in report["facts"]}
    expected = set()
    for key, fact in facts.items():
        action = fact["action"]
        expected.add(("VERIFICATION", *key, *VERIFY[action]))
        if not fact["compliant"]:
            expected.add(("FINDING", *key, *FINDING[action]))
            expected.add(("REMEDIATION", *key, *REMEDIATE[action]))
    observed, order = set(), []
    cutoff = report["request"]["audit_at"]
    for number, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != FIELDS or type(step["step_no"]) is not int or step["step_no"] != number:
            raise Rejected("Invalid step fields or numbering")
        if any(not isinstance(step[k], str) for k in FIELDS - {"step_no"}):
            raise Rejected("Step values must be strings")
        key = step["system_id"], step["resource_id"]
        signature = (step["phase"], *key, step["operation"], step["state"])
        if signature not in expected or signature in observed or not all(key):
            raise Rejected("Step is duplicate, ungrounded, or inconsistent with policy")
        observed.add(signature)
        order.append((RANK[step["operation"]], *key))
        cite_required = step["phase"] == "FINDING" or status == "COMPLETE"
        if cite_required:
            fact = facts[key]
            if step["evidence_id"] != fact["evidence_id"] or not any(
                    (o["system_id"], o["resource_id"]) == key and o["evidence_id"] == step["evidence_id"]
                    and o["state"] == fact["state"] and eligible(o["capture_at"], cutoff)
                    and eligible(o["observed_at"], cutoff) for o in report["observations"]):
                raise Rejected("Citation does not prove the accepted resource state at audit_at")
        elif step["evidence_id"] != "":
            raise Rejected("Future remediation and verification must have empty citations")
    if observed != expected or order != sorted(order):
        raise Rejected("Step coverage or ordering is invalid")
    if not steps or (status == "COMPLETE") != all(f["compliant"] for f in facts.values()):
        raise Rejected("Status disagrees with grounded resource facts")
    return output
