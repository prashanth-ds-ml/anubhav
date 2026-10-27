---
tags: [tracker, experiments]
---
# Experiments and benchmark

**Rule:** write the hypothesis *before* running. Report null results as null. Never fabricate uplift. Template: `templates/experiment`.

## Benchmark composition (target: 48)
| Split | EN | TE | RT | MIX | Voice variants | Total |
|---|---|---|---|---|---|---|
| Dev | 5 | 8 | 11 | 8 | 0 (later) | 32 |
| Held-out (locked) | 3 | 4 | 5 | 4 | 0 (later) | 16 |
| **Target** | 8 | 12 | 16 | 12 | ~8 | **48** |

Task file: `datasets/tasks/benchmark_v1.jsonl` (held-out = `split: heldout`). See `datasets/README.md`.

## Scenario coverage
| Scenario type | # tasks |
|---|---|
| SKU disambiguation | |
| Units / pack conversion | |
| Negation ("vaddu" = don't want, "cheyyaku" = don't do it) | |
| Discount eligibility | |
| Stock shortage | |
| Multi-step dependencies | |
| Missing tool / retrieval miss | |
| Transient errors | |

## Results by arm
| Arm | Config | Task success (mean ± spread) | Recall@k | Tool-call validity | Unsafe executed | Tokens/success | Cost/success | Latency p50 |
|---|---|---|---|---|---|---|---|---|
| A | Direct, 40 tools | | | | | | | |
| B | BigTool, baseline harness | | | | | | | |
| C | BigTool + approved harness | | | | | | | |
| OW | Muse Spark Open (if credits) | | | | | | | |

## Results by language (arms B → C)
| Lang | B success | C success | Δ |
|---|---|---|---|
| EN | | | |
| TE | | | |
| RT | | | |
| MIX | | | |

## Manual-vs-agent timing study (FR-16; self-timed, labeled as such)
| Quote # | Manual time | Agent time | Agent correct? |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| **Mean** | | | |

---
## Experiment entries

### EXP-001: Baseline B0, "is there anything worth fixing?" (pre-registered 2026-10-27, before running)
- **Question:** Does a frozen Muse agent fail on enough realistic tasks, for reasons a harness can fix, to justify the self-improvement project?
- **Setup:** `muse-spark-1.3`, temperature 0, the 8 simple tools in `scripts/eval/run_baseline.py`, a generic system prompt, **no** shop-specific hints. All 48 tasks × 2 repeats, fresh DB per run.
- **Primary metric:** task success: one draft quote with exactly the expected customer and `(sku, cases)` lines; for clarify/no_quote tasks, no quote created. Reported as mean over repeats and as pass^2 (passes both runs).
- **Secondary:** unsafe outcomes (a quote created when it should not be, or for the wrong customer), reply-language match, tool calls, cost and latency per task.
- **Hypothesis:** dev success 65–85%. Failures cluster on hidden shop slang, plus some policy slips (schemes, credit, defaults) and reply-language drift.
- **Decision rule (owner's thresholds, adopted 2026-10-27 while the run was in progress and before any results were seen):**
  - **Below 85% mean success:** keep the self-improving agent idea; there is meaningful room for improvement.
  - **85–95%:** investigate whether we can improve efficiency, reliability over repeats, or adaptation to changing tools.
  - **Above 95%:** strongly consider pivoting to a different problem where Muse enables something genuinely new.
  - **Qualifier:** the failures must be *harness-fixable* (missing shop knowledge, policy following, tool-use habits, reply language), not our own tool, grader or task-wording bugs. Bugs get fixed and re-run before applying the thresholds.
- **Caveat:** this is arm B0 (8 tools, no retrieval problem). Tool discovery at 40 tools is tested separately on Day 4.
- **Result (run 1, 2026-10-27, `artifacts/baseline/arm-core_v1_20261027_104331.json`):** mean success **80%** (dev 86%, held-out 69%); 38 tasks pass both repeats, 9 fail both, 1 flaky. Unsafe outcomes **0**. Reply language OK 99%. Cost $2.35 (96 runs), 6.9 tool calls and 19 s per run. English 100%, Telugu 83%, Roman 72%, mixed 75%.
- **Failure analysis (all 10 failing tasks read by hand):**
  - **Harness-fixable, missing shop knowledge (6):** D09, D15, D23, D29, H05, H10. Every one is hidden slang. Muse asked a clarifying question each time; it never guessed.
  - **Our bugs (4), to fix before applying the rule:** D25, H09 (`find_customer` matched "Vijaya Mart" on the word "mart"); H12 (policy said "ask" even when only one SKU fits); H13 (task "noodles 10 cases" is genuinely ambiguous: 70 g vs 280 g).
  - Everything else (units, discounts, bulk, schemes, credit, history defaults, negation, corrections, ambiguity) passed: Muse is strong at reasoning over tools and policies.
- **Run 2 (after the fixes, `artifacts/baseline/arm-core_20261027_105712.json`):** mean success **88%** (dev 89%, held-out 88%); 42 pass both repeats, 5 fail both, 1 flaky. Unsafe **0**. Reply language OK 95%. $2.04, 6.9 tool calls, 11.4k input tokens, 12 s per run. **The only failing tasks are the 6 slang tasks** (D09, D15, D23, D29, H05, H10).
- **Verdict (owner's thresholds):** **85–95% band → investigate efficiency, reliability or adaptation to changing tools.** Real headroom exists but is narrow: missing shop knowledge only. See EXP-002 for the efficiency side.

### EXP-002: 40 tools, direct (arm A) vs. Muse tool search (arm B) (pre-registered 2026-10-27, before running)
- **Question:** Does going from 8 to 40 tools hurt success? Does Muse's built-in tool search (Responses API, every tool deferred in 8 namespaces) keep success while cutting input tokens?
- **Setup:** same tasks, prompt, grader and repeats as EXP-001 run 2 (after the bug fixes). `core` = 8 tools, `a` = 40 tools passed directly (Chat Completions), `b` = 40 deferred tools + `{"type": "tool_search"}` (Responses API).
- **Metrics:** task success (mean, pass^2), input tokens and cost per run, tool calls, namespaces loaded per search (from `tool_search_call.paths`).
- **Already seen in a 2-task smoke test:** Muse's first search loaded 7–8 of the 8 namespaces at once, so retrieval may not be selective. If that holds, B saves little and "tool discovery" headroom has to come from the harness (namespace and tool descriptions, aliases), not from search alone.
- **Hypothesis:** A ≈ core on success (40 schemas is small for Muse) with ~2× input tokens; B ≈ A on success with modest token savings.
- **Result (2026-10-27):**

| Arm | Mean success | Fail both | Unsafe | Tool calls/run | Input tokens/run | Latency/run | Cost (96 runs) |
|---|---|---|---|---|---|---|---|
| core (8 tools) | 88% | 5 | 0 | 6.9 | 11.4k | 12 s | $2.04 |
| A (40 direct) | 86% | 6 | 0 | 11.1 | 24.5k | 15 s | $3.81 |
| B (40, Muse tool search) | 89% (85/96, after re-running 4 runs that crashed on our side) | 6 | 0 | 12.2 | 30.2k | 57 s | $4.56 + $0.18 re-runs |

  - All three arms fail only slang tasks (A also failed D18 "Balaji vallu ki GG oil").
  - **Muse tool search is not selective here:** 93 of 101 searches loaded 7 or 8 of the 8 namespaces. B used *more* input tokens than A and was ~4× slower, with no accuracy gain.
  - Going from 8 to 40 tools costs ~60% more tool calls and ~2× tokens, but not accuracy.
  - Hypothesis partly wrong: B saved no tokens.
- **Infra bug found:** on Windows a failed run's temp DB stayed locked and the cleanup error hid the real error (4 runs in arm B). Fixed: the DB is closed in `finally` and cleanup errors are ignored.

### EXP-004: Muse Spark Open (open weights, Baseten) vs. Muse Spark 1.3 (pre-registered 2026-10-27, before running)
- **Question:** Does the open-weights model fail more often than Spark 1.3, and are its failures harness-fixable? If so, "Spark teaches Spark Open through verified harness fixes" becomes the project.
- **Setup:** `meta-models/muse-spark-open-1026` on Baseten (Chat Completions), arms `core` (8 tools) and `a` (40 tools); same tasks, prompt, grader, temperature 0 and 2 repeats as EXP-001 run 2 / EXP-002. Arm B is not run (Muse tool search needs the Meta Responses API).
- **Compare against:** Spark 1.3 core 88%, A 86%.
- **Decision rule (fixed now):**
  - **Open clearly worse (≥ 8 points below Spark on the same arm) and most extra failures are harness-fixable** (policy following, tool-use habits, language, shop knowledge) → **teacher–student project**: Spark diagnoses Open's failures and proposes patches, a human approves, held-out verified on Open.
  - **Within ~8 points of Spark** → headroom is narrow on both; run EXP-003 (Business Operations Lab head-to-head) before choosing.
  - **Open fails ordinary requests** (English/basic tasks) → keep it off the customer path.
- **Result (2026-10-27, `artifacts/baseline/arm-*_baseten_*.json`):**

| Model | Arm | Mean success | Fail both | Unsafe | Lang OK | Tool calls/run | Input tokens/run | Latency/run | Cost (96 runs) |
|---|---|---|---|---|---|---|---|---|---|
| Spark 1.3 | core (8) | 88% | 5 | 0 | 95% | 6.9 | 11.4k | 12 s | $2.04 |
| Spark Open | core (8) | 88% | 5 | 0 | 99% | 7.3 | 11.3k | 8 s | $1.97 |
| Spark 1.3 | A (40) | 86% | 6 | 0 | 95% | 11.1 | 24.5k | 15 s | $3.81 |
| Spark Open | A (40) | 86% | 6 | 0 | 98% | 14.1 | 25.0k | 12 s | $3.89 |

  - Same failing tasks as Spark: the hidden-slang tasks. Extra on Open: one 429 rate-limit error (H11, infra, counted as a fail) and one flaky D17 run with 40 tools (19 tool calls, then asked to confirm instead of quoting: a tool-use habit).
  - Open is faster and slightly better on reply language; with 40 tools it makes ~27% more tool calls than Spark.
- **Verdict (rule fixed above):** Open is **within 8 points** of Spark on both arms (0 and 0 points) → **headroom is narrow on both models; run EXP-003 (Business Operations Lab head-to-head) before choosing.** The teacher–student premise (a weaker student) does not hold on this benchmark.

### EXP-003: Business Operations Lab head-to-head (final project-selection experiment; frozen 2026-10-27 before any Muse call)
- **Frozen files:** `datasets/lab/exp003_scenarios.json` (sha256 `cfaf9858ac802e33…`), `scripts/eval/exp003_lab.py` (sha256 `03ddc14efadbd55a…`). Scenario facts are copied from the business DB; each scenario has hidden `gold_constraints` (the correct reading of the instructions), never shown to Muse.
- **Scenarios (5):** L1 shortage + a no-substitute customer + a deadline before restock (Roman Telugu) · L2 binding credit limits, a hold lifted, a limit raised (Telugu) · L3 a sequence of changes: cancel, quantity change, no-substitute (mixed) · L4 a late customer that must be filled in full + a deadline (Roman Telugu) · L5 primary out of stock, a substitute in a different pack (2:1), a binding credit limit after a quantity change (mixed).
- **Hard rules:** stock/substitute/restock capacity; no over-allocation; credit headroom incl. GST for credit customers; holds get nothing; backorders only from a restock on or before the deadline; operator instructions override data.
- **Score:** weighted fulfillment = Σ weight × (now + 0.9 × substitute/ratio + 0.5 × backorder) / Σ weight × wanted (gold 3, silver 2, bronze 1), **0 if any hard rule is broken**. Also: feasibility, violations, revenue now and on backorder, latency, cost.
- **Methods:** basic greedy (FIFO, stock only) · strong heuristic without instructions · strong heuristic with the gold reading · exact ILP optimum (gold) · Muse one-shot · Muse + simulator feedback (≤ 2 revisions; the simulator checks against **Muse's own extracted constraints**, never the gold ones) · hybrid (Muse extracts constraints → ILP). Muse = `muse-spark-1.3`, temperature 0, 3 repeats.
- **Known before Muse (dry run):** the strong heuristic **equals the exact optimum in 5/5 scenarios** (mean 0.847). Optimization adds nothing at this scale; ignoring the instructions drops the heuristic to 0.101 (4 of 5 plans break a rule). Caveat: the scenarios were *designed* so that instructions matter, so this gap shows what correct reading is worth, not that Muse provides it.
- **Decision rule (fixed now):**
  - **GO for the Lab** only if the hybrid reaches ≥ 95% of the optimum mean, is feasible in ≥ 90% of runs, and Muse extracts ≥ 90% of instruction fields correctly. Even then, Muse's role would be *interpreting* instructions, with a solver doing the planning.
  - Report separately whether Muse planning directly (one-shot / feedback) matches the heuristic; any shortfall counts as "conventional algorithm beats Muse".
  - **NO-GO** otherwise.
  - **Either way, before pivoting:** "Muse reads Telugu instructions accurately" is the same capability the 48-task benchmark already showed at ~100% outside slang. A GO must therefore also beat the original project on novelty, not just on feasibility.
- **Result:** _pending_

