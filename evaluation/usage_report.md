# Usage report

## Full-dataset delivery run

There is **no final run that produced submission output.csv**. The 518-case run is a deterministic
diagnostic, with 250 accepted partial rows and 268 unresolved cases. A final inference usage/cost report
cannot be supplied honestly until a full validated output exists. No scaled application inference was launched.

| Run | Requests attempted | Application model invocations | Input tokens | Cached input (subset) | Output tokens | Measured wall time | Inference cost |
|---|---:|---:|---:|---:|---:|---:|---|
| Cached full diagnostic | 518 | 0 | 0 | 0 | 0 | 52.464495 s | 0 model charges; local compute cost unmeasured |

Per-request application model usage for this diagnostic: 0 input, 0 output, 0 total tokens and
0 model inference charges. Model/provider: none. These zeros do not cover coding-assistant tokens,
previous extraction or previous live investigations. Local compute and coding-assistant billing are
unavailable. The 32-case diagnostic cycles likewise made zero model calls. Existing extraction caches
were reused; no new extraction calls or benchmarks were made in this pass.

## Previous genuine application investigations (not the final run)

These two saved Codex investigations used OpenAI via an authenticated Codex ChatGPT login,
requested and reported model `gpt-6-sol`. Their usage was observed before this delivery revision.
They did not produce accepted complete case outputs. Raw events and failures remain unchanged.

| Saved run | Runtime invocations | Usage-bearing model responses | Input including cached | Cached subset | Uncached input | Output | Wall time |
|---|---:|---:|---:|---:|---:|---:|---:|
| runs/semantic-support-live | 1 | 8 | 116381 | 102784 | 13597 | 677 | 27.110003 s |
| runs/semantic-visual-live | 1 | 9 | 141192 | 125312 | 15880 | 928 | 30.202239 s |
| Overall for these two runs only | 2 | 17 | 257573 | 228096 | 29477 | 1605 | 57.312242 s |

Cached input is already included in input tokens and is **never added twice**.
Total tokens for these two runs: 259178; average per investigated request:
129589.0 total (128786.5 input including 114048.0 cached,
802.5 output). Reasoning-output counts are not added again to output counts.
Provider request counts are unavailable; two runtime invocations and 17 usage-bearing responses
must not be confused with 17 known billable API requests. Monetary cost and per-request cost:
unavailable, because the login runtime does not supply pricing or per-call billing. No API price
or model metadata was guessed. Other historical prototype traces are preserved but excluded from
this explicitly scoped subtotal; this is not a lifetime development-cost total.

The root coding harness is Codex with runtime model gpt-6.1-sol. Its own token/billing totals are
not supplied to the application and are unavailable here. They must not be reported as zero.

## Bounded inference projection and access feasibility

No additional live pilot or benchmark was run. The following projections use the two prior semantic
cases only; they are estimates, not observed improvements, token caps, or a full-dataset agent result.

* Current login check: Codex CLI 0.163.0 reports Logged in using ChatGPT. This proves a configured login,
  not model availability, remaining allowance, throughput or sufficient quota. No auth files were read.
* Thirty full-run requests explicitly require authorization judgment. At the observed per-case range,
  30 comparable investigations would consume 3,491,430–4,235,760 input tokens including cached input,
  407,910–476,400 uncached input, 20,310–27,840 output, and about 13.6–15.1 minutes sequentially.
  Cache reuse at that scale is not guaranteed. A request-only authorization interaction could differ greatly;
  no unmeasured optimized adapter or provider was substituted.
* For all 268 unresolved cases, the same weak extrapolation is 31,190,108–37,839,456 input tokens
  and about 121.1–134.9 minutes. Many cases need unavailable facts rather than more model effort.
* Existing per-case hard runtime budget is 180 seconds; 10 tool calls and 3 shared proposal attempts.
  A hypothetical explicitly selected batch of 30 cases has at most 30 runtime invocations,
  300 case-tool calls, 90 proposal attempts and 90 minutes of runtime timeout budget, plus orchestration.
  There is no implemented automatic live batch launcher and no hard input-token ceiling in the Codex adapter.
  Tool duration is checked on return; the overall process-group timeout terminates child processes.
* Remaining allowance and reset capacity are not exposed by the login runtime. Available access cannot
  be certified to support scaled inference. No direct API credentials, alternative provider, or mocked
  live success are assumed. Recommendation: retain the partial diagnostic and resolve supplied-proof
  questions before spending calls; do not launch hundreds of nested investigations.

## Artifacts and trace export

Measured diagnostic usage: `runs/delivery-full/summary.json`; per-case deterministic traces:
`runs/delivery-full/cases/`. Prior actual model observations: the two usage.json/model_events.jsonl
pairs listed above. Those native traces and initial rejected tool calls were not overwritten.
The source archive excludes runtime traces, caches, dataset and credentials.
The genuine root log.txt is a separate transcript deliverable. Follow agent_trace_instructions.md:
quit sessions before copying only relevant rollout files into a separate reviewed agent-trace.zip.
Do not include authentication/configuration files or claim an active session export is finalized.
