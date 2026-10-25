"""Deterministic diagnostics through the bounded agent tools; no live inference."""
import argparse
import csv
import json
import re
from pathlib import Path

from .core import Investigation, Limits, Rejected, rows, explicit_deletion_signal
from .public_index import PublicIndex
from .engine import _policy, _compliant, _make_output, _scope_kind

def deletion_intent(text):
    """Clear multilingual deletion language. Ambiguity stays unresolved."""
    from .authorization import deletion_authorization
    return deletion_authorization(text)


def investigate(index, request, case_seconds=10):
    # Scripted policy proposals exercise the same tools/validator as the model.
    # This is diagnostic evaluation, not a measured model decision.
    session = Investigation(index, request, Limits(tool_calls=128, case_seconds=case_seconds))
    intent = deletion_intent(request["request_text"])
    try:
        if intent is None:
            raise Rejected("Deletion authorization ambiguous; requires model judgment")
        if intent:
            session.call("resolve_identity", {})
            while True:
                pending = [fid for fid in session.ledger["candidates"]
                           if fid not in session.ledger["eligible_sources_inspected"]]
                if not pending: break
                session.call("inspect_evidence", {"evidence_id": pending[0]})
            session.call("inspect_activity", {})
            proposal = session.decision_proposal()
        else:
            proposal = {"authorized": False, "request_quote": request["request_text"],
                        "deletion_status": "NOT_APPLICABLE", "resources": []}
        session.call("propose_decision", proposal)
    except Rejected as exc:
        if str(exc) not in session.ledger["remaining_gaps"]:
            session.ledger["remaining_gaps"].append(str(exc))
    result = session.report()
    result["execution_kind"] = "DETERMINISTIC_DIAGNOSTIC_NOT_LIVE_AGENT"
    result["model_usage"] = {"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
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
