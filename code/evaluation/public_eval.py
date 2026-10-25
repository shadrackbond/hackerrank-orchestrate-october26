"""Compare a saved public prediction run against sample answers after prediction."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


FIELDS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")
STRUCTURE = ("phase", "system_id", "resource_id", "operation", "state")


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return {r["case_id"]: {**r, "steps": json.loads(r["steps_json"])} for r in csv.DictReader(stream)}


def shape(step):
    return tuple(step[k] for k in STRUCTURE)


def evaluate(reference_path, prediction_path, investigations_path):
    reference = read_csv(reference_path)
    prediction = read_csv(prediction_path)
    investigations = {r["case_id"]: r for r in json.loads(Path(investigations_path).read_text())}
    expected_ids = set(reference)
    if set(investigations) != expected_ids:
        raise ValueError("Investigation cases do not match public reference cases")
    status_correct = exact_cases = sequence_correct = true_steps = predicted_steps = matched_steps = 0
    fields_equal = fields_total = citation_mismatches = ordering_mismatches = 0
    groups = defaultdict(list)
    case_rows = []
    for case_id in sorted(expected_ids):
        ref = reference[case_id]
        pred = prediction.get(case_id)
        trace = investigations[case_id]
        expected, actual = ref["steps"], pred["steps"] if pred else []
        status_ok = bool(pred and pred["deletion_status"] == ref["deletion_status"])
        status_correct += status_ok
        exact = bool(pred and pred["deletion_status"] == ref["deletion_status"] and actual == expected)
        exact_cases += exact
        seq_ok = bool(pred and [shape(x) for x in actual] == [shape(x) for x in expected])
        sequence_correct += seq_ok
        ecounts, acounts = Counter(map(shape, expected)), Counter(map(shape, actual))
        true_steps += len(expected); predicted_steps += len(actual)
        matched_steps += sum((ecounts & acounts).values())
        if ecounts == acounts and not seq_ok: ordering_mismatches += 1
        # Field agreement is over aligned expected slots, with missing slots wrong.
        for slot, want in enumerate(expected):
            got = actual[slot] if slot < len(actual) else {}
            for key in FIELDS:
                fields_total += 1
                fields_equal += got.get(key) == want[key]
        if pred:
            expected_cites = Counter((shape(x), x["evidence_id"]) for x in expected)
            actual_cites = Counter((shape(x), x["evidence_id"]) for x in actual)
            same_structure = sum((ecounts & acounts).values())
            same_citation = sum((expected_cites & actual_cites).values())
            citation_mismatches += same_structure - same_citation
        if exact:
            group, earliest = "exact", None
        elif not pred:
            group = "unresolved"
            earliest = trace["ledger"]["remaining_gaps"][0] if trace["ledger"]["remaining_gaps"] else "No accepted decision"
        elif not status_ok:
            group = "status"
            if expected:
                first = next((s for s in expected if s["resource_id"] not in
                              {f["resource_id"] for f in trace["facts"]}), None)
                earliest = ("Missing identity-linked observation for " + first["resource_id"]) if first else \
                           "Observed resource state or policy treatment disagrees with reference"
            else: earliest = "Deletion authorization classification disagrees with reference"
        elif ecounts != acounts:
            group = "step_set"
            missing = list((ecounts - acounts).elements())
            if missing:
                item = missing[0]
                rid = item[2]
                earliest = ("Missing identity-linked observation for " + rid) if rid not in \
                    {f["resource_id"] for f in trace["facts"]} else \
                    ("Wrong policy state or plan for " + rid)
            else: earliest = "Extra step from an incorrectly linked or assessed resource"
        elif ordering_mismatches and not seq_ok:
            group, earliest = "ordering", "Step order differs after resource decisions"
        else:
            group, earliest = "citation_or_field", "Citation or output field differs after resource decisions"
        if group != "exact": groups[group].append({"case_id": case_id, "earliest_incorrect_fact": earliest})
        case_rows.append({"case_id": case_id, "resolved": pred is not None,
                          "expected_status": ref["deletion_status"],
                          "predicted_status": pred["deletion_status"] if pred else None,
                          "status_correct": status_ok, "whole_case_exact": exact,
                          "sequence_exact": seq_ok, "group": group,
                          "earliest_incorrect_fact": earliest})
    count = len(expected_ids)
    return {"cases_attempted": count, "cases_resolved": len(prediction),
            "cases_unresolved": count - len(prediction),
            "status_accuracy_all_cases": status_correct / count,
            "whole_case_exact_agreement_all_cases": exact_cases / count,
            "step_precision": matched_steps / predicted_steps if predicted_steps else 0,
            "step_recall": matched_steps / true_steps if true_steps else 0,
            "field_accuracy": fields_equal / fields_total if fields_total else 0,
            "exact_sequence_agreement_all_cases": sequence_correct / count,
            "citation_mismatched_steps": citation_mismatches,
            "ordering_mismatched_cases": ordering_mismatches,
            "counts": {"status_correct": status_correct, "whole_case_exact": exact_cases,
                       "sequence_exact": sequence_correct, "matched_steps": matched_steps,
                       "predicted_steps": predicted_steps, "reference_steps": true_steps,
                       "matched_fields": fields_equal, "reference_fields": fields_total},
            "mismatch_groups": dict(groups), "cases": case_rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--investigations", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.reference, args.predictions, args.investigations)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"cases", "mismatch_groups"}}, indent=2))


if __name__ == "__main__": main()
