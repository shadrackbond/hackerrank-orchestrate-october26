"""Cached deterministic batch diagnostics and fail-closed submission publication."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import time

from .core import Rejected, rows
from .contract import validate_report
from .public_index import PublicIndex
from .public_runner import investigate


def batch(dataset, cache, run_dir, samples=False, case_seconds=30, publish=None):
    started = time.monotonic()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    request_file = "sample_deletion_requests.csv" if samples else "deletion_requests.csv"
    requests = rows(Path(dataset) / request_file)
    ids = [r["case_id"] for r in requests]
    if len(ids) != len(set(ids)) or any(not v for v in ids):
        raise Rejected("Request IDs must be unique and nonempty")
    if not samples and len(requests) != 518:
        raise Rejected("Submission requires exactly 518 requests")
    index = PublicIndex(dataset, cache)
    indexed_seconds = time.monotonic() - started
    (run_dir / "cases").mkdir()
    accepted, unresolved, public_reports, causes = [], [], [], Counter()
    for number, request in enumerate(sorted(requests, key=lambda r: r["case_id"]), 1):
        report = investigate(index, request, case_seconds)
        if report.get("output"):
            try:
                validate_report(report)
            except Rejected as exc:
                report["delivery_validation_error"] = str(exc)
                report["output"] = None
                report["internal_state"] = "UNRESOLVED"
                report["ledger"]["remaining_gaps"].append("Delivery validation: " + str(exc))
        # Numeric file names are sequence positions, never interpreted as identity links.
        report_path = run_dir / "cases" / f"{number:04d}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if samples: public_reports.append(report)
        if report["output"]:
            accepted.append(report["output"])
        else:
            gaps = report["ledger"]["remaining_gaps"] + report["ledger"].get("unresolved_contradictions", [])
            gaps = sorted(set(gaps or [report.get("halt_reason") or "No accepted decision"]))
            unresolved.append({"case_id": request["case_id"], "report": str(report_path), "causes": gaps})
            for gap in gaps:
                # Group diagnostics by the stable message prefix; retain exact messages above.
                if not gap.startswith("Unresolved investigation gaps:"):
                    causes[gap.split(":", 1)[0]] += 1
        if number % 50 == 0:
            print(json.dumps({"processed": number, "resolved": len(accepted), "unresolved": len(unresolved)}), flush=True)
    if samples:
        (run_dir / "investigations.json").write_text(json.dumps(public_reports, ensure_ascii=False, indent=2) + "\n")
    partial = run_dir / "supported_partial.csv"
    write_outputs(partial, accepted)
    # Compatibility with the evaluator; this is still only the accepted subset.
    if samples: write_outputs(run_dir / "predictions.csv", accepted)
    (run_dir / "unresolved.json").write_text(json.dumps(unresolved, indent=2) + "\n")
    summary = {"execution_kind": "DETERMINISTIC_DIAGNOSTIC_NOT_LIVE_AGENT", "requests": request_file,
        "attempted": len(requests), "resolved": len(accepted), "unresolved": len(unresolved),
        "status_counts": dict(Counter(o["deletion_status"] for o in accepted)),
        "cause_counts": dict(causes), "index_seconds": indexed_seconds,
        "wall_seconds": time.monotonic() - started, "model_calls": 0,
        "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
        "observations": len(index.observations), "adapter_gaps": index.adapter_gaps,
        "source_assessments": index.source_assessments,
        "evidence_digest": index.digest.hexdigest(), "published_output": None,
        "limitations": "Diagnostic intent heuristics; no new model judgment. Resolved scope is not proof of exhaustive discovery."}
    if publish:
        if samples or unresolved or len(accepted) != 518:
            summary["publication_blocker"] = "Every one of the 518 requests must have a validated, grounded decision"
        elif Path(publish).exists():
            summary["publication_blocker"] = "Refusing to replace an existing output; preserve it before publishing"
        else:
            write_outputs(Path(publish), accepted)
            summary["published_output"] = str(publish)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"source_assessments", "adapter_gaps"}}, indent=2))
    return summary


def write_outputs(path, outputs):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, ["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for output in sorted(outputs, key=lambda o: o["case_id"]):
            writer.writerow({**output, "steps_json": json.dumps(output["steps_json"], separators=(",", ":"))})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[2] / "dataset")
    parser.add_argument("--visual-cache", type=Path, required=True, help="Existing content-hash cache; never starts inference or extraction")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--samples", action="store_true")
    parser.add_argument("--case-seconds", type=float, default=30)
    parser.add_argument("--publish-output", type=Path, help="Write only if all 518 decisions pass the evidence and contract gate")
    args = parser.parse_args(argv)
    if args.case_seconds <= 0: parser.error("case-seconds must be positive")
    result = batch(args.dataset, args.visual_cache, args.run_dir, args.samples, args.case_seconds, args.publish_output)
    return 0 if not result["unresolved"] else 2
