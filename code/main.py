"""Deletion audit: cached batch diagnostics, local extraction, or one bounded live review."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from ghost_audit.core import Limits, rows, write_csv
from ghost_audit.extraction import prepare_visual_index
from ghost_audit.runtime import run_codex


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "submit":
        from ghost_audit.contest import main as contest
        return contest(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "diagnostic":
        from ghost_audit.delivery import main as diagnostic
        return diagnostic(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "extract":
        parser = argparse.ArgumentParser(description="Prepare content-hash visual caches using local PDF/OCR tools; no model calls")
        parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "dataset")
        parser.add_argument("--visual-cache", type=Path, required=True)
        args = parser.parse_args(sys.argv[2:])
        print(json.dumps(prepare_visual_index(args.dataset, args.visual_cache, "local-ocr", image_extractor="local-ocr"), indent=2))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "dataset")
    parser.add_argument("--case", required=True)
    parser.add_argument("--samples", action="store_true")
    parser.add_argument("--model", required=True, help="Exact model identifier passed to the configured runtime")
    parser.add_argument("--run-dir", type=Path, required=True, help="New directory for review artifacts")
    parser.add_argument("--resume", action="store_true", help="Revalidate an existing sealed decision without a model call")
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
    if args.resume and args.run_dir.exists():
        from ghost_audit.saved import load, revalidate
        from ghost_audit.public_index import PublicIndex
        from ghost_audit.core import Rejected
        try:
            manifest, saved = load(args.run_dir / "decision.json")
            if (manifest.get("runtime_configuration") or {}).get("model") != args.model:
                raise Rejected("Resume model differs from saved runtime configuration")
            index = PublicIndex(args.dataset, args.visual_cache,
                "local-ocr" if args.visual_extractor == "local-ocr" else args.model)
            result = revalidate(index, requests[0], manifest, saved, limits)
            print(json.dumps({"resumed": True, "new_model_calls": 0, "output": result["output"]}, indent=2))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(json.dumps({"resumed": False, "new_model_calls": 0, "error": str(exc),
                "next_action": "Preserve this attempt; use a fresh run directory for a new investigation"}, indent=2))
            return 2
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
