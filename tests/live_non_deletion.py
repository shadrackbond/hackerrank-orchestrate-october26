"""Optional live model acceptance test. Requires configured Codex access."""
import argparse
import json
import sys
from pathlib import Path

from test_audit import fixture, csv_file
from ghost_audit.core import Limits
from ghost_audit.runtime import run_codex


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.run_dir.with_name(args.run_dir.name + "-input")
    dataset.mkdir(parents=True, exist_ok=False)
    request = fixture(dataset)
    request["case_id"] = "custom_non_deletion"
    request["request_text"] = "Please send me a portable copy of my records. Do not delete my account or change my information."
    csv_file(dataset / "sample_deletion_requests.csv", list(request), [request])
    report, usage = run_codex(dataset, request, "sample_deletion_requests.csv", args.run_dir, args.model,
                              Limits(tool_calls=4, proposal_attempts=2, case_seconds=120))
    expected = {"case_id": "custom_non_deletion", "deletion_status": "NOT_APPLICABLE", "steps_json": []}
    passed = report["output"] == expected
    (args.run_dir / "acceptance.json").write_text(json.dumps({"passed": passed, "expected": expected}, indent=2))
    print(json.dumps({"passed": passed, "output": report["output"], "usage": usage}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
