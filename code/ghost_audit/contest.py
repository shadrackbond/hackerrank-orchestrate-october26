"""Best-effort contest predictions; evidence certification remains independent.

No references or saved labels are inputs. Current participant data and cached
extractions are reassessed with the shared identity/cutoff/policy engine.
Unknown retention never supplies a record action. Unproved completion defaults
to an explicitly uncertain INCOMPLETE prediction, not an invented finding.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import time

from .authorization import deletion_authorization
from .contract import FIELDS, RANK, validate_report
from .core import Investigation, Limits, Rejected, eligible, rows
from .engine import FINDING, REMEDIATE, VERIFY, _make_output
from .public_index import PublicIndex


def contest_intent(text):
    """General multilingual vocabulary plus explicit non-deletion scope.

    Unknown language stays uncertain. Negation is checked before extending the
    strict diagnostic recognizer; this function never equates unknown with NO.
    """
    known = deletion_authorization(text)
    if known is not None:
        return known, "existing_clause_scope_recognizer"
    value = text.casefold()
    portuguese = bool(re.search(r"\b(?:exclus[aã]o|excluir|apagar|eliminar)\b", value)
                      and re.search(r"\b(?:conta|dados pessoais)\b", value))
    korean = "삭제" in value and any(word in value for word in ("계정", "개인정보"))
    if portuguese and not re.search(r"\b(?:n[aã]o|nunca|sem)\b.{0,45}\b(?:exclu\w*|apagar|eliminar)", value):
        return True, "portuguese_deletion_and_account_vocabulary"
    if korean and not any(word in value for word in ("삭제하지", "삭제를 원하지", "삭제하지마")):
        return True, "korean_deletion_and_account_vocabulary"
    # Correction, access and export requests need a recognizable action and
    # scope. Absence of a deletion keyword alone is never a NO decision.
    nondelete = re.search(r"\b(?:change|replace|correct|reset|download|export|send|copy|tell)\b", value)
    scoped = re.search(r"\b(?:email|phone|mobile|surname|name|login|information|invoices|records|data)\b", value)
    preservation = re.search(r"\b(?:keep|leave|continue|still use|account active|without removing)\b", value)
    if nondelete and scoped and preservation:
        return False, "recognized_access_correction_export_with_preservation"
    return None, "unrecognized_or_ambiguous_intent"


def investigate_contest(index, request):
    session = Investigation(index, request, Limits(tool_calls=128, case_seconds=30))
    intent, intent_basis = contest_intent(request["request_text"])
    if intent is False:
        proposal = {"authorized": False, "request_quote": request["request_text"],
                    "deletion_status": "NOT_APPLICABLE", "resources": []}
        session.call("propose_decision", proposal)
    else:
        try:
            session.call("resolve_identity", {})
            while True:
                pending = sorted(set(session.ledger["candidates"]) - session.inspected)
                if not pending:
                    break
                session.call("inspect_evidence", {"evidence_id": pending[0]})
            session.call("inspect_activity", {})
            if intent is True:
                try:
                    session.call("propose_decision", session.decision_proposal())
                except Rejected:
                    pass  # Missing certification does not suppress a prediction.
        except Rejected as exc:
            session.ledger["remaining_gaps"].append(str(exc))
    report = session.report()
    report["execution_kind"] = "BEST_EFFORT_CONTEST_NO_MODEL_CALLS"
    report["intent"] = {"authorized": intent, "basis": intent_basis}
    report["certified_output"] = report["output"]
    if report["certified_output"]:
        validate_report(report)
    conditions = report["ledger"].get("applicable_policy_conditions", [])
    usable = []
    for resource in (session.assessment or {}).get("resources", []):
        obs, action = resource["obs"], resource["action"]
        condition = any(c["resource_id"] == obs["resource_id"] and c["required_action"] == action
                        and c["proved"] for c in conditions)
        if not condition or not obs["system_id"] or not obs["resource_id"]:
            continue
        if not eligible(obs["capture_at"], request["audit_at"]) or not eligible(obs["observed_at"], request["audit_at"]):
            continue
        if resource["compliant"] or action in FINDING and obs["state"] == FINDING[action][1]:
            usable.append(resource)
    violation = any(not r["compliant"] for r in usable)
    if intent is False:
        output = {"case_id": request["case_id"], "deletion_status": "NOT_APPLICABLE", "steps_json": []}
        established, reason = True, "supported_non_deletion_intent"
    elif intent is True and report["certified_output"]:
        output = report["certified_output"]
        established, reason = True, "shared_engine_certified_scope"
    else:
        output = _make_output(request["case_id"], usable)
        # A compliant assessed subset is not proof that the whole case is done.
        output["deletion_status"] = "INCOMPLETE"
        for step in output["steps_json"]:
            if step["phase"] != "FINDING":
                step["evidence_id"] = ""
        established = bool(intent is True and violation)
        reason = "grounded_policy_violation" if established else "precautionary_prediction_completion_unproved"
    report["output"] = output
    report["prediction_assessment"] = {
        "status_established": established, "status_basis": reason,
        "plan_certified": bool(report["certified_output"]),
        "plan_scope": "known linked resources only; exhaustive discovery is not guaranteed",
        "included_resources": len(usable),
        "excluded_policy_or_state_resources": len((session.assessment or {}).get("resources", [])) - len(usable),
        "limitations": sorted(set(report["ledger"]["remaining_gaps"] +
                                   report["ledger"].get("unresolved_contradictions", []))),
    }
    validate_prediction(report)
    return report


def validate_prediction(report):
    """Strict schema and grounding checks, independent of completeness acceptance."""
    output, cutoff = report["output"], report["request"]["audit_at"]
    if set(output) != {"case_id", "deletion_status", "steps_json"} or output["case_id"] != report["case_id"]:
        raise Rejected("Invalid prediction identity/columns")
    status, steps = output["deletion_status"], output["steps_json"]
    if status not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"} or not isinstance(steps, list):
        raise Rejected("Invalid prediction status/JSON")
    if status == "COMPLETE" and not report.get("certified_output"):
        raise Rejected("Unproved COMPLETE prediction")
    if status == "NOT_APPLICABLE" and (steps or report["intent"]["authorized"] is not False):
        raise Rejected("Unsupported non-deletion prediction")
    pairs = {("FINDING", *v) for v in FINDING.values()} | {("REMEDIATION", *v) for v in REMEDIATE.values()} | {("VERIFICATION", *v) for v in VERIFY.values()}
    facts = {(f["system_id"], f["resource_id"]): f for f in report["facts"]}
    order, seen = [], set()
    for number, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != FIELDS or type(step["step_no"]) is not int or step["step_no"] != number:
            raise Rejected("Invalid step fields/numbering")
        if any(not isinstance(step[k], str) for k in FIELDS - {"step_no"}):
            raise Rejected("Invalid step field types")
        if (step["phase"], step["operation"], step["state"]) not in pairs:
            raise Rejected("Invalid operation/state pair")
        key = step["system_id"], step["resource_id"]
        if not all(key) or key not in facts:
            raise Rejected("Ungrounded resource")
        fact = facts[key]
        mapping = {"FINDING": FINDING, "REMEDIATION": REMEDIATE, "VERIFICATION": VERIFY}[step["phase"]]
        if mapping.get(fact["action"]) != (step["operation"], step["state"]):
            raise Rejected("Step disagrees with current policy action")
        if step["phase"] != "VERIFICATION" and fact["compliant"]:
            raise Rejected("Compliant resource cannot be a finding/remediation")
        if step["phase"] == "FINDING" and fact["state"] != FINDING[fact["action"]][1]:
            raise Rejected("Finding lacks a demonstrated violation state")
        if not any(c["resource_id"] == key[1] and c["required_action"] == fact["action"] and c["proved"]
                   for c in report["ledger"].get("applicable_policy_conditions", [])):
            raise Rejected("Unproved policy condition")
        signature = (step["phase"], *key, step["operation"])
        if signature in seen:
            raise Rejected("Duplicate step")
        seen.add(signature)
        order.append((RANK[step["operation"]], *key))
        cited = step["phase"] == "FINDING" or status == "COMPLETE"
        if cited:
            if step["evidence_id"] != fact["evidence_id"] or not any(
                (o["system_id"], o["resource_id"]) == key and o["evidence_id"] == step["evidence_id"]
                and o["state"] == fact["state"] and eligible(o["capture_at"], cutoff)
                and eligible(o["observed_at"], cutoff) for o in report["observations"]):
                raise Rejected("Invalid or post-cutoff state citation")
        elif step["evidence_id"]:
            raise Rejected("Future steps require empty citations")
    if order != sorted(order):
        raise Rejected("Noncanonical step order")
    return output


def validate_csv(path, requests):
    expected = sorted(r["case_id"] for r in requests)
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["case_id", "deletion_status", "steps_json"]:
            raise Rejected("Invalid CSV header")
        data = list(reader)
    ids = [r["case_id"] for r in data]
    if len(set(expected)) != len(expected) or ids != expected or len(set(ids)) != len(ids):
        raise Rejected("CSV must contain every unique requested case, sorted")
    for row in data:
        if set(row) != {"case_id", "deletion_status", "steps_json"}:
            raise Rejected("Extra or missing CSV columns")
        if row["deletion_status"] not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"} or not isinstance(json.loads(row["steps_json"]), list):
            raise Rejected("Invalid serialized status/JSON")
        steps = json.loads(row["steps_json"])
        if row["deletion_status"] == "NOT_APPLICABLE" and steps:
            raise Rejected("Non-deletion row must have empty steps")
        order, seen = [], set()
        pairs = {("FINDING", *v) for v in FINDING.values()} | {("REMEDIATION", *v) for v in REMEDIATE.values()} | {("VERIFICATION", *v) for v in VERIFY.values()}
        for number, step in enumerate(steps, 1):
            if not isinstance(step, dict) or set(step) != FIELDS or type(step["step_no"]) is not int or step["step_no"] != number:
                raise Rejected("Invalid serialized step fields or numbering")
            if any(not isinstance(step[k], str) for k in FIELDS - {"step_no"}):
                raise Rejected("Invalid serialized step types")
            if not step["system_id"] or not step["resource_id"] or (step["phase"], step["operation"], step["state"]) not in pairs:
                raise Rejected("Invalid serialized resource or operation/state")
            cited = step["phase"] == "FINDING" or row["deletion_status"] == "COMPLETE"
            if bool(step["evidence_id"]) != cited:
                raise Rejected("Incorrect serialized citation placement")
            signature = (step["phase"], step["system_id"], step["resource_id"], step["operation"])
            if signature in seen:
                raise Rejected("Duplicate serialized step")
            seen.add(signature)
            order.append((RANK[step["operation"]], step["system_id"], step["resource_id"]))
        if order != sorted(order):
            raise Rejected("Noncanonical serialized step order")
    return len(data)


def run(dataset, cache, run_dir, output, samples=False):
    started = time.monotonic()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "cases").mkdir()
    requests = rows(Path(dataset) / ("sample_deletion_requests.csv" if samples else "deletion_requests.csv"))
    if not samples and len(requests) != 518:
        raise Rejected("Expected 518 participant requests")
    index = PublicIndex(dataset, cache)
    reports, uncertainties = [], []
    with Path(output).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, ["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for n, request in enumerate(sorted(requests, key=lambda r: r["case_id"]), 1):
            report = investigate_contest(index, request)
            (run_dir / "cases" / f"{n:04d}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            prediction = report["output"]
            writer.writerow({**prediction, "steps_json": json.dumps(prediction["steps_json"], separators=(",", ":"))})
            uncertainties.append({"case_id": request["case_id"], "prediction": prediction["deletion_status"],
                                  "intent": report["intent"], **report["prediction_assessment"]})
            if samples:
                reports.append(report)
            if n % 100 == 0:
                print(json.dumps({"processed": n}), flush=True)
    validate_csv(output, requests)
    if samples:
        (run_dir / "investigations.json").write_text(json.dumps(reports, ensure_ascii=False) + "\n")
    (run_dir / "uncertainty_report.json").write_text(json.dumps(uncertainties, ensure_ascii=False, indent=2) + "\n")
    summary = {"execution_kind": "BEST_EFFORT_CONTEST_NO_MODEL_CALLS", "requests": len(requests),
               "status_counts": dict(Counter(r["prediction"] for r in uncertainties)),
               "established_statuses": sum(r["status_established"] for r in uncertainties),
               "inferred_statuses": sum(not r["status_established"] for r in uncertainties),
               "scope_certified_plans": sum(r["plan_certified"] for r in uncertainties),
               "uncertified_plans": sum(not r["plan_certified"] for r in uncertainties),
               "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
               "wall_seconds": time.monotonic() - started, "output": str(output),
               "limitations": "Best effort; scoped certification is not exhaustive discovery or hidden accuracy"}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[2] / "dataset")
    parser.add_argument("--visual-cache", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", action="store_true")
    args = parser.parse_args(argv)
    run(args.dataset, args.visual_cache, args.run_dir, args.output, args.samples)
    return 0
