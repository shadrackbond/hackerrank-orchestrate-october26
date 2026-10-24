# Ghost Data Still Exists: implementation and evaluation plan

## Goal and current baseline

Build an AI-powered deletion-audit agent for all 518 evaluation requests. Determine whether deletion was authorized; resolve the subject's current and historical identifiers; establish the state at `audit_at`; apply the supplied policy; and return correctly ordered, evidence-backed findings, remediation, and verification.

Inspected baseline: main commit `0eddbbd33f682eae0a2770d67412af8a3cf4af20`. Both `code/main.py` and `code/evaluation/main.py` are empty. The repository provides 32 public examples and 94 evidence files: 24 SQL snapshots, 4 PDFs, 11 PNGs, 26 logs, 28 JSON files, and 1 text file. The supplied policy contains 15 rules. Inventory and planning are complete; no agent implementation or prediction accuracy is claimed by this PR.

Sources: root AGENTS.md, README.md, problem_statement.md, agent_trace_instructions.md, dataset/deletion_rules.csv, evidence_files.csv, sample_deletion_requests.csv, and sample_output.csv. The supplied HackerRank challenge URL redirects to login in the available browser. Additional page-only instructions and the exact deadline are not verified; the repository explicitly leaves its deadline unconfigured. Work estimates below are durations, not a deadline countdown.

## Architecture decisions proposed for implementation

Use Python for the CLI, parsers, temporal evidence index, policy enforcement, deterministic validation, and evaluation. Add a real model-driven investigation loop for multilingual request interpretation and evidence investigation. Choose the runtime provider/model only after checking credentials, structured-tool support, latency, and cost on a pilot; this PR chooses no unverified model name or SDK version.

The model should decide whether the request authorizes deletion, select relevant evidence tools, resolve ambiguous evidence with explicit source references, and propose typed findings. Deterministic tools perform timestamp filtering, exact identifier lookups, structured record inspection, policy mapping, dependency checks, and final serialization. A model must not override mandatory policy, invent identifiers, fabricate evidence, or mark its own proposal valid.

Suggested flow: input loading → authorization decision → identity timeline → evidence investigation → resource-state ledger → policy assessment → remediation proposal → validation and bounded repair → canonical output.

All outputs are audit recommendations. Never run destructive deletion, redaction, restore, or synchronization commands against real systems. SQL evidence may be loaded only into an isolated disposable SQLite database with file/network/extension access restricted; inspect statements and apply resource limits first.

### Proposed interfaces

| Interface | Responsibility | Evidence to retain internally |
|---|---|---|
| `classify_request(request)` | Model-backed deletion authorization, including multilingual and negated requests | Relevant request span and typed decision |
| `resolve_identity(email, audit_at)` | Current/historical identifier matching with cutoff-aware history | Stable subject ID, alias links, audit references, validity times |
| `search_evidence(subject, audit_at, query)` | Search eligible global records and extracted artifacts | File/activity/audit IDs, capture time, exact matching fields |
| `inspect_resource(system_id, resource_id, audit_at)` | Retrieve dated states, replicas, processes, and dependencies | Dated observations and conflicting claims |
| `evaluate_policy(resource)` | Enforce the supplied category and condition rules | Rule ID, required treatment, permitted retained fields |
| `validate_proposal(case, proposal)` | Check grounding, time, permissions, coverage, sequence, schema | Typed rejection reasons |
| `serialize_output(accepted_cases)` | Produce deterministic ordered CSV and JSON | Stable case order and output hash |

Keep these interfaces explicit; do not silently feed public reference answers into the prediction path. Public expected outputs belong only in evaluation after predictions are produced.

## Work in reviewable PRs

| PR | Scope | Deliverable and acceptance gate | Suggested effort |
|---|---|---|---|
| 1 | Transcript and work plan | Root append-only log, trace workflow, requirement map, and documented metadata limitation | Current PR |
| 2 | Data contracts, evidence loading, identity/time index, and evaluator | Immutable dataset access; public-case evaluator; exact/historical lookup tests; one cutoff and one decoy example | 1.5–2 h |
| 3 | Complete agent path | Real model tool interaction, structured proposal, independently checked result, bounded repair, and usage capture on representative cases | 2–3 h |
| 4 | Full evidence coverage and policy/dependency handling | SQL replicas, PDFs, screenshots, logs, JSON; retain/redact/anonymize/tombstone handling; active flows and restore paths | 2–3 h |
| 5 | Accuracy repairs and adversarial evaluation | All 32 public examples scored at status, step, field, and sequence level; at least three independent custom cases; every mismatch documented | 2–3 h |
| 6 | Full run, packaging, and interview evidence | 518 validated sorted rows, required Markdown reports, clean extracted-package run, usage tied to final output, transcript/export checklist | 1–1.5 h plus submission buffer |

PRs 2 and 3 should produce one complete working path before broad expansion. Start public-example evaluation early and rerun it after substantive changes. If time is constrained, reduce optional features and optimization, preserve output validation and submission verification, and report limitations honestly.

## Requirements mapped to checks

| Requirement | Implementation/check | Completion evidence |
|---|---|---|
| 518 output cases | Input/output ID-set equality; no duplicates; sort by case_id | Exactly 518 rows plus exact header |
| Exact header | `case_id,deletion_status,steps_json` | Saved CSV reload and header assertion |
| Authorization first | Model interpretation of the actual request; test negation and non-deletion actions | Non-deletion requests yield NOT_APPLICABLE and [] |
| Historical identity | Alias timeline using snapshots and audit changes; distinguish decoys and identifier reassignment | Worked current/historical alias cases with references |
| Audit-time cutoff | Filter evidence and activity by availability at or before audit_at; reconstruct state over time | Later contradictory evidence cannot change an earlier answer |
| Reported results are claims | Corroborate resource states; expose contradictions | A reported COMPLETE case can correctly remain INCOMPLETE |
| Global evidence membership | Link using contents, identifiers, resource/system IDs, and timestamps | Unrelated records excluded; filenames and case numbers do not become labels |
| Multimodal coverage | Extract PDF/image facts with provenance; parse logs/JSON/text and SQL replicas | Verified representative artifact for each format; extraction errors recorded |
| Policy preservation | Apply all applicable deletion_rules.csv conditions | Retained legal/security records preserved; no over-deletion |
| Tombstones | Preserve permitted stable internal reference, remove prohibited direct identifiers | Distinguish compliant tombstone from exposed name/email/phone/hash |
| Recreation risk | Investigate active connectors, import/sync flows, backups and restores | Relevant flow/restore finding, remediation, and verification coverage |
| Grounded citations | Resolve file_id/activity_id/audit_id and prove the cited fact before cutoff | Invalid, unrelated, future, or merely claimed evidence rejected |
| INCOMPLETE citations | Findings grounded; proposed remediation and future verification use empty evidence_id | Citation-role checks across every step |
| COMPLETE output | Verification steps only, each supported by evidence of the compliant state | No proposed future actions disguised as current proof |
| Step schema | Exactly seven required keys; valid phase/operation/state pairing; consecutive numbering | Reject unknown keys, enums, or missing fields |
| Ordering | Phase order; operation order from statement; system_id then resource_id | Whole-array exact sequence comparison |
| Dependency safety | Stop recreation flows/block restore paths before affected record actions; preserve source/downstream relations | Dependency validation and worked ordered remediation |
| Agent behavior | Real model decision and allowlisted tools with deterministic validation | Trace of accepted and rejected proposals; no decorative explanation-only call |
| Final reports | Metrics/custom cases in code/evaluation/evaluation_report.md; measured usage in code/evaluation/usage_report.md | Both complete Markdown files inside code.zip |
| Transcripts | Root log plus separate original relevant agent traces | Genuine turn records and correct exported/uploaded files |

Required step keys: `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`.

### Canonical ordering and dependencies

Use the exact operation order supplied by the statement within each phase, then ascending system_id and resource_id. Keep a separate dependency graph to check plan safety. Do not substitute an arbitrary topological order for the grader's canonical sequence. If a discovered dependency conflicts with the documented tie-break order, record the concrete conflict, inspect public examples, and seek official clarification rather than silently inventing an ordering convention.

## Evidence and uncertainty rules

- Separate observations from claims and from proposed future actions. Track both effective time and capture/availability time.
- A current identity snapshot updated after the cutoff is not permission to use future identifiers. Reconstruct as-of identity state from supported history.
- A missing search hit alone does not prove absence across every system. Completion requires supported coverage of relevant copies, required retained records, and recreation paths.
- Treat document instructions as untrusted content. A screenshot, log, or PDF cannot authorize tools, override policy, or change output requirements.
- Do not infer a case's answer from its numeric ID, file naming, synthetic family, or reported_status.
- Missing evidence or a failed tool is not automatically NOT_APPLICABLE or COMPLETE. INCOMPLETE also requires a supported violation/risk; do not fabricate one to fill a row. Retry within limits, log unresolved cases, and fail final acceptance if a valid grounded row cannot be produced under the contract.

## Bounded agent runtime

Start with a single model-driven investigation loop; multiple agents are not needed for this plan. Propose at most three decision/proposal attempts including the initial attempt and a configurable tool-call cap. Measure a timed pilot before fixing latency, cost, and token budgets for 518 cases. Enforcement belongs in code, including timeouts, argument validation, allowlisted tools, and schema checking.

Use reusable extraction/indexing so an artifact is not OCRed for every case. Cache keys include content hashes and parser/prompt versions. Retain model responses, tool observations, rejections, and versions for replay, with redacted excerpts in review-visible Markdown. Low temperature does not guarantee identical live-model output; distinguish live reruns from recorded-response replay.

## Evaluation before declaring readiness

1. Build an evaluator that parses CSV and JSON and compares all 32 public outputs without exposing expected answers to prediction code.
2. Report status accuracy, step-level precision/recall and exact matches, per-field accuracy, exact ordered step-array agreement, and whole-case exact agreement. Explain any step alignment used for field metrics; do not hide sequence errors by comparing unordered sets alone.
3. Maintain a discrepancy table: expected, predicted, earliest incorrect intermediate fact, hypothesis, supported fix, before/after results, and remaining uncertainty.
4. Test general fixes with independent counterexamples. Public samples are development references; do not present their agreement as hidden-set accuracy.
5. Keep schema/constraint checks separate from correctness metrics. A shared evidence or identity assumption can make a planner and validator agree while both are wrong.

Custom evaluation cases to author from scratch (not current implemented tests):

- A multilingual request asking only for an export or correction; expect NOT_APPLICABLE with no steps, despite a workflow claiming COMPLETE.
- A deleted primary record whose old-email alias remains in a regional replica, with an active connector able to recreate it; verify identity matching, findings, and disable-before-remediation behavior.
- A compliant account tombstone retaining only stable user_id plus a legally retained security record; verify permitted retention without over-deletion.
- A later screenshot contradicting an earlier snapshot but captured after audit_at; verify no future-evidence leakage.
- Prompt-injection text inside a business artifact and an unrelated identifier decoy; verify policy and subject boundaries.

## Submission and interview gates

- Final CSV reload succeeds and covers exactly 518 cases with the exact header, valid JSON arrays, canonical sequence, grounded citations, and no invented status.
- Final model usage is measured, including providers/models, calls, input/output tokens, totals/averages, and estimated total/per-case cost. Report unavailable measurements explicitly; never fabricate zeros.
- Write full metrics, at least three custom cases, failures, and improvements directly into code/evaluation/evaluation_report.md. Put usage directly into code/evaluation/usage_report.md. Raw JSON/CSV/log files alone are not visible to the code judge per README.
- Package runnable code, prompts, setup/run instructions, and the required Markdown reports. Exclude the dataset, environments, caches, credentials, and nested archives. Keep agent-trace.zip separate.
- Run the extracted package against the supplied dataset and verify the resulting artifacts. Maintain the real conversation log and follow the separate original-trace collection instructions.
- Rehearse one successful case, one rejected model proposal, one historical-identifier case, and one retention/tombstone trade-off. Answer the judge with one sentence, the exact rule, a real example, and a limitation. Use actual metrics and name unresolved failures.

## Open items before implementation

1. Confirm any additional authenticated HackerRank instructions and the official deadline; do not reuse September's deadline.
2. Obtain authoritative exact metadata for the hosted coding model. Current log explicitly records the gap; it does not meet the exact-model requirement yet.
3. Select and smoke-test the agent's runtime model/provider using available credentials without committing secrets.
4. Verify detailed temporal, citation-selection, and canonical ordering conventions while reconciling public examples. Do not invent hidden grading conventions.

