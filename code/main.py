"""Run one review case. This intentionally does not emit the submission output.csv."""
import argparse
import json
import subprocess
from pathlib import Path

from ghost_audit.core import Limits, rows, write_csv
from ghost_audit.extraction import prepare_visual_index
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
    parser.add_argument("--visual-cache", type=Path,
                        help="Content-hash cache for PDF and image text. Extracts missing artifacts before audit.")
    parser.add_argument("--visual-extractor", choices=["local-ocr", "codex-vision"], default="local-ocr")
    args = parser.parse_args()
    limits = Limits(args.tool_calls, args.proposal_attempts, args.tool_seconds, args.case_seconds)
    if min(vars(limits).values()) <= 0:
        parser.error("All limits must be positive")
    request_file = "sample_deletion_requests.csv" if args.samples else "deletion_requests.csv"
    requests = [r for r in rows(args.dataset / request_file) if r["case_id"] == args.case]
    if len(requests) != 1:
        parser.error("Case ID must resolve to exactly one request")
    extraction = None
    if args.visual_cache:
        try:
            extraction = prepare_visual_index(args.dataset, args.visual_cache, args.model,
                                              audit_at=requests[0]["audit_at"],
                                              image_extractor=args.visual_extractor)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            args.run_dir.mkdir(parents=True, exist_ok=False)
            failure = {"internal_state": "UNRESOLVED", "output": None,
                       "ledger": {"remaining_gaps": ["Visual extraction failed: " + str(exc)]}}
            (args.run_dir / "investigation.json").write_text(json.dumps(failure, indent=2) + "\n")
            print(json.dumps(failure, indent=2))
            return 2
    result, usage = run_codex(args.dataset, requests[0], request_file, args.run_dir, args.model, limits,
                              args.visual_cache, args.visual_extractor)
    if extraction:
        (args.run_dir / "extraction_usage.json").write_text(json.dumps(extraction, indent=2) + "\n")
    if result["output"]:
        write_csv(args.run_dir / "review_output.csv", result["output"])
    print(json.dumps({"internal_state": result["internal_state"], "output": result["output"],
                      "usage": usage, "report": str(args.run_dir / "investigation.json")}, indent=2))
    return 0 if result["output"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
