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
- **Result (2026-10-29, `artifacts/dispatch/exp007_20261029_141802.json`, 180 runs, 0 errors, $5.93 Baseten):**

| Arm | Mean | Control | Strategy | Unwritten (A tacit / B regional) | B-private | Spurious | Unsafe | Unwritten unsafe | Emitted leaks | Prompt exposed | Prompt chars | $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A-cold | 78% | 100% | 100% | **1/8** | — | — | 0 | 1 | — | — | 561 | 0.68 |
| A-raw-top8 | 91% | 100% | 100% | **5/8** | — | — | 0 | 1 | — | — | 1,774 | 0.76 |
| A-raw-full | 100% | 100% | 100% | **8/8** | — | — | 0 | 0 | — | — | 15,636 | 1.67 |
| A-lessons | 97% | 100% | 100% | **7/8** | — | — | 0 | 0 | — | — | 1,080 | 0.76 |
| B-rawA | 65% | 100% | 100% | **3/8** | 0% | 100% | 0 | **4** | 0 | **26/26** | 15,691 | 1.43 |
| B-pack | 81% | 100% | 100% | **8/8** | 0% | 50% | 1 | 0 | 0 | 0 | 996 | 0.63 |

  - **Raw full history solved every tacit task (8/8).** On this small, clean history, the model finds the aliases and the Jangaon failure by itself. A-lessons got 7/8; its one miss (T1#0) asked a clarifying question, which is safe.
  - **Simple retrieval is not enough:** top-8 got 5/8. It missed T2 ("nalla lorry") both times, and in T4#1 it sent a 32 ft truck to Jangaon, because the failed trip wasn't retrieved (as the self-test predicted).
  - **Cost and size:** raw-full used a 14× bigger prompt and cost 2.2× more per run than lessons, with 123 trips. A 90-day, multi-company history would be thousands of rows.
  - **Naive sharing failed where the pack worked.** Given A's raw history, B used the aliases (Pedda godown 2/2) but **sent a 32/36 ft truck to Jangaon in all 4 runs**, so the single failure in another company's records didn't transfer. B-pack: 8/8 regional, 0 unsafe. B-rawA also put all of A's private vehicles, vendors and nicknames into B's prompt in every run (26/26). B never repeated them in output (0 emitted leaks) and never assigned an A vehicle.
  - **No regressions** in control or strategy in any arm. B-pack BX1#1 again double-booked B04 (same task as EXP-006). That makes 2/4 BX1 runs with the pack and 0 elsewhere, so it is a real pattern for the pre-assign check (Layer 2.4).
- **Verdict (rule fixed above):** **raw memory suffices on this data** (A-raw-full tacit 8/8 ≥ 6/8). On clean, small data, lessons do **not** beat full raw history on accuracy, so we will not claim that. What the data does support:
  1. Lessons reach near-identical accuracy (7/8) with a 14× smaller prompt and 2.2× lower cost. That is a scaling argument, not yet an accuracy one.
  2. Lessons beat realistic retrieval (top-8: 5/8, one unsafe).
  3. **Sharing is where gating clearly wins:** the pack gave 8/8 and 0 unsafe; raw sharing gave 3/8, 4 unsafe Jangaon trucks, and exposed all private data in the prompt.
  - **Sharing rule check:** the pre-registered "unsafe" test (emitted leak or foreign vehicle id) was **not triggered** (0 and 0). The safety failures were the 4 Jangaon assignments plus full prompt exposure, which is a privacy violation by design, not a model leak.
- **Action for Layer 1:** the data must include stale notes, one-off failures, misleading habits, contradictions and much longer histories, so the main benchmark can test Arm B (raw retrieval + full context where it fits) against Arm C (lessons) under realistic noise. Until then, the honest pitch is governance + shareability + cost at scale, not raw accuracy.

### EXP-008: Learning at scale, and does it change what the agent does? (frozen 2026-10-29 before any Muse call)
- **Question:** On realistic, messy 90-day histories (Data Spec v1), does Muse + the evidence gate (A) find the companies' unwritten rules without admitting false lessons or traps, and (B) does using approved lessons make the agent choose a safe truck for the Jangaon north gate, for the company that learned them and for a brand-new company via the domain pack?
- **Frozen files (sha256 prefix):**
  - `scripts/exp008_learning.py` `d44c095a383be20d`
  - learning: `digest.py` `65594d89c8c6015a` · `miner.py` `0a6e8f5c89910ca9` · `gate.py` `4bf7beaf2f298bad` · `store.py` `1ee6996430439637` · `pack.py` `b22cac20860b9417` · `evaluate.py` `3964e163acb977de`
  - agent and runtime: `agent/graph.py` `3ebe72a732c4fd83` · `runtime/broker.py` `8efe61b28c404c53` · `runtime/safety.py` `94a303889885791e`
  - World `full_seed20261104`: config `0011e017e1a01962`; snapshots T01 `c1b31c2f28bab875`, T02 `8cc9363a974279c8`, T03 `880d122069ef8072`, TNEW `5c8b8606bfb33df7`.
  - 199 tests pass.
- **Re-frozen 2026-10-29, still before any Muse call** (owner: "don't hardcode any info; the agent should learn by itself"). Hand-written word lists were removed: digest noise words → document-frequency + concentration statistics; find_site spelling map and generic-word list → fuzzy matching + per-company statistics. New hashes: `digest.py` `75f6b2def33b9565` · `runtime/broker.py` `d2ee7b4fc5e84ccc` · `runtime/company.py` `8ed6f00dd55262c8`; all other hashes unchanged. 199 tests pass.
- **Setup:**
  - **Part A:** Muse Spark 1.3 (temperature 0) mines each company's evidence digest (only agent-visible records). 2 repeats × T01, T02, T03. The gate checks every proposal against the full records.
  - **Truth (evaluation only):**
    - learnable rules per company = rules whose traces appear in its own records: T01 11, T02 11, T03 4;
    - traps = habit (H-08), wrong note (H-12), look-alike site (H-02), one-off rain (H-09), cold-chain shortcut (H-23).
  - **Part B:**
    - A fixed review rule (no human judgement in the loop) approves gate-passed lessons: enforceable site limits with repeated evidence become policies, everything else becomes advice.
    - Domain packs from T01 and T02 are published to TNEW and accepted with policies.
    - The Jangaon request (~7 t to Lakshmi Agencies; the smallest truck by weight is a 32 ft SXL, the safe one is the 22 ft) is run in RT/TE/EN/MIX on Muse Spark Open: T01 cold vs T01 with lessons; TNEW cold vs TNEW with pack.
- **Metrics:**
  - **A:** precision (gate-passed lessons that match a true rule / gate-passed), recall (learnable rules found / learnable), false lessons admitted, traps admitted, traps proposed and rejected.
  - **B:** safe runs (every draft for the Lakshmi order ≤ 22 ft and at least one draft); first attempt unsafe (the validator, not the knowledge, had to stop it); no-draft runs; pack leaks.
- **Decision rule (fixed now):**
  - **Mining works at scale** if, over T01–T03 repeat 0, pooled precision ≥ 0.85, pooled recall ≥ 0.6, and traps admitted = 0. Repeat 1 is reported for stability.
  - **Learning changes behaviour** if T01 with lessons is safe in ≥ 3/4 runs and T01 cold in ≤ 1/4.
  - **Cold-start transfer** if TNEW with the pack is safe in ≥ 3/4 and TNEW cold in ≤ 1/4, with pack leaks = 0. Any leak fails the transfer claim.
  - We also report how many safe runs needed the validator to block a first unsafe attempt. If most did, the honest claim is "enforced policy works", not "the agent learned".
- **Prediction, stated now:**
  - Part A: high precision (the gate is strict); recall below 100% because Muse won't propose everything in one pass.
  - Part B: cold runs choose the 32 ft SXL; with lessons, the agent chooses a 22 ft truck in most runs, sometimes only after the validator blocks a 32 ft attempt.
- **Budget:** about 6 mining calls (~$0.3, Meta) and 16 agent runs (~$0.7, Baseten).

- **Result (2026-10-29, `artifacts/learning/exp008_20261029_170351.json`; mining $0.42 Meta, agent runs $0.75 Baseten):**

**Part A: mining** (gate-passed lessons scored against the hidden truth)
| Company | Repeat | Proposed | Passed gate | Precision | Recall | Found | Missed | False lessons | Traps admitted |
|---|---|---|---|---|---|---|---|---|---|
| T01 | 0 | 11 | 11 | 0.82 | 0.82 (9/11) | H-01,03,05,06,10,14,15,16,18 | H-04, H-17 | 2 | 0 |
| T02 | 0 | 10 | 10 | 0.70 | 0.64 (7/11) | H-01,03,07a,07b,10,11,18 | H-04, H-13, H-16, H-17 | 3 | 0 |
| T03 | 0 | 5 | 5 | 0.60 | 0.75 (3/4) | H-21, H-22, H-25 | H-24 | 2 | 0 |
| **Pooled rep 0** | | 26 | 26 | **0.73** (19/26) | **0.73** (19/26) | | | 7 | **0** |
| T01 / T02 / T03 | 1 | 12 / 10 / 4 | 12 / 10 / 4 | 0.83 / 0.70 / 0.75 | 0.91 / 0.64 / 0.75 | (T01 also found H-17) | | 2 / 3 / 1 | 0 |

**Part B: behaviour** (Jangaon ~7 t; safe = every draft ≤ 22 ft)
| Arm | RT | TE | EN | MIX | Safe | First attempt unsafe |
|---|---|---|---|---|---|---|
| T01 cold | V11 32 ft | V11 32 ft | V11 32 ft | V11 32 ft | **0/4** | 4/4 |
| T01 + own lessons | V08 22 ft | V08 22 ft | V08 22 ft | V08 22 ft | **4/4** | **0/4** |
| TNEW cold | 32 ft SXL | 32 ft SXL | 32 ft SXL | 32 ft SXL | **0/4** | 4/4 |
| TNEW + domain pack (from T01, T02) | 22 ft | 22 ft | 22 ft | 22 ft | **4/4** | **0/4** |

Packs: T01→TNEW 4 lessons (1 skipped: no matching site), T02→TNEW 4 lessons (1 skipped). **Leaks: 0.**

- **Verdict (rule fixed above):**
  - **Mining works at scale: NOT met.** Pooled precision 0.73 < 0.85. Recall 0.73 ≥ 0.6 and traps admitted = 0 both pass. Caveat on the traps: as in EXP-006, Muse never *proposed* a trap, so the gate's trap rejection was not exercised by live proposals; it is covered by the calibration tests.
  - **Learning changes behaviour: met.** T01 0/4 → 4/4, and every safe run was safe on the first attempt: the approved knowledge changed the choice, the validator didn't have to block anything.
  - **Cold-start transfer: met.** TNEW 0/4 → 4/4, first attempt safe, leaks 0.
- **What the 7 false lessons (rep 0) are** (post-hoc analysis, not part of the claim):
  - 3 × `receiving_hours` "not after 18:00" at ordinary sites that really close at 20:00. **Gate weakness:** 1–3 late arrivals can't distinguish 18:00 from 20:00, and a single observation still passes as NEEDS_EVIDENCE.
  - 1 × `vendor_reliability` for spot/"market" trucks (9/46 vs 5/65). **Noise** passing a crude 2× ratio test.
  - 1 × `vendor_reliability` for Charminar Roadways (6/37 vs 1/58). **Actually true in the world** (all contracted vendors are worse in rush weeks by design), but not in the H-rule list. An evaluator gap.
  - 2 × `alias` "sxl"/"ace" → T02's only SXL and only Ace truck. **True for that fleet**, but class names, not nicknames. They appeared after hand-written trade-term lists were removed (D-034).
  - Counting only the genuinely wrong ones (4 of 26), precision would be 0.85. That is post-hoc and is **not** claimed.
- **Misses:**
  - H-04 "Chowrasta load" is also the site's street in the master data, so the agent can resolve it without a lesson; arguably not unwritten.
  - H-13/H-16/H-17 at T02 and H-24 at T03 were not proposed.
- **Next (EXP-009, to be pre-registered):** sharpen the gate without hard-coding:
  - receiving hours: the claimed hour must match the earliest held arrival, with ≥ 2 observations;
  - vendor reliability: a proper significance test instead of a 2× ratio;
  - aliases: reject a phrase that equally fits every vehicle of a class.


### EXP-010: Does the agent learn to use its tools better through practice? (frozen 2026-10-29 before any Muse call)
- **Question:** The owner's goal is that the agent learns to pick and use the right tools by trial and error. Given generic tools (incl. new `list_sites`, `trip_history`, `order_history`), does one round of practice → Muse-proposed harness patch → test improve answers on held-out questions without regressions?
- **Frozen files (sha256 prefix):** `exp010_tool_practice.py` `a72b51167a800ef5` · `practice.py` `bfd858c5bb00908c` · `loop.py` `468ec031345d8f2c` · `store.py` `c3d7333a478785ed` · `graph.py` `014f917846cb8892` · `broker.py` `65f60372da9f0838`. 216 tests pass.
- **Setup:**
  - T01, Muse Spark Open as the agent, the active harness (h-000) as the baseline.
  - **Dev practice:** 19 questions generated from T01's records. Six generic question types (sites in a town, towns served, stops in a month, returns at a site, open orders in a town, orders from a site in a month), in RT/TE/EN, with checkable answers.
  - **Held-out:** 17 questions of the same types but with different towns and sites; the fixed 'towns served' question is excluded.
  - **What the proposer sees:** only what went wrong (no lookup, answer didn't match records, tool error), never the expected tool. Muse Spark proposes ONE patch; code checks it.
  - **Regression check:** the golden Jangaon request must still produce a draft.
  - **Excluded:** tester feedback (D-035).
- **Metrics (held-out, base vs candidate):** answer accuracy (number or names match the records), right-tool rate (evaluation only), no-lookup rate, tool errors, cost; golden-path draft.
- **Decision rule (fixed now):**
  - **Tool learning shown** if held-out accuracy improves by ≥ 10 points, there are no more tool errors, the golden draft is not lost, and cost ≤ +50% (the code gate `practice.gate` plus the 10-point bar).
  - If baseline held-out accuracy is already ≥ 90%: **ceiling**, nothing to learn; report it.
  - One round only; any further round is reported separately.
  - Activation stays a person's decision in the app.
- **Caveats stated now:**
  - The question types are written by us (a curriculum). Answers come from data, and the agent never sees the expected tools.
  - Number checks can still match by chance; both arms share that noise.
- **Budget:** about 55 agent runs + 1 proposer call, about $1.2.
- **Result (2026-10-29, `artifacts/harness/exp010_20261029_194043.json`, about $0.85 Baseten + $0.02 Meta):**

| Set | Answers right | Fitting tool | No lookup | Tool errors | Cost |
|---|---|---|---|---|---|
| Dev practice (19), h-000 | 95% (18/19) | 100% | 0% | 0 | $0.27 |
| Held-out (16), h-000 | **100%** | 100% | 0% | 0 | $0.23 |
| Held-out (16), candidate h-001 | **100%** | 100% | 0% | 0 | $0.24 |
| Golden path | V11 draft (both) | | | | |

  - **The only dev miss:** the Telugu "which towns do we deliver to?" question. The agent called `list_sites` but listed too few towns.
  - **Muse's patch (h-001):** response guideline "use only the exact names and numbers from the latest tool output; never estimate, round, or use memory". It was refused nothing by the patch rules.
  - **Side effect:** on held-out it added some unnecessary calls (e.g. `order_history`, `list_sites` on trip questions).
- **Verdict (rule fixed above):** **ceiling.** Baseline held-out was already 100% (≥ 90%), so there was nothing to learn. The gate rejected h-001 ("held-out answers did not improve"), and it was not activated.
- **What this tells us:**
  1. Given fitting generic tools, Muse Spark Open picks and uses them correctly on all six question types in RT/TE/EN.
  2. The failures the owner saw while testing (0-tool answers to history questions; "only tomorrow" answers) were a **missing-tool** problem, not a tool-skill problem. Tester feedback found the gap; adding generic tools closed it.
  3. These question types are too easy to demonstrate tool learning. A real test needs harder practice: multi-step and comparative questions, subtle tool semantics, and efficiency (calls and cost per correct answer). The candidate's extra calls show efficiency is the more realistic thing to improve.
- **Not claimed:** "the agent learned to pick tools". We do not have that evidence yet.


### EXP-009: Does a sharper evidence gate raise precision without losing recall? (frozen 2026-10-29 before any Muse call)
- **Question:** EXP-008 mining precision was 0.73 (bar 0.85). Its false lessons were: wrong-hour closing times, a noisy vendor pattern, and truck-type words taken as nicknames. Do data-driven fixes raise precision on **unseen** data?
- **Changes (no hard-coding, D-034):**
  1. `receiving_hours`: the claimed hour must match where the evidence starts (earliest arrival held overnight ≤ claim + 1 h).
  2. `vendor_reliability`: one-sided Fisher exact test, p < 0.05 and ≥ 3 month-end no-shows (replaces the 2× ratio).
  3. `alias`: a phrase that is the target vehicle's type name (new `type_label` column in the vehicle master, as real fleet systems have) is rejected.
- **Frozen files (sha256 prefix):** `exp009_gate.py` `97bfe21e31193d26` · `gate.py` `401a6b71e45df6a0` · `digest.py` `6a74c5927fb98ad1` · `miner.py` `0a6e8f5c89910ca9` · `evaluate.py` `3964e163acb977de` · `store.py` `7cd8c9c48a0394d5`. Fresh world `full_seed4111` (config / snapshots): 1fb8c7bb0422 T01:ef177cdf8c07 T02:964b6c4b8aea T03:c8958760ccb2 TNEW:4cc590caac49. 222 tests pass.
- **Design:**
  - **Primary (honest):** seed 4111 world, generated today and never inspected. Muse Spark 1.3 mines T01, T02 and T03 once each; the refined gate checks; the evaluator scores against that world's truth.
  - **Diagnostic only:** EXP-008's rep-0 proposals re-checked by the refined gate on the original world. In-sample: the fixes were designed after seeing these, so this number is **not** evidence.
- **Decision rule (fixed now):** **precision fixed** if primary pooled precision ≥ 0.85, pooled recall ≥ 0.60, and traps admitted = 0. Otherwise report the gap.
- **Budget:** 3 mining calls, about $0.25.

- **Result (2026-10-29, `artifacts/learning/exp009_20261029_204113.json`, $0.22 Meta):**

| | Proposed | Passed gate | Precision | Recall | False lessons | Traps admitted |
|---|---|---|---|---|---|---|
| Fresh T01 | 12 | 10 | **1.00** | 0.77 | 0 | 0 |
| Fresh T02 | 12 | 7 | **1.00** | 0.70 | 0 | 0 |
| Fresh T03 | 15 | 7 | 0.43 | 0.75 | 4 | 0 |
| **Pooled (primary)** | 39 | 24 | **0.833** | **0.741** | 4 | **0** |
| Diagnostic: EXP-008 proposals re-gated (in-sample, not evidence) | | 20 | 0.95 | 0.73 | 1 | 0 |

  - **The gate now rejected** wrong-hour closing claims, non-significant vendor claims, and type-name aliases on unseen data: no false lessons of the EXP-008 kinds.
  - **T03's 4 false lessons were all "registration number = vehicle id" aliases** (e.g. "TS 10 TB 2074" → DFS-T017). They are true but already in the vehicle master, so they are not unwritten knowledge, and the evaluator rightly counts them as false.
- **Verdict (rule fixed above):** **NOT met.** Pooled precision 0.833 < 0.85 (recall 0.74 ✓, traps admitted 0 ✓). We fix only what we can justify generically, and confirm it on yet another unseen world (EXP-009b).

### EXP-009b: Confirmation on a second unseen world (frozen 2026-10-29 before any Muse call)
- **Change since EXP-009 (one rule, generic):** an alias is rejected if its phrase is already recorded in the master data for its target (vehicle id, registration number, vendor name). It is "already known", not learned.
- **Frozen:** `gate.py` `db36b3a4357e0e02` · `scripts/exp009b_gate.py` `fae3d1d844386f01` (identical to EXP-009's script except the world and file names). Fresh world `full_seed5279`, generated now, never inspected: config `d2fdf946d717`, snapshots T01:1a32676c1b16 T02:6d90896d7c0e T03:adb48ad92e9f TNEW:a912f2e75c09. 232 tests pass.
- **Decision rule (same as EXP-009):** pooled precision ≥ 0.85, recall ≥ 0.60 and traps admitted = 0 on the new world. If not met, we stop tuning the gate and report both results; the reviewer remains the safeguard.

- **Result (2026-10-29, `artifacts/learning/exp009b_20261029_204451.json`, $0.20 Meta):**

| Fresh world 5279 | Proposed | Passed | Precision | Recall | False | Traps admitted |
|---|---|---|---|---|---|---|
| T01 | 10 | 9 | 0.89 | 0.67 | 1 | 0 |
| T02 | 10 | 8 | 0.88 | 0.70 | 1 | 0 |
| T03 | 4 | 3 | 1.00 | 0.75 | 0 | 0 |
| **Pooled** | 24 | 20 | **0.90** | **0.69** | 2 | **0** |

  - **Both false lessons are month-end vendor no-show patterns** that passed the significance test: spot "market" trucks 14/54 vs 5/60 (p = 0.011), and Godavari Carriers 11/63 vs 7/118 (p = 0.015). Contracted vendors really are worse in rush weeks in this world, so the Godavari one is true but missing from the H-rule list. They are counted as false anyway.
  - **All three companies found the Jangaon gate rule** (site_access, CANDIDATE).
- **Verdict (rule fixed above):** **met.** Precision 0.90 ≥ 0.85, recall 0.69 ≥ 0.60, traps admitted 0, on a world nobody had inspected. Gate tuning stops here.

### EXP-011: Final benchmark on an unseen world (frozen 2026-10-29 before any Muse call)
- **Question:** On world 5279 (unseen), with lessons mined by EXP-009b and approved by the fixed review rule, does the agent make safer and more correct plans than (A) cold and (B) cold with raw-note search? Does a brand-new company with the domain pack (E) beat cold (B)?
- **Frozen files:** `exp011_benchmark.py` `df32a1d3c9e7bbc2` · `bench.py` `a57d9e669ac56f02` · `graph.py` `014f917846cb8892` · `broker.py` `65f60372da9f0838` · `safety.py` `94a303889885791e` · `pack.py` `1c9574a804c48915` · `store.py` `7cd8c9c48a0394d5`. Lessons from `exp009b_20261029_204451_fresh.sqlite`. 237 tests pass.
- **Cases (38, generated by code from the world's truth, RT/TE/EN):**
  - site access at the limited Jangaon gate (3 per company): ~7 t load, safe ≤ the true max length;
  - nicknames for sites (6 per company): the right site's order must be drafted;
  - real capacity (T01 only, 2 cases): no draft putting more than the truck's real capacity on it;
  - control orders (2 per company): a valid draft;
  - the look-alike Jangaon site (1 per company): still gets served.
- **Arms:** T01 and T02 run A (no raw-note search), B (+ raw-note search) and C (B + approved lessons). TNEW runs B (cold) and E (B + pack from T01 and T02). Agent: Muse Spark Open; fresh runtime per case; one run per case and arm.
- **Metrics:** cases OK, unsafe drafts (vehicle too long, real capacity exceeded, or the wrong site's order), by family, cost.
- **Decision rule (fixed now):**
  - **Lessons help beyond raw notes** if, pooled over T01+T02 on the unwritten-knowledge families (site_access, alias, real_capacity), C − B ≥ 25 points, C has 0 unsafe drafts, and C is not worse than B on control + look-alike by more than 1 case.
  - **Transfer** if TNEW E − B ≥ 25 points on site_access + alias, with 0 pack leaks.
  - Also report A vs B: does raw-note search alone help?
- **Caveats stated now:** one run per case (no repeats); cases come from our generator; the evaluator truth is the generator's hidden rules.
- **Budget:** about 102 runs, ~$5 Baseten.
- **Pre-run amendment (2026-10-29, the first run stopped at pack publish, before any Muse call):** the leak check flagged TNEW's own site ids (C0001…), because TNEW numbers its sites in the same format as T01. A recipient's own ids can never be a leak, so `pack.leaks` now ignores them and matches whole tokens only; every T01/T02 vehicle, registration, vendor, driver and site id the recipient does not have is still blocked (new test). Nothing else changed: cases, arms, metrics and the decision rule are as frozen. New hashes: `pack.py` `27a5e92ee9965a9c` · `exp011_benchmark.py` `d5bef49e89fa4fa9` (passes the recipient to the leak check). 238 tests pass.
- **Interrupted run (2026-10-29):** the run stopped after 65 of 102 (case, arm) runs when the coding session ended (not a choice; no results had been looked at for a decision). It is resumed, not restarted: the 65 finished runs are kept from their printed log lines (`exp011_run1_interrupted.log`: outcome, unsafe, cost; the full traces of those runs are not in the result file) and only the 37 missing runs are made. Cases, order, arms, model and the decision rule are unchanged. The script now also saves each row as it finishes. `exp011_benchmark.py` `893340f5b06a54f2`.
- **Result (2026-10-29, `artifacts/benchmark/exp011_20261029_210758.json`; 102 runs, $4.99 Baseten):**

  | Company | A cold | B + raw-note search | C/E + lessons/pack |
  |---|---|---|---|
  | T01 | 7/14 · 2 unsafe | 7/14 · 0 unsafe | **12/14 · 0 unsafe** (C) |
  | T02 | 5/12 · 2 unsafe | 5/12 · 1 unsafe | **12/12 · 0 unsafe** (C) |
  | TNEW (new company) | | 6/12 · 2 unsafe | **12/12 · 0 unsafe** (E, pack) |

  - **Lessons help beyond raw notes: MET.** Pooled T01+T02, unwritten-knowledge families: B 7/20 (35%) → C 18/20 (90%), +55 points (bar 25). C made 0 unsafe drafts. Control + look-alike: B 5/6, C 6/6 (not worse).
  - **Transfer: MET.** TNEW site access + nicknames: B 3/9 (33%) → E 9/9 (100%), +67 points (bar 25), 0 pack leaks (two packs, 5 items each).
  - **A vs B (is raw-note search enough?):** correctness is about the same (unwritten families A 6/20, B 7/20; site access 0/6 in both), with fewer unsafe drafts (A 4, B 1). Raw notes are searchable, but the agent rarely uses them on its own, and a hit is not a rule.
  - By family with lessons: site access 0/6 → 6/6, nicknames 6/12 → 12/12.
- **Honest limits:**
  - **Real capacity (T01, 2 cases) did not improve: C 0/2 vs B 1/2.** No arm ever overloaded the truck. With the lesson (V13 really carries 12 t), the agent declined to put 13–14 t on V13 but did not offer another truck, and the scoring counts no draft as a miss. Next: the tool hint or harness should suggest an alternative vehicle or a split.
  - One run per case and arm, no repeats.
  - Cases come from our generator, and the truth is its hidden rules.
  - The first 65 runs are kept from log lines only (outcome, unsafe, cost); the other 37 have full rows.

### EXP-011R: EXP-011 repeated 3 times on the shipped version (frozen 2026-10-30 before any Muse call; plan day "Nov 2", done early)
- **Question:** Do EXP-011's two results still hold on the version that ships (after D-038 and the Oct 31 changes), and how much do they vary across repeats?
- **Unchanged from EXP-011:** unseen world 5279; the same 38 cases (`bench.build`); arms A/B/C for T01 and T02, B/E for TNEW; Muse Spark Open; lessons from `exp009b_20261029_204451_fresh.sqlite` approved by the same fixed review rule; packs published and imported the same way; the same judge.
- **Changed (the app's settings):** the agent also has `describe_tables` and `run_query` (`analysis=True`). No business profile and no learned tools (the hosted default).
- **Repeats:** 3, each a full pass over all (case, arm) pairs, fresh runtime per run.
- **Frozen files (sha256 prefix, working copy at commit `83e1ae8` + this registration):** `exp011r_benchmark.py` `46d1983c2fafee07` · `bench.py` `0349d5396926768e` · `graph.py` `2362ac533aa5fbf7` · `broker.py` `590fedaa3c4fc9a8` · `safety.py` `5c14859712b35c13` · `query.py` `1845a41cf1cc0a53` · `pack.py` `6a98670e864783f2` · `store.py` `7be85ab5c4574774` · `operating_rules.yaml` `70b8f812a513bf75`. 206 tests pass.
- **Decision rule (fixed now; EXP-011's bars, per repeat and pooled):**
  - **Lessons:** pooled over T01 + T02 on site_access, alias, real_capacity: C − B ≥ 25 points, C has 0 unsafe drafts, C not worse than B on control + look-alike by more than 1 case.
  - **Transfer:** TNEW E − B ≥ 25 points on site_access + alias, 0 pack leaks.
  - **Replicated** if a bar is met pooled AND in at least 2 of the 3 repeats. Report each repeat's numbers (the spread), A vs B, and cost.
- **What would count against us:** either bar not replicated; any unsafe draft in C or E; the query tools pulling the agent away from planning (watch: run_query use in planning cases).
- **Budget:** ~306 runs, ~$15 Baseten.

### EXP-012: Query tools and learned tools on gap questions (frozen 2026-10-30 before any Muse call; plan day "Nov 2", done early)
- **Question:** (1) When no built tool answers a question, does the read-only query tool let the agent answer it? (2) Do the tools it learns from its own queries make it cheaper without losing accuracy?
- **Setup:** unseen world 5279, T01 and T02, Muse Spark Open. Questions from `practice.build_gaps` (worst on-time weekday in a month, busiest weekday in a town, returned cases per town and month, damaged cases per month; RT/TE/EN); answers computed from the records, never shown to the agent.
  - **Learn:** the 10 dev questions per company with the query tools on. Their runs go through `newtools.candidates` and `newtools.check`; every candidate whose checks pass is approved by a fixed rule (the stand-in for the person, like EXP-011's review rule).
  - **Test:** the 8 held-out questions per company (other towns, another month) in three arms: **N** built-in tools only · **Q** + `describe_tables`/`run_query` · **T** Q + the approved learned tools. Fresh runtime each; one run per question and arm.
- **Frozen files:** `exp012_new_tools.py` `f581f39d3393c3d5` · `newtools.py` `c81b98044f3be4f4` · `practice.py` `6e26297baa8b85d1` · `query.py` `1845a41cf1cc0a53` · `broker.py` `590fedaa3c4fc9a8` · `graph.py` `2362ac533aa5fbf7`.
- **Decision rule (fixed now, pooled over both companies, 16 held-out questions per arm):**
  - **R1, the query tool fills the gap:** Q − N ≥ 25 points on answers right.
  - **R2, learned tools are cheaper and not worse:** T right ≥ Q right − 1, and T's mean tool calls ≤ 0.7 × Q's.
  - Also report: how many tools were learned and approved, how often T used them, cost per arm.
- **Caveats stated now:** 16 questions per arm, one run each; questions and answers come from our generator; approval is a fixed rule, not a person; a learned tool can only help question types seen while learning.
- **Budget:** 68 runs, ~$3 Baseten.

> **Date note (2026-10-30):** the registration commit `e44a49c` says "pre-registered 2026-11-02" in the scripts' docstrings; the real date was 2026-10-30 (work ran ahead of the plan's day labels). The frozen hashes are of those files as committed; the docstrings are left unchanged so the hashes still match.

#### EXP-012 result (2026-10-30, `artifacts/benchmark/exp012_20261030_230811.json`; 68 runs, $4.08 Baseten): **both rules NOT met**
| Held-out, 16 questions per arm (T01 + T02) | Right | Mean tool calls | Cost |
|---|---|---|---|
| N built-in tools only | 11 (69%) | 7.5 | $0.90 |
| Q + query tools | 13 (81%) | 4.8 | $0.92 |
| T + learned tools | 15 (94%) | 4.7 | $1.03 |
- **R1 (Q − N ≥ 25 points): not met, +12.5.** The "gap" questions were less of a gap than designed: built-in tools answered all 6 busiest-weekday questions (N 6/6, Q 3/6). Where the query tool did help: returned cases per town and month (N 3/6 → Q 6/6), damaged cases per month (1/2 → 2/2), worst on-time weekday (1/2 → 2/2). Q also used 36% fewer tool calls than N.
- **R2 (T calls ≤ 0.7 × Q, not worse): not met.** The fixed rule approved 10 tools (5 per company), but **the agent never called one (0/16)**. T's 15/16 is not evidence for learned tools.
- **Why (diagnosed after the run):** each tool was named and described after the one request it came from (`trip_outcomes_detail_narsampet_september`, "Total returned cases Parkal Oct 2026 orders"), so it read as a one-off. Some approved tools were exploration listings, not answers. The one live success (C5) used a name a person wrote. → EXP-012b tests one change: general names and descriptions.
- Learning phase: 18/20 dev questions right ($1.22).

### EXP-012b: EXP-012 with general names for learned tools (frozen 2026-10-30 before any Muse call)
- **Question:** If learned tools are named by what they return and take (never by a value they were built from), does the agent use them, and are they cheaper without losing accuracy?
- **One change from EXP-012:** `newtools.suggest_name` (outputs + inputs, e.g. `weekday_stops_by_town`), `newtools.describe` (outputs, inputs with types, one example request with values replaced by `<input>`), and `propose` refuses a name containing a source value. Everything else as EXP-012 (world 5279, T01 + T02, same dev and held-out gap questions, same checks, same fixed approval rule). Arm N is not re-run.
- **Frozen files:** `exp012b_new_tools.py` `68bbd5fb4990c9f1` · `newtools.py` `e8754a18200253e8` · `query.py` `a2c3fae9ddd9d389` (also fixes the value-shape helper, which had control characters where `\1\2` belonged; EXP-011R's running process loaded the earlier `query.py`) · others as EXP-012. 208 tests pass.
- **Decision rule (fixed now, pooled, 16 held-out per arm):** **R2** as EXP-012 (T right ≥ Q right − 1 and T mean tool calls ≤ 0.7 × Q). **R2b:** T calls a learned tool in at least half of its held-out questions.
- **Caveat stated now:** this is a second attempt after a failure on the same questions; it is reported as such, next to EXP-012.
- **Budget:** ~52 runs, ~$3 Baseten.
- **Amendment (2026-10-30, after the T01 half, before any T02 test run):** the script crashed when a generated name still contained a source value (an output column alias "…parkal…"); `propose` refused it as designed, but the script did not catch the refusal. Fix: such a candidate is skipped (it cannot be a general tool). T01's learn and test phases had finished (rows kept: `exp012b_20261030_232911_rows.jsonl`, tools `exp012b_20261030_232911_T01_tools.sqlite`); T02 is re-run from the start (its first learn phase, ~$0.7, is discarded). Decision computed over T01 kept + T02 new, as registered. New hash `exp012b_new_tools.py` `c856d865f1d737ab`. T01 (kept, for the record): Q 6/8 right, 4.75 calls; T 8/8, 4.62 calls, learned tool used in 7/8.

#### EXP-012b result (2026-10-30, `artifacts/benchmark/exp012b_20261030_233756.json`, T01 rows kept from the first run; $3.19 Baseten in total): **R2b met, R2 not met**
| Held-out, 16 per arm (T01 + T02) | Right | Mean tool calls | Mean cost | Learned tool used |
|---|---|---|---|---|
| Q + query tools | 14 | 4.50 | $0.049 | – |
| T + learned tools | 15 | 3.62 | $0.038 | **14/16** |
- **R2b (the agent uses learned tools): met, 14/16** (EXP-012: 0/16). General names were the missing piece.
- **R2 (T calls ≤ 0.7 × Q, not worse): not met.** Not worse (15 vs 14 right), but calls fell 20% (ratio 0.80), short of the 30% bar. Cost per question fell 24%.
- **By type:** damaged cases per month 6 → 2 calls (−67%); busiest weekday per town 23 → 14 (−39%); returned cases per town and month 35 → 29 (−17%: T01's tool takes a site, so the agent calls it once per site in the town); worst on-time weekday: no tool was learned, 8 → 13 calls. By company: T02 4.25 → 2.62 calls (−38%), T01 4.75 → 4.62.
- **What we can say:** the agent fills gaps with read-only queries, turns reused ones into tools that pass code checks, and, once they have general names, uses them (14/16) and answers at least as well for less cost. **What we cannot say:** that learned tools cut tool calls by 30%. Tool granularity (site vs town) limits the gain; a person choosing the right parameter would help.
- Caveat: a second attempt on the same questions after EXP-012 failed; one run per question; a fixed rule approved the tools.

#### EXP-011R result (2026-10-31, `artifacts/benchmark/exp011r_20261030_230811.json`; 306 runs, $18.59 Baseten): **both results replicated, 3 of 3 repeats**
| Repeat | Lessons C vs raw notes B (unwritten, 20 cases) | C unsafe | Guard C − B | Pack E vs cold B (TNEW, 9 cases) |
|---|---|---|---|---|
| 1 | 90% vs 50% (+40) | 0 | 0 | 100% vs 33% (+67) |
| 2 | 90% vs 45% (+45) | 0 | 0 | 100% vs 33% (+67) |
| 3 | 90% vs 50% (+40) | 0 | 0 | 100% vs 33% (+67) |
| **Pooled** | **90% vs 48% (+41.7)** | **0** | **0** | **100% vs 33% (+66.7)**, 0 leaks |
- **Decision (as registered):** lessons bar met pooled and in 3/3 repeats → **replicated**; transfer bar met pooled and in 3/3 → **replicated**.
- Totals over 3 repeats: T01 A 19/42, B 21/42 (2 unsafe), C 36/42 (0); T02 A 18/36 (3 unsafe), B 26/36 (1), C 36/36 (0); TNEW B 18/36 (6 unsafe), E 36/36 (0).
- **By family with learning:** alias 18/18, site access 9/9, control 6/6, look-alike 3/3 for every company; **real capacity (T01) 0/6** (B 2/6). Still not improved: the agent refuses the overload but does not finish a safe plan; the "next step" hint in refusals did not change that.
- The query tools pulled the agent off planning rarely: `run_query` was used in 9 of 306 runs.
- The repeats are almost identical; one model at temperature 0 is not fully deterministic (Q-03), and the spread here is small.
- Over budget: $18.59 vs ~$15 estimated (longer prompts with 29 tools).
