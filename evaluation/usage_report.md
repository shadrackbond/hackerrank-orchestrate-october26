# Usage report — actual final output-producing run

## Final run

`runs/final-submission/summary.json` records the deterministic run that wrote root `output.csv`.
It processed **518 requests** in **63.257112 seconds**, using existing content-hash
extraction caches and local policy/identity processing. No application model invocation,
new extraction, live nested investigation or network inference occurred in this run.

| Provider/model | Calls | Input tokens | Cached input | Output tokens | Total tokens | Estimated model cost |
|---|---:|---:|---:|---:|---:|---:|
| None — deterministic local final path | 0 | 0 | 0 | 0 | 0 | 0 |
| Overall final run | 0 | 0 | 0 | 0 | 0 | 0 |

Average application input/output/total tokens per request: **0 / 0 / 0**.
Total and per-request model-inference charges for this run: **0**. Local compute cost
is unmeasured, not zero. Root coding-assistant token usage and cost are unavailable and
are not included in these zeros. The coding harness is Codex, model gpt-6.1-sol.

The one public final-path run processed 32 requests in **7.785861 seconds**,
also with zero application model calls/tokens. Its post-prediction reference comparison
is separate from output generation and makes no model calls.

## Prediction and coverage accounting

The final 518 rows include 429 evidence-established scoped statuses and 89 inferred
precautionary predictions. Plans: 235 scoped certificates and 283 uncertified cases.
These are not hidden accuracy measurements. Uncertainty and incomplete coverage are
recorded per case in root `uncertainty_report.json`, outside output.csv.

## Historical application usage — excluded from final-run totals

Earlier genuine OpenAI/Codex-login investigations requested/reported model `gpt-6-sol`.
The two saved semantic investigations together recorded 257573 input tokens including
228096 cached, 1605 output tokens, and 57.312242 seconds. The subsequent bounded account-access
pilot recorded 117862 input including 98944 cached, 1075 output, and 30.958783 seconds.
None produced an accepted final complete row. These historical subtotals are not a lifetime
usage total and were not newly spent by the final submission path. Cached input is already
included in input and is never added twice. Reasoning output is already included in output.
Provider HTTP request counts, monetary billing and remaining login quota are unavailable;
no price or provider request count is invented. Other original attempts remain in native traces.

Original `model_events.jsonl`, usage and prompt files are exported separately from code.zip.
The in-session trace ZIP excludes the active session until Codex exits; follow
`agent_trace_instructions.md` and run `python3 code/export_traces.py --after-session-exit`
after quitting. The root log.txt remains the genuine append-only transcript.
