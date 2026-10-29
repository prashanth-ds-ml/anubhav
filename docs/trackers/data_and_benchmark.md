---
tags: [tracker, data, benchmark]
---
# Data and benchmark tracker

Generator runs, integrity results, human review and the sealed casebook. Spec: [[Data_Benchmark_Blueprint_v1.0]]. Plan: [[build_plan]] Layers 1 and 5.

## 1. Generator runs
Every generated world gets a row. Never edit generated data by hand; fix the generator and regenerate.

| Date | Run | Companies | Days | Orders | Trips | master_seed | generator ver | config hash | snapshot hash | Validation | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | pilot | T01 | 7 | ~100 | | | | | | ⬜ | |

## 2. Hidden rules (world truth)
Agent-invisible. One row per planted rule, trap or change, so the benchmark can be checked against it.

| Rule ID | Company / scope | Kind | True rule | Valid from → to | Evidence planted | Trap? | Should transfer? |
|---|---|---|---|---|---|---|---|
| | | site_access / alias / habit / stale / contradiction | | | | | |

## 3. Validation gates (blueprint §7)
| Check | Pilot | Full |
|---|---|---|
| Structural (keys, uniqueness, tenant ownership) | ⬜ | ⬜ |
| Temporal (order ≤ pickup ≤ delivery, notes after events) | ⬜ | ⬜ |
| Physical (mass, volume, dimensions, site/vehicle) | ⬜ | ⬜ |
| Operational (overlaps, capacity, at least one feasible plan) | ⬜ | ⬜ |
| Statistical summaries reviewed | ⬜ | ⬜ |
| Privacy (no oracle in agent-visible data) | ⬜ | ⬜ |
| Reproducibility (same seed → same hash) | ⬜ | ⬜ |

## 4. Human review log
| Date | Pass | What was reviewed | Reviewer | Verdict | Issues found → fix |
|---|---|---|---|---|---|
| | 1 realism | pilot: 20 trips, 30 orders, rules | me | | |

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
