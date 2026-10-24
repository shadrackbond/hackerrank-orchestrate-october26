"""Review a genuine run and independently challenge its validator.

Reference answers, if requested, are opened here only AFTER prediction.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ghost_audit.core import EvidenceIndex, Investigation, Rejected, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[2] / "dataset")
    parser.add_argument("--compare-sample", action="store_true")
    args = parser.parse_args()
    report = json.loads((args.run_dir / "investigation.json").read_text())
    session = Investigation(EvidenceIndex(args.dataset), report["request"])
    accepted = None
    for event in report["trace"]:
        if event["tool"] == "propose_decision":
            if event["accepted"]:
                accepted = event["arguments"]
        elif event["accepted"]:
            session.call(event["tool"], event["arguments"])
    if not accepted:
        raise SystemExit("No accepted model proposal to review")
    mutated = copy.deepcopy(accepted)
    mutated["deletion_status"] = "COMPLETE" if accepted["deletion_status"] == "INCOMPLETE" else "INCOMPLETE"
    try:
        session.validate_proposal(mutated)
    except Rejected as exc:
        rejection = {"actor": "deterministic_review_probe_NOT_model", "proposal": mutated,
                     "rejected": True, "reason": str(exc)}
    else:
        raise AssertionError("Invalid status mutation was accepted")
    result = {"invalid_proposal_probe": rejection}
    if args.compare_sample:
        expected = next(r for r in rows(args.dataset / "sample_output.csv") if r["case_id"] == report["request"]["case_id"])
        expected["steps_json"] = json.loads(expected["steps_json"])
        result["exact_sample_match"] = expected == report["output"]
    (args.run_dir / "review_checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
