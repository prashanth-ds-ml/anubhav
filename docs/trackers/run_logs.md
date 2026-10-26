---
tags: [tracker, runs]
---
# Run logs

Summary of every **real** (non-mock) model run. The full traces live in the trace store; this file is the human index. Later, a script will append rows from the traces automatically.

| Date / time (IST) | run_id | task_id | Lang | Input | Model | Harness | Arm | Outcome | Tools called | Tokens in/out | Cost $ | Latency s | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 01:47 | smoke-text | T1 | EN | text | muse-spark-1.3 | — | — | ✅ | — | 14/163 | 0.0007 | 4.2 | basic call |
| 2026-10-27 01:47 | smoke-text | T2 | RT | text | muse-spark-1.3 | — | — | ✅ | find_customer ∥ check_stock | 764/594 | 0.0035 | 4.9 | parallel calls |
| 2026-10-27 01:47 | smoke-text | T3 | TE | text | muse-spark-1.3 | — | — | ✅ | find_customer ∥ check_stock | 790/649 | 0.0037 | 4.2 | Telugu → Roman args |
| 2026-10-27 01:47 | smoke-text | T4 ×3 | RT | text | muse-spark-1.3 | — | — | ✅ 3/3 | find_customer ∥ check_stock | ~854/~430 | ~0.0029 ea | ~3.3 | no confirm |
| 2026-10-27 01:47 | smoke-text | T5 | RT | text | muse-spark-1.3 | — | A (40 tools) | ✅ | find_customer ∥ check_stock | 2984/1011 | 0.0080 | 7.0 | 40 schemas OK |
| 2026-10-27 01:47 | smoke-text | T8 ×3 | EN | text | muse-spark-1.3 | — | — | ❌ | — | small | ~0.002 | — | temp 0 + seed not deterministic |
| 2026-10-27 01:47 | smoke-negation | T4b ×3 | RT | text | muse-spark-1.3 | — | — | ✅ 3/3 | find_customer → check_stock → create_draft_quote | — | ~0.03 total | — | full loop, never confirmed |

Artifacts: `artifacts/smoke/text_20261027_014700.json`, `artifacts/smoke/negation_loop_20261027_014750.json`

**Outcome values:** ✅ verified success · ❌ verified fail · ❓ clarification asked · ⛔ blocked unsafe · 💥 error
**Lang values:** EN · TE (script) · RT (Roman Telugu) · MIX

## Saved replay artifacts (for the demo)
- 
