# Ghost Data Still Exists

Python 3.11+ deletion-audit prototype with a shared evidence index, bounded model tools,
deterministic policy assessment, and fail-closed delivery checks.

**Delivery state:** all 518 requests have been attempted in a cached deterministic diagnostic.
250 have supported diagnostic rows; 268 remain unresolved. No submission `output.csv` has
been generated. Public diagnostics resolve 15/32 cases, with 1/32 whole-case exact matches.
These are diagnostic results, not end-to-end agent accuracy or proof of exhaustive plans.
See `evaluation/evaluation_report.md` and `evaluation/usage_report.md`.

## Setup

Run from the repository root with participant files in `dataset/`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Fresh visual extraction additionally needs `pdftotext`, `pdftoppm`, the Tesseract shared
library and English language data (on Debian/Ubuntu: `poppler-utils libtesseract5 tesseract-ocr-eng`).
The existing validated content-hash cache can be reused without extracting again.
The source archive excludes caches and the dataset; place the supplied dataset beside `code/`.

## Deterministic processing

Prepare a fresh cache only when needed; this command uses local tools and makes no model calls:

```bash
python3 code/main.py extract --visual-cache runs/visual-cache
```

Use a new output directory for each run:

```bash
python3 code/main.py diagnostic --samples --visual-cache runs/visual-cache --run-dir runs/public-review
python3 code/evaluation/public_eval.py --reference dataset/sample_output.csv --predictions runs/public-review/predictions.csv --investigations runs/public-review/investigations.json --report runs/public-review/evaluation.json
python3 code/main.py diagnostic --visual-cache runs/visual-cache --run-dir runs/full-review --publish-output output.csv
```

The diagnostic command exits **2 when any case remains unresolved**; this is an expected,
recorded incomplete outcome, not a completed submission. It never starts extraction or inference.
Outputs include `summary.json`, `unresolved.json` with precise per-case causes,
`cases/NNNN.json` with requests, identity, facts, source locations, coverage and tool traces,
and `supported_partial.csv` containing only accepted rows. Public runs also save evaluator inputs.
Classification and plan completeness are separate in case reports. Missing facts never receive
an invented output status. The publication option writes root `output.csv` only for a full
518-case run with every request accepted and all evidence/schema checks passed.
It refuses to replace an existing output. Partial CSV files are **not** submission outputs.

Diagnostics use explicit intent heuristics to exercise the same tools and policy engine;
ambiguous requests remain unresolved. Default diagnostic limits are 128 tool calls,
3 proposal attempts, 10 seconds per tool and 30 seconds per case. The per-tool bound is
checked after return; SQL has its own progress timeout. No diagnostic model tokens are spent.

## Bounded model investigation

The existing live adapter requires an installed and authenticated Codex CLI. It has been
used successfully through an existing ChatGPT login with `gpt-6-sol`; model availability
and remaining quota are not guaranteed. No direct API credentials or provider switch are assumed.
The process-group timeout currently requires Linux or macOS.

```bash
python3 code/main.py --samples --case CASE_ID --model AVAILABLE_MODEL --visual-cache runs/visual-cache --run-dir runs/live-review --tool-calls 10 --proposal-attempts 3 --tool-seconds 10 --case-seconds 180
```

Replace `CASE_ID` and `AVAILABLE_MODEL` explicitly. Do not launch this command for every
request automatically. Review the usage projection in `evaluation/usage_report.md` first.
The child uses an empty working directory, ignores user configuration, and disables shell,
patching, apps, web and multi-agent tools. Only case-scoped MCP reads and structured proposals
are exposed; this tool boundary is not an OS-level filesystem isolation guarantee.
Defaults bound each investigation to 10 tool calls, 3 shared semantic/final proposal attempts,
10 seconds per tool and 180 seconds overall. There is no hard input-token ceiling in this adapter.
Timeouts, rejection and exhaustion preserve unresolved reports rather than fabricating rows.

Prompts are in `code/ghost_audit/runtime.py` (`PROMPT`, `CHILD_INSTRUCTIONS`), semantic tool
schemas in `server.py`, and extraction prompts in `extraction.py`. Native `model_events.jsonl`,
`runtime_stderr.txt`, `model_prompt.txt`, `usage.json` and `investigation.json` are saved in the
selected run directory. The two earlier semantic investigations are preserved in the workspace;
this delivery pass made no new model calls.

## Evidence and policy boundary

All prediction inputs come from participant-facing identities, history, activity, rules and
manifest-listed evidence. `sample_output.csv` is opened only by the explicit evaluation command
after predictions have been saved. Organizer-only material is never a prediction input.

One index normalizes JSON collections/service snapshots, isolated SQLite exports, correlated
log events, labelled text and supported cached PDF/image structures. Format matching uses
collection/table schemas, event types, field labels and explicit relationships, never case IDs,
evidence IDs, filenames, expected labels or numeric suffixes. Export owner/file/download schemas
establish `export_service` while preserving exporter provenance. Support replica readbacks keep
the replica source label and normalize to `support_platform` only when that supplying service
is explicit in the manifest. Resource IDs, identities and capture/observation times remain grounded.

A contact-index query is not a conversation. A support reference and shared order context do
not establish a support-message resource. Visual proposals need quoted, resource-bound type
and subject evidence; attachment ownership is checked separately. Financial retention registers
remain context unless explicit legal-hold semantics establish a hold. Legal holds and security
retention require supplied active proof; capture time is never record creation time. No retention
duration is invented. Unknown flags and omitted tombstone fields do not prove compliant states.

The ledger records inspected sources, searched aliases and link types, historical relationships,
resource/process states, applicable policy conditions, contradictions and remaining gaps. It cannot
prove unknown associations or eliminate OCR/adapter omissions. COMPLETE accepts sufficient scoped
proof rather than requiring every global service inventory, and never infers absence from no match.
All findings and COMPLETE checks cite eligible state evidence; INCOMPLETE remediation and future
verification have empty citations. An independent delivery validator checks complete step sets,
phase/operation ordering, fields, identifiers, citations and status against accepted facts.

Known gaps include record-specific retention terms, anonymous-resource historical associations,
uninterpreted visual regions, shared-context/ownership conditions and ambiguous authorization.
Eight previously recorded public temporal discrepancies remain excluded at the unchanged cutoff.
No hidden full-dataset accuracy measurement is available.

## Tests and packaging

```bash
python3 -m unittest discover -s tests -v
python3 code/package.py
```

The archive has `README.md`, `requirements.txt`, runnable `code/`, independent tests,
root `evaluation/evaluation_report.md`, root `evaluation/usage_report.md`, and trace-export
instructions. Prompts are included as source. Its explicit allowlist excludes dataset files,
runs, caches, credentials, virtual environments, transcripts and nested archives.
The package is runnable but **not a completed challenge submission** without a valid 518-row output.

## Transcript and trace export

`log.txt` is the genuine append-only development transcript and stays separate from `code.zip`.
Follow `agent_trace_instructions.md` for the separate `agent-trace.zip`: finish and quit the
coding sessions before copying the relevant original rollout files, preserve their structure,
include relevant application runtime traces, and review/redact secrets. Never copy auth or
configuration files. An active session cannot yet be exported as a complete finalized trace.

Challenge and submission: https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
