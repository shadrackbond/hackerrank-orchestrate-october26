# Ghost Data Still Exists — best-effort contest submission

This submission predicts all 518 participant requests. It has known correctness and
coverage limitations: prediction, status evidence, and plan certification are separate.
No hidden accuracy is claimed. Public reference answers are used only by the evaluation
command after predictions have been saved.

## Setup and run

Python 3.11+ and the participant `dataset/` directory are required. Install:

```bash
python3 -m pip install -r requirements.txt
```

Existing content-hash extraction caches can be reused. If starting from the source ZIP,
prepare them locally (no model calls); PDF/OCR extraction needs `pdftotext`, `pdftoppm`,
the Tesseract shared library and English data (`poppler-utils libtesseract5 tesseract-ocr-eng`
on Debian/Ubuntu):

```bash
python3 code/main.py extract --visual-cache runs/visual-cache
python3 code/main.py submit --visual-cache runs/visual-cache --run-dir runs/submission --output output.csv
```

Use a new run directory and a nonexistent output path. The submission command does not
launch extraction, network requests, or model investigations. It produces all requested
rows, per-case evidence reports, a summary, and `runs/submission/uncertainty_report.json`.
The delivered root `uncertainty_report.json` is a copy from the measured final run.
Keep it separate from the three-column submission schema.

## Decision rules and evidence boundary

The existing shared index resolves current and historical identities, follows exact
resource links, applies both capture and observation cutoffs, and assesses supplied
policy conditions against cached participant evidence. All existing sources are
revalidated through this current path; saved labels and reference-derived IDs are
never imported as evidence. The pre-final sources and reports were preserved under
`checkpoints/pre-final-submission/` in the working checkout, outside code.zip.

Recognized account/data deletion vocabulary establishes intent, including general
Portuguese and Korean vocabulary. Recognized correction/access/export requests with
preservation scope establish non-deletion intent. Unrecognized language remains
uncertain and never implies NOT_APPLICABLE.

A grounded violation establishes INCOMPLETE despite unrelated gaps. COMPLETE requires
the strict shared engine's successful scoped evidence check. When neither status can
be proved, the contest prediction is conservatively INCOMPLETE, explicitly marked as
inferred in the uncertainty report. This does not claim a violation was observed.
Workflow reported statuses are not used as proof or fallback labels.

Only currently proved policy actions and resource states contribute steps. Unknown
retention does not authorize deletion, establish compliance, or erase an independent
violation. Unproved resources are omitted and recorded as gaps. Some inferred rows
therefore have empty step arrays. Plans remain uncertified where coverage is missing.
No identifiers, citations, retention dates, or anonymous-resource associations are invented.

Steps follow FINDING, REMEDIATION, VERIFICATION, with canonical operation/system/resource
ordering and disabling/blocking before record treatment. Findings and COMPLETE checks
cite eligible evidence; future INCOMPLETE remediation/verification citations are empty.
Structural and grounding validators check schema, exact requested case sets, numbering,
operation/state pairs, ordering, current policy actions, citations and time eligibility.
The retained scoped certificates cannot guarantee exhaustive discovery or OCR completeness.
No grounded explicit resource dependency relationships were present in the final reports;
unknown dependencies remain a coverage limitation.

## Results, evaluation and tests

See `evaluation/evaluation_report.md` and `evaluation/usage_report.md` for the actual
output-producing run and one public evaluation. Run independent tests with:

```bash
python3 -m unittest discover -s tests -q
```

The final path's public predictions and evidence were saved before references were read:

```bash
python3 code/main.py submit --samples --visual-cache runs/visual-cache --run-dir runs/public-final --output runs/public-final/predictions.csv
python3 code/evaluation/public_eval.py --reference dataset/sample_output.csv --predictions runs/public-final/predictions.csv --investigations runs/public-final/investigations.json --report runs/public-final/evaluation.json
```

`diagnostic` and the bounded live/resume tools remain available for research; their
strict acceptance gates are separate from the explicitly selected `submit` path.
Prompts are preserved in `code/ghost_audit/runtime.py` and `extraction.py`.

## Artifacts and native traces

`code.zip` contains sources, tests, requirements, this README, and both evaluation reports.
It excludes participant data, caches, runtime traces, checkpoints, nested archives and credentials.
`output.csv`, root `log.txt`, and native `agent-trace.zip` are separate deliverables.

The trace ZIP created during the final session includes completed Codex sessions and
genuine application-native events. It deliberately excludes the still-active session.
Follow `agent_trace_instructions.md`: after quitting Codex, run from this repository:

```bash
python3 code/export_traces.py --after-session-exit
```

This refreshes `agent-trace.zip` with the now-closed session and writes
`trace_export_manifest.json`. Review the ZIP before sharing. The exporter preserves
original files, redacts common token patterns only in exported copies, and excludes
configuration/authentication stores. Its automated redaction is not a guarantee that
all sensitive material has been removed.

## Interview notes

- Architecture: one participant-evidence index; historical identity graph; shared cutoff,
  policy and state assessment; separate best-effort compiler and strict structural validator.
- A workflow completion message is a claim. Readbacks, replicas, field values, disabled
  flows and blocked restores establish state; missing matches never establish absence.
- Status proof and plan coverage differ. One violation proves incompleteness; COMPLETE
  needs all required scoped conditions. Unknown retention remains unresolved.
- Final batch inference is deterministic and spends no model tokens. Earlier bounded
  model investigations and their native traces remain distinct from the final run.
- Main limitations: uncertain fallback statuses, missing associations/states, policy
  applicability gaps, partial visual adapters and low exact public plan agreement.
