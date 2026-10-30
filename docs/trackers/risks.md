---
tags: [tracker, risks]
---
# Risk register (live)

Review at the end of each day. Close a risk when it can no longer happen.
**Likelihood/Impact:** H / M / L · **Status:** open / watching / closed / happened

| ID | Risk | L | I | Mitigation | Trigger to act | Status |
|---|---|---|---|---|---|---|
| R-01 | Muse tool calling or Telugu handling not good enough | L | H | EXP-001–006: 88–100% on language and tools | Regressions on new data | watching |
| R-02 | Muse Voice Transcribe weak on Telugu | L | M | T6 passed; voice is cut before core features | Layer 2.6 fails | watching |
| R-04 | No real improvement on sealed cases | M | H | EXP-008: 0/4 → 4/4 for T01 and the new company on the golden path; sealed benchmark still to come | Arm C ≈ Arm A | watching |
| R-23 | Mining precision below bar (0.73): plausible-but-wrong lessons pass the gate | M | M | EXP-009: sharper statistical gates (no hard-coding); reviewer stays in the loop | Precision < 0.85 after EXP-009 | closed: EXP-009b precision 0.90 on an unseen world, 0 traps |
| R-05 | Benchmark leakage / overfitting | M | H | Hidden rules separate; split by family and time; leakage scan | Proposer sees oracle | open |
| R-07 | Credits run out | L | H | [[cost_ledger]], mock mode, budget in [[build_plan]] | >$20 in a day | open |
| R-08 | Hosted demo abused or overspends | M | M | Spend cap, rate limit, replay default | Unusual spend | mitigated: replay default, 8 live runs/session, 60/day for the app, every live call behind one guard, deploy without keys (D-038) |
| R-09 | Demo not reproducible | M | H | Seeds, hashes, replay artifacts | Clean clone fails | mitigated: fresh clone rebuilds the identical world (same hashes); replay bundle |
| R-10 | Originality / rules challenge | L | H | Daily commits, attribution, fictional data | — | open |
| R-11 | Secrets or personal info committed | L | H | `.gitignore`, history scan before each push | — | watching |
| R-12 | Solo fatigue | M | M | Layers, Nov 1 checkpoint, cut order | Two gates slip | open |
| R-13 | Daylight saving shift (Nov 1) causes a missed session or deadline | L | H | All times in IST | — | open |
| R-14 | Git identity uses a work email | L | M | Repo-local config (D-015) | — | closed |
| R-15 | Muse picks the wrong tool (`tool_choice` auto only) | M | M | Graph limits, validator, Loop A patches | Benchmark failures | open |
| R-16 | **Raw-note retrieval (Arm B) matches learned lessons** | H | H | EXP-007: full raw history 8/8 = lessons 7/8 on clean data. Pitch = governance + sharing + cost; Layer 1 data adds noise and scale to test B vs C properly | B ≈ C on Layer 1 data | resolved: on noisy, larger data (EXP-011) lessons beat raw-note search by +55 pts |
| R-17 | **Scope too big for 6 days** (two loops, 100 cases, judge challenge) | H | H | Layers, Nov 1 checkpoint, cut order | Layer 3 not done by Nov 1 10 AM | open |
| R-18 | 100-case human review doesn't fit your time | H | M | Code-computed oracles; review a sample; publish the real count | <50 reviewed by Nov 2 noon | open |
| R-19 | Synthetic data looks fake to judges | M | H | World-first generator, noise, misleading habits, practitioner review | Pilot review flags it | open |
| R-20 | Unverified citations in PRD (Harness², arXiv) | M | H | All 4 verified 2026-10-29 (questions I-05) | — | closed |
| R-21 | Over-cautious lessons (warnings everywhere) make the agent useless | M | M | Measure warning rate and task success together | Many advisories, low success | open |
| R-22 | Multi-schema adapters take longer than planned | M | M | Same contract tests; drop to 2 adapters if needed | Layer 2.1 > 1 day | open |
| R-24 | Model-written query escapes its limits, reads other data, or hangs the app (D-040) | M | H | SQL only, never Python; in-memory copy of the company's own tables; query_only + SELECT-only authorizer; 2 s / 200 rows / 4 kB caps; a test for each | Any sandbox test fails | open |
| R-25 | New features (Logs, new tools, nightly review) eat video day | M | H | Cut order in [[implementation_plan]] §5; Nov 3 reserved for the video | C not done by Nov 1 night | open |
| R-26 | "Learns new tools" / "learns from its runs" claimed as measured when only shown | M | H | Pre-register EXP-012, or say "shown working"; D-038 separates the measured commits | Any claim without an experiment row | open |
| R-27 | `run_query` changes measured behaviour (the agent writes SQL instead of using the right tool) | M | M | Off in frozen configs; "use other tools first"; Loop A flags wrong tool; visible on the Logs page | Gap-question runs use SQL for questions a tool answers | open |
| R-28 | Hosted demo state leaks between visitors | M | M | Per-session runtime and lesson store; harness decisions local-only (D-038); AppTest isolation test | — | mitigated |

Closed from the order-desk plan: R-03 (BigTool gain), R-06 (40 tools dilute quality); no longer applicable.
