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
| 2026-10-29 | golden-path | Jangaon ×4 + ambiguous | RT/TE/EN/MIX | text | muse-spark-open-1026 | v0 | — | ✅ | find_site → get_site_constraints → create_dispatch_draft | — | 0.29 | — | batch summary; `scripts/golden_path.py` |
| 2026-10-29 | EXP-008 / EXP-009 / EXP-009b / EXP-010 | see [[experiments]] | RT/TE/EN | text | muse-spark-1.3 (mining) + open-1026 (agent) | v0 | A–E | see [[experiments]] | — | — | see [[cost_ledger]] | — | batch summaries; per-run rows in `artifacts/` |
| 2026-10-29 | EXP-011 | 38 cases × arms (102 runs) | RT/TE/EN | text | muse-spark-open-1026 | v0 | A/B/C/E | C 24/26 · E 12/12, 0 unsafe | — | — | 4.99 | — | `artifacts/benchmark/exp011_20261029_210758.json` (+ `_rows.jsonl` for the 37 resumed runs) |
| 2026-10-30 | live-check | 6 user questions | TE/RT | text | muse-spark-open-1026 | v0 + 8 new tools | — | ✅ 6/6 | plan_board, check_load, create_dispatch_drafts, list_drivers, trip_documents, performance, list_lessons | — | 0.31 | — | T03 plan: 16 drafts, 18/21 orders; see [[tool_calling]] |
| 2026-11-02 | dry run (7 runs) | S4, S5 | RT/EN | text | muse-spark-1.3 | current | team | 6 of 7 as hoped | find_site, plan_board, check_load, create_dispatch_draft | — | 0.39 | — | S4: lesson retired → V11 (32 ft); restored → V08 (22 ft), cites L-T01-002. S5: confirm-now drafted only; overload refused (27.3 t on 9 t, chemical with food); night-only site refused 9 am and asked for a night slot; ambiguous Warangal drafted all 3 Warangal orders instead of asking. Nicknames: "nalla lorry lo pedda godown load" → V11 to Venkata Sri Traders, Warangal. One run each. |
| 2026-11-03 00:15–03:17 | overnight batch (D-054) | EXP-015, EXP-014, EXP-016 | RT/TE/EN | text | muse-spark-1.3 | current (frozen) | A/B/C/E, stages, Q/T | see [[experiments]] | — | — | 43.05 | — | 905 rows: EXP-015 306 ($20.15), EXP-014 283 ($20.62), EXP-016 52 ($2.28). Meta only, Baseten key blanked. Per-run rows in `artifacts/benchmark/exp01{4,5,6}_2026110*_rows.jsonl` |
| 2026-11-03 20:59–21:11 | EXP-018 (scaling check) | T01 mining at 30/60/90 days × 3 + 1 smoke | — | text | muse-spark-1.3 | current (frozen) | 30d/60d/90d | ✅ bar met | — (miner only) | — | 0.55 | — | Recall 72.7% → 81.8% → 81.8%, precision 100% at every length, 0 traps. Meta only, Baseten key blanked. `artifacts/learning/exp018_20261103_205939.json` (+ `_rows.jsonl`, `_lessons.sqlite`, `.md`) |

Artifacts: `artifacts/smoke/text_20261027_014700.json`, `artifacts/smoke/negation_loop_20261027_014750.json`

**Outcome values:** ✅ verified success · ❌ verified fail · ❓ clarification asked · ⛔ blocked unsafe · 💥 error
**Lang values:** EN · TE (script) · RT (Roman Telugu) · MIX

## Saved replay artifacts (for the demo)
- 
