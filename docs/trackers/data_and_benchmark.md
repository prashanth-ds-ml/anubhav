---
tags: [tracker, data, benchmark]
---
# Data and benchmark tracker

Generator runs, integrity results, human review and the sealed casebook. Spec: [[Data_Benchmark_Blueprint_v1.0]]. Plan: [[build_plan]] Layers 1 and 5.

## 1. Generator runs
Every generated world gets a row. Never edit generated data by hand; fix the generator and regenerate.

| Date | Run | Companies | Days | Orders | Trips | master_seed | generator ver | config hash | snapshot hash | Validation | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-29 | pilot | T01 | 7 (Sep 8–14) | 66 | 54 | 20261104 | 0.1.0 | `428941c30233` | T01 `db39cae926c6` | ✅ 0 critical | Awaiting your review (`reports/review_T01.md`) |
| 2026-10-29 | full (dry run) | T01, T02, T03, TNEW | 90 | 2,884 | 1,894 | 20261104 | 0.1.0 | `428941c30233` | T01 `266f596ddf94` · T02 `0f5b5d31f779` · T03 `d75970210e29` · TNEW `6d5ce019660d` | ✅ 0 critical | Generated to stress-test; final full run only after pilot review |

## 2. Hidden rules (world truth)
Agent-invisible. One row per planted rule, trap or change, so the benchmark can be checked against it.

| Rule ID | Company / scope | Kind | True rule | Valid from → to | Evidence planted | Trap? | Should transfer? |
|---|---|---|---|---|---|---|---|
| | | site_access / alias / habit / stale / contradiction | | | | | |

## 3. Validation gates (blueprint §7)
| Check | Pilot | Full |
|---|---|---|
| Structural (keys, uniqueness, tenant ownership) | ✅ | ✅ |
| Temporal (order ≤ pickup ≤ delivery, notes after events) | ✅ | ✅ |
| Physical (mass, volume, dimensions, site/vehicle) | ✅ | ✅ |
| Operational (overlaps, capacity, at least one feasible plan) | ✅ | ✅ |
| Statistical summaries reviewed | 🟨 by Claude; awaiting you | 🟨 by Claude |
| Privacy (no oracle in agent-visible data) | ✅ | ✅ |
| Reproducibility (same seed → same hash) | ✅ | ✅ |

## 4. Human review log
| Date | Pass | What was reviewed | Reviewer | Verdict | Issues found → fix |
|---|---|---|---|---|---|
| 2026-10-29 | 1 realism | pilot review packet (`reports/review_T01.md`) | owner | approved to proceed ("yes"); no issues raised | — |
| 2026-10-29 | 1 realism (Claude) | full 90-day dry run: rates, samples | Claude | 6 realism problems fixed (E-010) | generator |

## 5. Sealed casebook (100)
| Pack | Category | Target | Generated | Reviewed | Approved | Notes |
|---|---|---:|---:|---:|---:|---|
| 1 | Orders, quantity, units | 10 | | | | |
| 1 | Consolidation, splitting, planning | 15 | | | | |
| 1 | Carrier, vehicle, driver choice | 10 | | | | |
| 1 | Dispatch exceptions, replanning | 10 | | | | |
| 1 | Multilingual tool/intent | 5 | | | | |
| 2 | True/false/stale/conflicting lessons | 15 | | | | |
| 2 | Harness/tool-use improvement | 10 | | | | |
| 2 | Regional transfer / cold start | 15 | | | | |
| 2 | Cross-task multilingual | 10 | | | | |
| | **Total** | **100** | | | | |

**Language balance (tags):** EN __ · TE __ · RT __ · MIX __
**Freeze:** case IDs hash `____` · fixtures hash `____` · evaluator hash `____` · frozen on `____`

## 6. Adversarial suite
| Test | Count | Pass |
|---|---|---|
| Prompt injection in notes / tool results | | ⬜ |
| Cross-tenant access | | ⬜ |
| Role / tenant spoofing | | ⬜ |
| Concurrent double-booking | | ⬜ |
| Idempotent retry | | ⬜ |
| Stale approval after contradiction | | ⬜ |
| Unreviewed patch / lesson activation | | ⬜ |
