"""Run one review case. This intentionally does not emit the submission output.csv."""
import argparse
import json
from pathlib import Path

from ghost_audit.core import Limits, rows, write_csv
from ghost_audit.runtime import run_codex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "dataset")
    parser.add_argument("--case", required=True)
    parser.add_argument("--samples", action="store_true")
    parser.add_argument("--model", required=True, help="Exact model identifier passed to the configured runtime")
    parser.add_argument("--run-dir", type=Path, required=True, help="New directory for review artifacts")
    parser.add_argument("--tool-calls", type=int, default=10)
    parser.add_argument("--proposal-attempts", type=int, default=3)
    parser.add_argument("--tool-seconds", type=float, default=10)
    parser.add_argument("--case-seconds", type=float, default=180)
    args = parser.parse_args()
    limits = Limits(args.tool_calls, args.proposal_attempts, args.tool_seconds, args.case_seconds)
    if min(vars(limits).values()) <= 0:
        parser.error("All limits must be positive")
    request_file = "sample_deletion_requests.csv" if args.samples else "deletion_requests.csv"
    requests = [r for r in rows(args.dataset / request_file) if r["case_id"] == args.case]
    if len(requests) != 1:
        parser.error("Case ID must resolve to exactly one request")
    result, usage = run_codex(args.dataset, requests[0], request_file, args.run_dir, args.model, limits)
    if result["output"]:
        write_csv(args.run_dir / "review_output.csv", result["output"])
    print(json.dumps({"internal_state": result["internal_state"], "output": result["output"],
                      "usage": usage, "report": str(args.run_dir / "investigation.json")}, indent=2))
    return 0 if result["output"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
