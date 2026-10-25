# Final best-effort submission evaluation

This report describes the actual final prediction path, not the earlier strict diagnostic.
The pre-final checkpoint is preserved at `checkpoints/pre-final-submission/checkpoint.zip`
in the workspace. No organizer truth or hidden answers were read. References remained
strictly in post-prediction public evaluation. No reference-derived fixes followed that evaluation.

## Full output-producing run

Command: `python3 code/main.py submit --visual-cache runs/visual-cache --run-dir runs/final-submission --output output.csv`

- Requests and output rows: **518**; unique requested IDs, sorted, exact three-column header.
- Predictions: **423 INCOMPLETE, 85 COMPLETE, 10 NOT_APPLICABLE**.
- Evidence-established statuses within recorded scope: **429** (334 INCOMPLETE, 85 COMPLETE, 10 NOT_APPLICABLE).
- Explicitly inferred statuses: **89**, all precautionary INCOMPLETE because completion could not be proved.
- Scoped plan certificates: **235**; uncertified/unfinished coverage: **283**.
- Measured wall time: **63.257112 seconds**; application model calls: **0**.
- Forty-six deletion predictions have no actionable grounded resource and therefore empty steps.
  No findings, record IDs or remediation actions were invented for those rows.
- Full hidden deletion-status, step, field and sequence accuracy: **unavailable**.

Per-case inference bases, intent, certification and exact limitations are in root
`uncertainty_report.json`; complete participant-evidence traces are under
`runs/final-submission/cases/`. Uncertainty is outside the submission CSV schema.
All 186 rows accepted at the latest previous full checkpoint were compared against this output;
see the final validation record for preservation results. Revalidation uses current participant
identities, history, activity, manifest, cached extraction, cutoffs and policy, not trusted old labels.

## One public evaluation of the actual final path

Public predictions: `runs/final-public/predictions.csv`; evidence reports were saved
before reading `dataset/sample_output.csv`. The final path produced all 32 predictions.
This is deterministic best-effort evaluation, not measured end-to-end model-agent accuracy.

| Metric | Measured result |
|---|---:|
| Case-level status accuracy | 27/32 (84.375%) |
| Whole-row exact agreement | 1/32 (3.125%) |
| Structural step precision | 131/132 (99.242%) |
| Structural step recall | 131/193 (67.876%) |
| Positional field accuracy | 704/1351 (52.110%) |
| Exact structural sequence agreement | 1/32 (3.125%) |
| Citation disagreements among matched structures | 4 |
| Ordering disagreements with matching step multisets | 0 |

Separating support from prediction: **26/32** public statuses are established from scoped
evidence and all 26 agree with reference statuses. Six statuses are inferred; one agrees
and five disagree. Fourteen plans pass the scoped certificate; eighteen remain uncertified.
All 32 cases remain in denominators. Exact row agreement includes status, all step fields,
citations and order. Structural precision/recall use multiset matching; field accuracy uses
seven fields at each expected array position, with missing fields counted wrong. Extra
steps affect precision and exact agreement. Detailed evaluation-only disagreements stay
in `runs/final-public/evaluation.json`; they do not become prediction inputs.

## Independent participant-created evaluation cases

These synthetic tests use fictional identifiers and no public reference answers.

| Scenario | Required and observed behavior |
|---|---|
| Independent profile violation plus security record with unknown retention | Established INCOMPLETE; grounded profile finding/remediation/check retained; no invented security action; plan uncertified |
| Request identity has no grounded associated state | Inferred INCOMPLETE with empty steps; no invented finding; cannot become unproved COMPLETE |
| Portuguese/Korean deletion paraphrases, explicit negation and unknown language | Deletion vocabulary recognized; unknown/negated extensions remain uncertain, never automatically non-deletion |
| Correction/export request with explicit preservation | NOT_APPLICABLE with empty steps |
| Citation captured after cutoff or attached to a future check | Rejected by final structural/grounding validator |
| Unsorted serialized requested case IDs | Rejected |

## Failures, improvements and limits

The former all-or-nothing gate suppressed evidence-supported statuses whenever plans had
gaps. A separate explicit contest path now produces every prediction, preserves grounded
steps and records certification separately. It does not weaken the strict investigation gate.
General multilingual intent and preservation-scope recognition recover requests without
sentence-specific/case-specific labels. Existing cached observations are reassessed through
the shared engine; no new retention searches, nested model investigations or architecture
expansion were performed.

Remaining overlapping full-run gap occurrences include 202 security-retention conditions,
100 shared-support-context conditions, 41 grounded resources lacking state proof, seven
visual assessment gaps and one legal-hold condition. These are diagnostic occurrences,
not mutually exclusive case counts. Unknown retention supplies neither a deletion fallback
nor evidence of compliance. The earlier bounded retention and missing-step investigations
are reused; the latter demonstrated no general output-compilation omission. The known
capture-time interpretation and ungrounded-association questions remain unresolved.

Public failures include five wrong precautionary statuses, one extra structural step,
62 missing reference steps and four matched-step citation disagreements. Exact plan agreement
remains low. Scoped certification and passing tests do not prove exhaustive discovery or
contest correctness. Partial plans are intentionally submitted as best effort and explicitly
remain uncertified in the separate report.

Final validation and independent test results are recorded in `evaluation/final_validation.json`.

Final checks passed: 92 independent tests locally and 92 from a clean extracted archive,
CLI import/help from the extraction, all 518 serialized rows matched their validated
per-case evidence reports, and all 186 previously accepted rows remained unchanged.
The ZIP was checked for current source equality, required reports, exclusions and integrity.
