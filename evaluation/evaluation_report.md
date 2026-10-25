# Evaluation report

This is a deterministic diagnostic evaluation, **not end-to-end agent accuracy**.
No new model investigations or extraction calls were made in the delivery pass. Public references
were opened only after saving predictions. No organizer-only data was inspected or used.
The two allowed repair/evaluation cycles are saved under `runs/delivery-public-cycle1/` and
`runs/delivery-public-final/`; their metrics are identical. These runtime directories are workspace
artifacts and deliberately excluded from the source archive.

## Public sample results

| Metric | Observed result |
|---|---:|
| Cases attempted | 32 |
| Cases resolved | 15 |
| Cases unresolved (included in denominator) | 17 |
| Status accuracy | 15/32 (46.875%) |
| Whole-case exact agreement | 1/32 (3.125%) |
| Step precision | 70/70 (100.000%) |
| Step recall | 70/193 (36.269%) |
| Field accuracy (positional; all expected slots) | 388/1351 (28.719%) |
| Exact structural sequence agreement | 1/32 (3.125%) |
| Citation mismatches among matched steps | 0 |
| Ordering mismatches with matching step multisets | 0 |

All 32 examples are in every case-level denominator. Missing predictions are wrong, not excluded.
Steps are multiset-matched by phase, system, resource, operation and state; citations are evaluated
separately. Field accuracy compares seven fields at each expected array position; extra steps
are penalized by precision and exact agreement rather than extra field slots. Exact whole-case
agreement includes status, all fields, citations and array order. Structural sequence agreement
includes the ordered structural step fields; it excludes citations and is reported separately.

Before this pass: 14/32 statuses, 1/32 whole cases, 67/193 reference steps. After: 15/32,
1/32, 70/193. One additional case resolves after a structurally grounded contact-index
classification. It still lacks a separately grounded account verification, so it is not a complete
reference match. No previously resolved output changed: regressions = [].
Among the 15 resolved cases, 24 reference steps are missing and 0 extra steps are present.
Fourteen resolved cases have incomplete reference step sets. Eleven public retention blockers remain.
Status correctness is separate from plan completeness; 100% step precision does not demonstrate coverage.

## Failures fixed and validation boundary

* A visual support reference and shared order context previously created SUPPORT_MESSAGE automatically.
  Semantic proposals now need explicit, resource-bound TYPE evidence; ownership is separate for attachments.
  The visual UI adapter also requires conversation-record structure, not merely prose mentioning a conversation.
* Correlated contact-index queries are SECONDARY_IDENTIFIER observations; support origin is not a category.
  Replica provenance remains explicit when a manifest-grounded canonical support service is used.
* Search hits use their own resource IDs, not a wrapper/query ID. A query is retained as retrieval provenance,
  not ownership proof for an unrelated hit.
* Omitted tombstone fields and unrecognized process flags no longer establish redaction/disabled/blocked states.
  A stable tombstone reference need not have a particular spelling or prefix.
* The independent delivery gate checks exact fields, step numbering, ordering, complete per-resource step sets,
  permitted operations/states, eligible state citations, empty future citations, status and certified scoped proof.
  It blocks unresolved reports and sample subsets from submission publication.

There is one shared index/policy/compilation implementation for model tools and deterministic diagnostics.
Model assistance can interpret quoted evidence, but cannot create identities, policy terms, states or citations.
Scoped COMPLETE proof does not require an unrelated full-system inventory. Missing matches never imply absence.
Category collections/table schemas, event types, explicit field labels and resource relationships select adapters.
No case-ID, evidence-ID, filename, reference-label or numeric-suffix prediction overrides were found or added.
The final conversation structure guard was independently checked to leave the entire normalized participant
observation list unchanged (SHA-256 f9ca0a5bda66140f782ea8d9890437f41151f8ffc6853b6deca2b1662fdbc1d9).
There was no third public prediction/evaluation cycle.

## Full participant-request diagnostic

All **518** requests were attempted in **52.464495 seconds**;
indexing took 0.311178 seconds. **250** accepted diagnostic rows
(166 INCOMPLETE, 83 COMPLETE,
1 NOT_APPLICABLE); **268 unresolved**.
No hidden-reference accuracy was computed. No full-dataset model inference was launched.
The run used 2835 normalized observations from 94 manifest sources;
86 sources have supported link-search adapters and eight have partial visual assessment.
No unknown case was assigned a fabricated status after exhaustion or missing proof.

`runs/delivery-full/supported_partial.csv` contains 250 accepted rows and is **not a submission**.
`runs/delivery-full/unresolved.json` records every unresolved request with exact causes and per-case
report paths. `runs/delivery-full/cases/` preserves 518 reports, tool interactions, identity links,
source locations, cutoff checks, policy facts, classifications and remaining coverage gaps.
`runs/delivery-full/summary.json` records measured time and zero application model usage.
The root `output.csv` was withheld by the delivery gate; no valid final submission exists.
The archive contains runnable sources, not the dataset, caches or these diagnostic traces.

Blocking cause counts below overlap, so they must not be summed as a count of cases:

| Cause | Case/message occurrences |
|---|---:|
| No identity-linked resource state | 42 |
| Retention period unproved | 192 |
| Deletion authorization ambiguous; requires model judgment | 30 |
| Identity and evidence not searched | 30 |
| Activity links resource without state proof | 32 |
| Grounded resource lacks state proof | 40 |
| Shared-context condition unproved | 28 |
| Policy treatment lacks violation-state proof | 1 |
| Resource state unproved | 1 |
| Visual resource assessment unresolved | 7 |
| Active legal hold unproved | 1 |
| Identity hit lacks parsed resource observation | 2 |

All 192 retention diagnostic failures specifically lack a supported record-scoped retention_until or
retained_until proof in the eligible normalized observations. This is a statement about the implemented
proof path, not a claim that all possible business evidence lacks a fact: duration-based proof is not
implemented. No retention duration or record creation time was inferred. The underlying per-case ledger
identifies the actually eligible/searchable/inspected sources; uninspected, partial or failed sources remain
explicit. A model cannot safely infer absent retention terms, anonymous record identity links, or state.
The other blockers include authorization requiring judgment, historical links, visual type/ownership,
shared context, and missing resource state. Some categories and conditional policy combinations remain
unsupported; multi-rule condition resolution beyond the implemented supplied conditions is unresolved.
The full-run results are not an exhaustive-coverage certificate for the 250 accepted rows.

## Independent regression cases

71 independent deterministic tests pass; scripted proposals are not labelled as real model behavior.
These cases use synthetic participant-style fixtures, not reference answer labels:

| Test scenario | Required outcome |
|---|---|
| Access/export request without deletion authorization | NOT_APPLICABLE with an empty step list |
| Historical email and similar-address decoy | Only the exact subject and grounded resource are associated |
| Record observed before cutoff but artifact captured later | Excluded from retrieval, policy and citation |
| Anonymized current record with earlier eligible resource link | Historical association preserved without restoring identifiers |
| Unrelated anonymous record | Remains unassociated |
| Explicit relationship across JSON and log evidence | Follow only grounded directed resource IDs, with provenance |
| Relationship learned only after cutoff | Excluded |
| Financial retention register without legal semantics | Contextual evidence, not LEGAL_HOLD_RECORD |
| Explicit active legal hold and ordinary financial retention date | Hold accepted only with supplied legal semantics/activity |
| Active, expired and insufficient retention proof | Active retain; expired/insufficient remain unresolved without invented fallback |
| Renamed fixture files and identifiers | Equivalent decisions and appropriately renamed citations |
| Exporter provenance differs from resource service | Preserve origin; normalize only the supported owner/file/download schema |
| Missing resource identity | Remains unresolved |
| Search wrapper with unrelated hit | Keep actual document ID; query does not establish unrelated ownership |
| Support contact-index lookup | Secondary identifier, not conversation |
| Support reference plus shared-order prose | No message category from context alone |
| Explicit source-quoted conversation type/context | Model tool assessment feeds the same policy compiler |
| Unknown process flags or omitted tombstone fields | No inferred compliant state |
| Missing steps, ineligible finding citation, future citation on INCOMPLETE | Delivery validator rejects |
| Sample-only run or unresolved decision | Cannot publish final 518-row output |
| Unapproved tools, arbitrary paths and reference-answer access | Rejected by the case tool boundary |
| Invalid proposal followed by correction | Scripted rejection and acceptance stay within proposal limits |

The source archive is also extracted to a clean temporary directory and its independent tests run there.
CLI import/help, archive integrity and exact report paths are checked. This does not imply the live adapter
was rerun on the final revision; previous genuine native traces remain available in the workspace.

## Evaluation-only disagreements

Reference details in this section do not feed prediction. Earliest mismatches from saved comparisons:

* unresolved: 17 cases. First recorded intermediate discrepancy: `case_01` — No identity-linked resource state.
* step_set: 14 cases. First recorded intermediate discrepancy: `case_03` — Missing identity-linked observation for analytics_9406.

The eight previously recorded temporal discrepancies remain excluded: an earlier event timestamp inside
a later-captured artifact does not make it eligible. This is a possible interpretation/evaluation issue,
not a claim that the dataset is defective. No later artifact was admitted to improve reference agreement.

| Public case | Reference resource/operation excluded by capture cutoff |
|---|---|
| case_09 | account_service/account_3960: VERIFY_RECORD_ABSENT |
| case_09 | security_service/audit_record_4902: VERIFY_RECORD_PRESENT |
| case_23 | security_service/audit_record_4128: VERIFY_RECORD_PRESENT |
| case_24 | security_service/audit_record_7095: VERIFY_RECORD_PRESENT |
| case_26 | account_service/account_5684: VERIFY_RECORD_ABSENT |
| case_27 | account_service/account_3866: VERIFY_RECORD_ABSENT |
| case_29 | security_service/audit_record_3954: VERIFY_RECORD_PRESENT |
| case_30 | security_service/audit_record_1707: VERIFY_RECORD_PRESENT |

Remaining missing steps among resolved cases (evaluation only):

| Case | Missing step count |
|---|---:|
| case_03 | 1 |
| case_08 | 1 |
| case_09 | 2 |
| case_10 | 1 |
| case_20 | 2 |
| case_21 | 2 |
| case_23 | 2 |
| case_24 | 1 |
| case_25 | 2 |
| case_26 | 2 |
| case_27 | 2 |
| case_28 | 2 |
| case_29 | 2 |
| case_30 | 2 |

## Unresolved full-run inventory

This appendix is copied from saved diagnostic causes, not predictions rerun during evaluation.
For exact evidence, source locations and inspected-source scope, use the corresponding numbered
`runs/delivery-full/cases/` report; full JSON retains duplicate summary messages omitted here.

| Case | Exact unresolved causes |
|---|---|
| case_103 | No identity-linked resource state; Retention period unproved: audit_record_9522 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_104 | Retention period unproved: audit_record_6230 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_105 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_106 | Retention period unproved: audit_record_8723 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_107 | No identity-linked resource state; Retention period unproved: audit_record_7572 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_108 | No identity-linked resource state; Retention period unproved: audit_record_1469 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_109 | Retention period unproved: audit_record_2718 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_110 | Retention period unproved: audit_record_9268 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_111 | No identity-linked resource state; Retention period unproved: audit_record_8933 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_112 | Retention period unproved: audit_record_4082 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_114 | Activity links resource without state proof: support_3786; Grounded resource lacks state proof: support_platform/support_3786 |
| case_118 | Activity links resource without state proof: support_036; Grounded resource lacks state proof: support_platform/support_036 |
| case_119 | Activity links resource without state proof: support_9309; Grounded resource lacks state proof: support_platform/support_9309 |
| case_132 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_133 | Retention period unproved: audit_record_3130 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_134 | Retention period unproved: audit_record_4064 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_4410 |
| case_135 | Retention period unproved: audit_record_5140 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_136 | Retention period unproved: audit_record_7931 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_4442 |
| case_137 | Retention period unproved: audit_record_6779 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_138 | Retention period unproved: audit_record_122 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_2716 |
| case_139 | Retention period unproved: audit_record_7689 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_140 | Retention period unproved: audit_record_8086 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_5323 |
| case_141 | Retention period unproved: audit_record_5497 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_142 | Retention period unproved: audit_record_280 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_771 |
| case_144 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_153 | Retention period unproved: audit_record_5652 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_154 | Retention period unproved: audit_record_2580 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_155 | Retention period unproved: audit_record_4199 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_156 | Retention period unproved: audit_record_5890 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_157 | No identity-linked resource state; Retention period unproved: audit_record_8821 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_158 | Retention period unproved: audit_record_9665 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_159 | Retention period unproved: audit_record_8742 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_160 | Retention period unproved: audit_record_9882 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_161 | Retention period unproved: audit_record_8002 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_162 | No identity-linked resource state; Retention period unproved: audit_record_6362 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_165 | Activity links resource without state proof: support_3586; Grounded resource lacks state proof: support_platform/support_3586 |
| case_166 | Activity links resource without state proof: support_3155; Grounded resource lacks state proof: support_platform/support_3155 |
| case_171 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_172 | Activity links resource without state proof: support_2322; Grounded resource lacks state proof: support_platform/support_2322 |
| case_183 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_198 | Activity links resource without state proof: support_6131; Grounded resource lacks state proof: support_platform/support_6131 |
| case_201 | Activity links resource without state proof: support_2863; Grounded resource lacks state proof: support_platform/support_2863 |
| case_203 | Retention period unproved: audit_record_1159 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_204 | Retention period unproved: audit_record_2736 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_205 | Retention period unproved: audit_record_5023 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_206 | No identity-linked resource state; Retention period unproved: audit_record_9878 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_207 | Retention period unproved: audit_record_3578 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_208 | Retention period unproved: audit_record_2697 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_209 | Retention period unproved: audit_record_8189 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_210 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_211 | Retention period unproved: audit_record_7804 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_212 | Retention period unproved: audit_record_3261 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_222 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_233 | Activity links resource without state proof: support_9670; Grounded resource lacks state proof: support_platform/support_9670 |
| case_234 | Activity links resource without state proof: support_1254; Grounded resource lacks state proof: support_platform/support_1254 |
| case_235 | Activity links resource without state proof: support_9391; Grounded resource lacks state proof: support_platform/support_9391 |
| case_249 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_253 | No identity-linked resource state; Retention period unproved: audit_record_2927 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_254 | Retention period unproved: audit_record_9256 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_255 | Retention period unproved: audit_record_2513 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_256 | Retention period unproved: audit_record_2453 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_257 | No identity-linked resource state; Retention period unproved: audit_record_7193 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_258 | Retention period unproved: audit_record_9890 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_259 | Retention period unproved: audit_record_1421 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_260 | No identity-linked resource state; Retention period unproved: audit_record_1876 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_261 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_262 | Retention period unproved: audit_record_4812 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_263 | Retention period unproved: audit_record_6863 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_2498 |
| case_264 | Policy treatment lacks violation-state proof: backup_3250; Resource state unproved: backup_3250; Retention period unproved: audit_record_6711 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_265 | Retention period unproved: audit_record_6378 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_266 | Retention period unproved: audit_record_1857 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_267 | Retention period unproved: audit_record_6621 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_268 | Retention period unproved: audit_record_4636 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_269 | Retention period unproved: audit_record_4534 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_8301 |
| case_270 | Retention period unproved: audit_record_5206 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_7707 |
| case_271 | Retention period unproved: audit_record_2546 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_272 | Retention period unproved: audit_record_4646 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_287 | Activity links resource without state proof: support_7432; Grounded resource lacks state proof: support_platform/support_7432 |
| case_288 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_292 | Activity links resource without state proof: support_1526; Grounded resource lacks state proof: support_platform/support_1526 |
| case_300 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_303 | Retention period unproved: audit_record_7923 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_304 | No identity-linked resource state; Retention period unproved: audit_record_4759 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_305 | Retention period unproved: audit_record_507 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_306 | Retention period unproved: audit_record_9051 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_307 | Retention period unproved: audit_record_5129 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_308 | Retention period unproved: audit_record_3221 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_309 | No identity-linked resource state; Retention period unproved: audit_record_1945 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_310 | Retention period unproved: audit_record_5640 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_311 | Retention period unproved: audit_record_6245 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_312 | Retention period unproved: audit_record_6559 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_324 | Activity links resource without state proof: support_7249; Grounded resource lacks state proof: support_platform/support_7249 |
| case_326 | Activity links resource without state proof: support_305; Grounded resource lacks state proof: support_platform/support_305 |
| case_327 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_328 | Activity links resource without state proof: support_7926; Grounded resource lacks state proof: support_platform/support_7926 |
| case_33 | Grounded resource lacks state proof: export_service/export_1260; Grounded resource lacks state proof: export_service/export_1842; No identity-linked resource state; Visual resource assessment unresolved: evidence_18; Visual resource assessment unresolved: evidence_23 |
| case_330 | Activity links resource without state proof: support_4851; Grounded resource lacks state proof: support_platform/support_4851 |
| case_331 | Activity links resource without state proof: support_1403; Grounded resource lacks state proof: support_platform/support_1403 |
| case_339 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_34 | Retention period unproved: audit_record_3753 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_353 | Retention period unproved: audit_record_5773 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_354 | No identity-linked resource state; Retention period unproved: audit_record_9286 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_355 | Retention period unproved: audit_record_1151 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_356 | Retention period unproved: audit_record_771 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_357 | Retention period unproved: audit_record_350 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_358 | Retention period unproved: audit_record_1395 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_359 | Retention period unproved: audit_record_2641 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_36 | Retention period unproved: audit_record_2966 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_360 | Retention period unproved: audit_record_2605 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_361 | Retention period unproved: audit_record_7587 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_362 | No identity-linked resource state; Retention period unproved: audit_record_8638 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_363 | Retention period unproved: audit_record_9777 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_364 | Retention period unproved: audit_record_7136 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_365 | Retention period unproved: audit_record_5798 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_3294 |
| case_366 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_367 | Retention period unproved: audit_record_9082 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_4691 |
| case_368 | Retention period unproved: audit_record_3738 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_369 | Retention period unproved: audit_record_337 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_37 | Retention period unproved: audit_record_2019 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_370 | Retention period unproved: audit_record_9696 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_6949 |
| case_371 | Retention period unproved: audit_record_689 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_372 | Retention period unproved: audit_record_5705 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_376 | Activity links resource without state proof: support_475; Grounded resource lacks state proof: support_platform/support_475 |
| case_378 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_38 | Retention period unproved: audit_record_633 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_382 | Activity links resource without state proof: support_5071; Grounded resource lacks state proof: support_platform/support_5071 |
| case_383 | Retention period unproved: audit_record_989 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_384 | Retention period unproved: audit_record_2342 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_385 | Retention period unproved: audit_record_3007 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_386 | Retention period unproved: audit_record_8245 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_1693 |
| case_387 | Retention period unproved: audit_record_2536 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_388 | Retention period unproved: audit_record_8683 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_8378 |
| case_389 | Retention period unproved: audit_record_9005 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_39 | Grounded resource lacks state proof: integration_service/data_flow_1121; No identity-linked resource state; Visual resource assessment unresolved: evidence_14 |
| case_390 | Active legal hold unproved: legal_hold_8049 — A retain-until date or ordinary retention reason does not establish an active legal hold; Retention period unproved: audit_record_101 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_5720 |
| case_391 | Retention period unproved: audit_record_5007 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_392 | Retention period unproved: audit_record_7510 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_40 | Retention period unproved: audit_record_8349 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_4887 |
| case_403 | No identity-linked resource state; Retention period unproved: audit_record_4733 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_404 | Retention period unproved: audit_record_6099 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_405 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_406 | Retention period unproved: audit_record_5455 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_407 | Retention period unproved: audit_record_6152 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_408 | No identity-linked resource state; Retention period unproved: audit_record_4216 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_409 | No identity-linked resource state; Retention period unproved: audit_record_2559 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_41 | Retention period unproved: audit_record_7814 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_2667 |
| case_410 | Retention period unproved: audit_record_896 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_411 | No identity-linked resource state; Retention period unproved: audit_record_4330 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_412 | No identity-linked resource state; Retention period unproved: audit_record_5637 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_413 | Retention period unproved: audit_record_9099 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_414 | Retention period unproved: audit_record_3768 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_415 | Retention period unproved: audit_record_6154 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_416 | Retention period unproved: audit_record_8832 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_417 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_418 | Retention period unproved: audit_record_5493 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_9464 |
| case_419 | Retention period unproved: audit_record_7716 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_42 | Retention period unproved: audit_record_6760 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_7769 |
| case_420 | Retention period unproved: audit_record_9687 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_421 | Retention period unproved: audit_record_1256 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_422 | Retention period unproved: audit_record_4218 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_433 | Retention period unproved: audit_record_6665 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_434 | Retention period unproved: audit_record_4043 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_3364 |
| case_435 | Retention period unproved: audit_record_9695 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_436 | Retention period unproved: audit_record_2748 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_165 |
| case_437 | Retention period unproved: audit_record_6846 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_438 | Retention period unproved: audit_record_1366 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_6688 |
| case_439 | Retention period unproved: audit_record_1149 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_44 | Activity links resource without state proof: support_1066; Grounded resource lacks state proof: support_platform/support_1066 |
| case_440 | Retention period unproved: audit_record_5488 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_441 | Retention period unproved: audit_record_7313 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_442 | Retention period unproved: audit_record_4839 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_4123 |
| case_444 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_45 | Visual resource assessment unresolved: evidence_37 |
| case_453 | Retention period unproved: audit_record_3600 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_454 | Retention period unproved: audit_record_2775 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_455 | Retention period unproved: audit_record_2788 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_456 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_457 | No identity-linked resource state; Retention period unproved: audit_record_1171 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_458 | No identity-linked resource state; Retention period unproved: audit_record_6750 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_459 | Retention period unproved: audit_record_6171 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_46 | Grounded resource lacks state proof: identity_service/tombstone_17 |
| case_460 | Retention period unproved: audit_record_1369 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_461 | Retention period unproved: audit_record_3883 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_462 | No identity-linked resource state; Retention period unproved: audit_record_641 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_47 | Activity links resource without state proof: support_5742; Grounded resource lacks state proof: support_platform/support_5742 |
| case_473 | Retention period unproved: audit_record_519 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_474 | Retention period unproved: audit_record_712 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_475 | Retention period unproved: audit_record_5667 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_476 | Retention period unproved: audit_record_4197 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_477 | Retention period unproved: audit_record_6405 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_478 | Retention period unproved: audit_record_8754 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_479 | No identity-linked resource state; Retention period unproved: audit_record_5745 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_480 | Retention period unproved: audit_record_7742 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_481 | Retention period unproved: audit_record_9025 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_482 | Retention period unproved: audit_record_2180 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_483 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_484 | Activity links resource without state proof: support_7973; Grounded resource lacks state proof: support_platform/support_7973; Identity hit lacks parsed resource observation: evidence_64; No identity-linked resource state |
| case_487 | Activity links resource without state proof: support_5361; Grounded resource lacks state proof: support_platform/support_5361 |
| case_490 | Activity links resource without state proof: support_4247; Grounded resource lacks state proof: support_platform/support_4247 |
| case_492 | Activity links resource without state proof: support_6737; Grounded resource lacks state proof: support_platform/support_6737 |
| case_495 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_503 | No identity-linked resource state; Retention period unproved: audit_record_5454 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_504 | Retention period unproved: audit_record_3733 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_505 | Retention period unproved: audit_record_3441 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_506 | No identity-linked resource state; Retention period unproved: audit_record_1361 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_507 | Retention period unproved: audit_record_7627 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_508 | Retention period unproved: audit_record_8154 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_509 | Retention period unproved: audit_record_2323 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_51 | Activity links resource without state proof: support_1097; Grounded resource lacks state proof: support_platform/support_1097 |
| case_510 | Retention period unproved: audit_record_4266 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_511 | Retention period unproved: audit_record_4883 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_512 | No identity-linked resource state; Retention period unproved: audit_record_4219 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_513 | Retention period unproved: audit_record_2044 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_514 | Retention period unproved: audit_record_1967 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_3982 |
| case_515 | Retention period unproved: audit_record_7062 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_516 | Retention period unproved: audit_record_3777 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_517 | Retention period unproved: audit_record_946 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_518 | Retention period unproved: audit_record_5572 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_519 | Retention period unproved: audit_record_4027 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_52 | Grounded resource lacks state proof: export_service/export_1260; No identity-linked resource state; Visual resource assessment unresolved: evidence_23 |
| case_520 | Retention period unproved: audit_record_9504 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_9251 |
| case_521 | Retention period unproved: audit_record_3567 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_522 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_53 | Shared-context condition unproved: support_1034 |
| case_533 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_534 | No identity-linked resource state |
| case_535 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_536 | No identity-linked resource state |
| case_537 | No identity-linked resource state |
| case_538 | No identity-linked resource state |
| case_539 | No identity-linked resource state |
| case_54 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_540 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_541 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_543 | Retention period unproved: audit_record_6244 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_544 | Retention period unproved: audit_record_1037 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_545 | Retention period unproved: audit_record_5041 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_546 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_547 | Retention period unproved: audit_record_7352 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_548 | Retention period unproved: audit_record_6970 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_549 | Retention period unproved: audit_record_1491 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_55 | Grounded resource lacks state proof: backup_service/backup_9287; No identity-linked resource state; Visual resource assessment unresolved: evidence_32 |
| case_550 | Retention period unproved: audit_record_3831 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_56 | Retention period unproved: audit_record_4078 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_57 | Retention period unproved: audit_record_7219 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_58 | No identity-linked resource state; Retention period unproved: audit_record_8465 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_59 | No identity-linked resource state; Retention period unproved: audit_record_962 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_60 | No identity-linked resource state; Retention period unproved: audit_record_629 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_61 | Grounded resource lacks state proof: object_storage/object_19; No identity-linked resource state |
| case_62 | Retention period unproved: audit_record_4889 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_63 | Grounded resource lacks state proof: marketing_platform/marketing_001; No identity-linked resource state; Visual resource assessment unresolved: evidence_60 |
| case_66 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
| case_76 | Activity links resource without state proof: support_9746; Grounded resource lacks state proof: support_platform/support_9746; Identity hit lacks parsed resource observation: evidence_91; No identity-linked resource state |
| case_77 | Activity links resource without state proof: support_008; Grounded resource lacks state proof: support_platform/support_008 |
| case_78 | Activity links resource without state proof: support_9652; Grounded resource lacks state proof: support_platform/support_9652 |
| case_81 | Activity links resource without state proof: support_5953; Grounded resource lacks state proof: support_platform/support_5953 |
| case_82 | Activity links resource without state proof: support_9166; Grounded resource lacks state proof: support_platform/support_9166 |
| case_83 | Retention period unproved: audit_record_2636 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_84 | Retention period unproved: audit_record_3787 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_85 | Retention period unproved: audit_record_8094 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_86 | Retention period unproved: audit_record_5580 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_87 | Retention period unproved: audit_record_4474 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_88 | Retention period unproved: audit_record_3825 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_2967 |
| case_89 | Retention period unproved: audit_record_2539 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_90 | Retention period unproved: audit_record_9355 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_7460 |
| case_91 | Retention period unproved: audit_record_8304 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented; Shared-context condition unproved: support_266 |
| case_92 | Retention period unproved: audit_record_5625 — Missing explicit record-scoped retention_until or retained_until deadline; duration-based proof is not implemented |
| case_93 | Deletion authorization ambiguous; requires model judgment; Identity and evidence not searched |
