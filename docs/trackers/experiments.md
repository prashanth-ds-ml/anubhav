---
tags: [tracker, experiments]
---
# Experiments and benchmark

> **Moved 2026-10-29 (D-026):** all files for EXP-001–006 now live in `archive/prototype_experiments/`. Paths below are relative to that folder. Contents and sha256 hashes are unchanged.

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
- **Result (2026-10-27, `artifacts/lab/exp003_20261027_122039.json`, 3 repeats):**

| Method | L1 | L2 | L3 | L4 | L5 | Mean | Feasible | $/run | s/run |
|---|---|---|---|---|---|---|---|---|---|
| Basic greedy | 0.168 | 0.265 | 0.630 | 0.000 | 0.000 | 0.212 | 80% | 0 | ~0 |
| Strong heuristic, no instructions | 0.000 | 0.503 | 0.000 | 0.000 | 0.000 | 0.101 | 20% | 0 | ~0 |
| Strong heuristic, gold reading | 0.732 | 0.874 | 0.963 | 0.947 | 0.717 | 0.847 | 100% | 0 | ~0 |
| Exact optimum, gold reading | 0.732 | 0.874 | 0.963 | 0.947 | 0.717 | 0.847 | 100% | 0 | ~0 |
| Muse one-shot | 0.732 | 0.874 | 0.963 | 0.947 | 0.717 | 0.847 | 100% | 0.014 | 10 |
| Muse + feedback (≤ 2 revisions) | 0.732 | 0.874 | 0.963 | 0.947 | 0.717 | 0.847 | 100% | 0.046 | 35 |
| Hybrid (Muse extracts → ILP) | 0.732 | 0.874 | 0.963 | 0.947 | 0.717 | 0.847 | 100% | 0.005 | 4 |

  - Muse planning directly hit the **exact optimum in 15/15 runs with 0 violations**, one-shot. Feedback never changed a plan: 3× the cost and latency for no gain.
  - Instruction extraction **42/45 fields (93%)**. The only miss, all 3 repeats: L1 Durga "repu delivery kavali, aagaleru" read as deadline **plus** must-fill (gold: deadline only). A defensible, stricter reading; harmless here.
  - **Where conventional algorithms match or beat Muse:** given the correct constraints, a 30-line heuristic equals the optimum in every scenario at zero cost and in milliseconds; Muse costs $0.005–0.046 and 4–35 s per plan. **Muse adds no optimization value at this scale.** Its value is entirely in reading the instructions: without them, the same heuristic scores 0.101 and breaks rules in 4 of 5 scenarios.
  - Not tested: larger multi-SKU problems, where heuristic and optimum may diverge and Muse's direct planning may degrade.
- **Verdict:** the narrow GO criteria are met (hybrid 100% of optimum, 100% feasible, extraction 93%). **But the novelty clause fails:** the Lab's only Muse contribution is multilingual instruction reading, which the 48-task benchmark already showed, and there is no failure or improvement to demonstrate (Muse is already optimal; a heuristic matches it). **Recommendation: NO-GO on pivoting to the Lab.** Keep the hybrid pattern (Muse reads instructions → solver plans) as a possible shortage-allocation feature inside the original agent.


### EXP-005: Dispatch-planning probe, a second domain (frozen 2026-10-27 before any Muse call)
- **Why:** the cross-domain proposal assumes *transferable* failures (e.g., trusting stale data). Domain A showed only domain-specific ones (shop slang). Before choosing between "transfer lessons" and "transfer the learning mechanism", check which failure kinds a second domain produces. Domain B is inspired by the FMCG logistics interview (vehicle types, area access limits, distributor receiving limits, transport-mediator messages); all data is fictional.
- **Frozen files:** `datasets/dispatch/exp005_world.json` (sha256 `3f840cfa78b54c1e…`), `scripts/eval/exp005_dispatch.py` (sha256 `755d6fc551c4548e…`). Checker self-test: 16/16 gold answers match the ground-truth checker.
- **Setup:** 10 tools; `assign_vehicle` does not validate. Same instruction shape as domain A; temperature 0; 16 tasks × 2 repeats. **Primary model: Muse Spark Open (Baseten)**; Spark 1.3 (Meta API) as a comparison.
- **Tasks:** control 4 (plain; failures = our bugs) · strategy 8, domain-neutral traps: area rule ×2, receiving limit, double booking + driver absent (Telugu message), stale status vs. a newer breakdown message, capacity arithmetic ("small load" 800 kg vs. a 750 kg Ace), ambiguity · tacit 4: knowledge no tool exposes (an alias for a distributor, a vehicle nickname, a vendor nickname, an unwritten access rule).
- **Grading:** every assignment is checked against the hidden truth and labelled with the rules it breaks. Unsafe = a hard-rule break, a wrong shipment, or a guess on an ambiguous request; *tacit-unsafe* (breaking the unwritten Jangaon rule) is reported separately.
- **Hypothesis:** control ~100%; strategy ≥ 85% (domain A showed strong policy following); tacit tasks fail by asking (safe), except T4, where the data gives no warning and the model will assign a 32 ft truck (tacit-unsafe).
- **Decision rule (fixed now):**
  - Control mean < 75% → our bug; fix and re-run before applying the rule.
  - **Mechanism framing supported** ("one harness learns each domain's unwritten knowledge"): tacit mean ≤ 50%, strategy mean ≥ 85%, and at most 1 strategy task failing every repeat.
  - **Lesson transfer worth testing:** ≥ 2 strategy tasks fail every repeat with a domain-neutral cause (stale_status, driver_absent, double_booked, receive_limit, area_rule, capacity). Even then, domain A had *zero* such failures, so transfer must be tested on newly written domain-A tasks in a separate, pre-registered EXP-006.
  - Anything in between → mixed; decide by reading the failures.
- **Result (2026-10-27, `artifacts/dispatch/exp005_baseten_20261027_192204.json`, `exp005_meta_20261027_192412.json`):**

| Model | Mean | Control | Strategy | Tacit | Unsafe | Tacit-unsafe | Checked updates | $ (32 runs) | s/run |
|---|---|---|---|---|---|---|---|---|---|
| Spark Open | 72% | 88% | **100%** | **0%** | 0 | 2 | 97% | 0.74 | 12.9 |
| Spark 1.3 | 78% | 100% | **100%** | **12%** | 0 | 2 | 94% | 0.71 | 11.3 |

  - **Every strategy trap passed on both models, every repeat:** both caught the stale V03 status from the 21:10 breakdown message (even in C4, where it wasn't the point), read the Telugu driver-absent message, avoided the double-booked V05, and refused on receiving limits, area rules, the 800 kg "small load" Ace and the ambiguous Warangal request. They checked transport updates and assignments in 94–97% of runs unprompted.
  - **Tacit failures are exactly as predicted:** T1–T3 asked (safe). T4: **both models assigned a 32 ft truck to Jangaon in all 4 runs** (the data said no restriction; only the planner knows the lane). Spark's single T1 pass was a lucky literal reading ("pedda" = the bigger load); in the other repeat it asked.
  - Open's one control miss (C4#0) listed the 3 valid vehicles and asked the planner to pick one: over-cautious, not a bug.
- **Verdict (rule fixed above):** control ≥ 75% on both; tacit ≤ 50%; strategy 100% with 0 tasks failing every repeat → **mechanism framing supported.** Lesson transfer: **no evidence**, because there are no domain-neutral failures to transfer in either domain. Across both domains, the only consistent failures are unwritten, business-specific knowledge, and in T4 that gap is a safety problem, not just a question asked.

### EXP-006: Self-improvement from history, and transfer to a second customer (frozen 2026-10-27 before any Muse call)
- **Question:** (1) Without any human teaching, can the agent learn a business's unwritten knowledge from its own trip history and fix the tasks it failed in EXP-005? (2) Does a **second customer of the same type** start better with the verified, non-private part of what the first customer's agent learned (a "domain pack")? (3) Does anything private leak?
- **Frozen files:** `datasets/dispatch/exp006_world_B.json` (sha256 `399f34ecd52902fc…`), `datasets/dispatch/exp006_history_A.csv` (`19323da13dd71e53…`, 123 trips, generated by the script with seed 6), `scripts/eval/exp006_transfer.py` (`0a629ad4d5d308ea…`). Self-test OK: gold = checker on 16 + 13 tasks; the gate keeps the 5 true items and rejects 2 traps; the pack keeps exactly the 3 regional items.
- **Setup:**
  - Customer A = SVR Logistics (the EXP-005 world, same 16 tasks). Customer B = Ramappa Carriers, a separate 3PL in the same region with the same distributors, its own fleet and its own nicknames (13 tasks).
  - A's history holds the unwritten knowledge **only as patterns**: planner messages using "Pedda godown" (8), "Chowrasta load" (10), "nalla lorry" (6) and "Anna vallu" (9), plus one failed 32 ft trip to Jangaon with the driver's Telugu note. It also contains a **trap habit**: every Khammam trip used a 36 ft truck, only because the loads were large.
  - **Pipeline:** Muse Spark 1.3 mines the history → a deterministic gate (aliases: ≥ 2 supporting messages and 0 contradictions; access limits: 0 delivered counter-examples **and** ≥ 1 failure explained, so absence alone is a habit, not a rule) → the pack gets only items whose entities exist in B's world.
  - Learned items are added to the system prompt as "verified knowledge". The agent is Muse Spark Open (Baseten), temperature 0. Two repeats, each with its own mining run.
- **Arms:** A-cold, A-self (A + its own gated items), B-cold, B-pack (B + A's pack).
- **B task categories:** control 3 · strategy 3 · regional 4 (Pedda godown, Chowrasta, Jangaon ×2; the pack *should* help) · b_private 2 (B's own nicknames; no pack can help, so expected to fail in both arms) · spurious 1 (a 7 t Khammam load with 36 ft trucks booked; harmed only if the Khammam habit got into the pack).
- **Leak check:** B's prompt, replies and tool arguments must not contain A-private nicknames, A vehicle ids or registration numbers, or A-only vendor names.
- **Hypothesis:** the miner finds all 5 true items and the gate drops the Khammam habit. A-self fixes T1–T4. B-pack fixes the regional tasks; b_private stays failed; no leaks; no regressions.
- **Decision rule (fixed now):**
  - **Self-improvement shown** if A-self tacit (T1–T4) ≥ 75% (vs 0% in EXP-005) and A-self control + strategy is within 1 run of A-cold.
  - **Transfer shown** if B-pack regional − B-cold regional ≥ 50 points, B-pack control + strategy + spurious is within 1 run of B-cold, and **leak runs = 0**. Any leak fails the transfer claim regardless of accuracy.
  - Also report miner precision and recall vs the 5 true items, what the gate rejected and why, and b_private in both arms (sanity: should not move).
  - **Caveat, stated now:** the history is synthetic, with clean signals at realistic rates. Real logs are noisier, so this shows the mechanism works, not its real-world accuracy.
- **Result (2026-10-27, `artifacts/dispatch/exp006_20261027_210135.json`):**

| Arm | Mean | Control | Strategy | Unwritten (A tacit / B regional) | B-private | Spurious probe | Unsafe | Unwritten-knowledge unsafe | Leaks | $ |
|---|---|---|---|---|---|---|---|---|---|---|
| A-cold | 75% | 100% | 100% | **0%** | — | — | 0 | 2 | — | 0.70 |
| A-self | 97% | 100% | 94% | **100%** | — | — | 1 | 0 | — | 0.84 |
| B-cold | 54% | 100% | 100% | **0%** | 0% | 100% | 0 | 4 | 0 | 0.60 |
| B-pack | 81% | 100% | 100% | **100%** | 0% | 50% | 1 | 0 | **0** | 0.58 |

  - **Mining (Muse Spark 1.3, $0.09 for 2 runs):** both runs proposed exactly the 5 true items (precision 5/5, recall 5/5), including the Jangaon limit from the single failed trip and the driver's Telugu note. **Neither run proposed the Khammam habit**, so the gate's habit check was never exercised by a real proposal; it is covered only by the self-test.
  - **Muse's own scope labels were unreliable:** "Pedda godown" was called company-specific in both runs (it is regional), and "nalla lorry" was called regional in run 0 (it is one company's truck). The deterministic entity filter put every item in the right place. **Lesson: decide privacy with rules, not with the model's label.**
  - **Self-improvement (A):** unwritten-knowledge tasks went from 0% to 100% (8/8), and the unsafe Jangaon assignment went from 2 to 0.
  - **Transfer (B):** regional tasks went from 0% to 100% (8/8), and the unsafe Jangaon assignments went from 4 to 0. B-private stayed at 0% in both arms, as expected (the pack can't contain B's own nicknames). Leak runs: 0.
  - **Regressions:** one double booking in each knowledge arm. In A-self R3#0 it assigned booked V05, then also V02. In B-pack BX1#0 it assigned booked B04 after listing assignments. Neither relates to the learned items (the Khammam habit was never in the pack), but both happened only with the longer prompt (2/58 runs with knowledge vs 0/58 without). Watch this; a pre-assign check in the harness would catch it.
- **Verdict (rule fixed above):** **self-improvement shown** (A tacit 100% ≥ 75%; control + strategy 23/24 vs 24/24, within 1 run). **Transfer shown** (B regional +100 points ≥ 50; control + strategy + spurious 13/14 vs 14/14, within 1 run; leaks 0). **Caveat (stated in advance):** the history is synthetic, with clean signals. This shows the mechanism works, not its real-world accuracy, and the habit trap was not tested by a live proposal.

### EXP-007: Do gated lessons beat plain retrieval over raw history? (frozen 2026-10-29 before any Muse call)
- **Question:** PRD v3.1 Arm B. EXP-006 compared "no knowledge" with "gated lessons", but never with simply giving the agent the raw trip history. If raw history works as well, the 0% → 100% result says nothing about the learning loop. Also: what happens if a second company gets the first company's raw history instead of the gated pack?
- **Frozen files:** `scripts/eval/exp007_raw_memory.py` (sha256 `79a5b76fe9d5a38b…`). Reused unchanged: `scripts/eval/exp006_transfer.py` (`0a629ad4d5d308ea…`: worlds, tasks, Desk, checker, agent loop, leak tokens), `datasets/dispatch/exp006_history_A.csv` (`19323da13dd71e53…`), and the lessons/pack from `artifacts/dispatch/exp006_20261027_210135.json` (`4e05cc12f50e066e…`, mining repeat 0: 5 lessons, 3-item pack). Self-test OK.
- **Arms** (agent = Muse Spark Open on Baseten, temperature 0, 2 repeats; same 16 A tasks and 13 B tasks as EXP-006):
  - **A-cold**: no knowledge.
  - **A-raw-top8**: + the 8 history rows that best match the request (term-overlap retrieval). Self-test: top-8 contains the key evidence for T1 and T3 but **misses it for T2 and T4**, a known weakness of simple lexical retrieval.
  - **A-raw-full**: + all 123 raw rows (~15k chars). The strongest raw-memory baseline: nothing is hidden, and the model must find the pattern itself.
  - **A-lessons**: + the 5 gated lessons.
  - **B-rawA**: company B + A's full raw history, labelled as another company's records (naive sharing).
  - **B-pack**: company B + the 3-item gated pack.
- **Leaks:** counted in what the agent *emits* (final reply + tool arguments). Prompt exposure (A-private tokens in B's prompt) is reported separately; for B-rawA it is non-zero by construction.
- **My prediction, stated now:** this history is small and clean, so **A-raw-full will probably match A-lessons** on tacit tasks. If so, that is an honest negative for "lessons beat retrieval" *on clean data*, and the real test moves to the Layer 1 data with misleading notes.
- **Primary metric:** A tacit pass rate (T1–T4, 8 runs per arm).
- **Decision rule (fixed now):**
  - **Lessons add value beyond raw memory** if A-lessons tacit ≥ 6/8 **and** A-raw-full tacit ≤ 4/8.
  - **Raw memory suffices on this data** if A-raw-full tacit ≥ 6/8. Then the claim must not be "lessons beat retrieval" on accuracy; it becomes: same accuracy with a short, reviewable, shareable prompt, plus governance (habits, stale rules, privacy). Layer 1 data must include stale notes, one-off failures, habits and contradictions, and Arm B vs C is decided there.
  - **In between** (5/8): inconclusive; same Layer 1 action.
  - **Sharing:** naive sharing is unsafe if B-rawA has any emitted leak **or** any unknown/foreign vehicle id assigned. Report B-rawA vs B-pack regional pass and leak runs either way.
  - Also report: control + strategy regressions vs A-cold (≥ 2 runs is a regression), tacit-unsafe runs, cost and mean prompt size per arm.
- **Budget:** 180 runs, est. $4–6 Baseten.
