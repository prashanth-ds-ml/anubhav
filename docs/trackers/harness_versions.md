---
tags: [tracker, harness]
---
# Harness versions and corrections (Loop A)

Loop A: the agent improves *how it uses its tools*. Each row is one candidate, from failure to human decision. Business lessons (Loop B) live in [[lessons]]. Method inspired by Harness² Propose–Probe–Compose (PRD v3.1 §8; citation to be verified, Layer 0.2).
**Allowed surfaces:** tool descriptions/examples · retrieval tags · Telugu/Roman-Telugu aliases · workflow sequencing hints · clarification templates · memory-selection guidance · response format.
**Forbidden:** auth, authorization, tenant selectors, the validator, the benchmark, hidden answers, data rows, secrets, executable code, new MCP permissions, model weights.

**Built 2026-10-29:** `src/anubhav/harness/` (store, loop) and the app's Tuning page. Versions live in `data/harness/harness.sqlite`; this page records the notable ones for the README and demo.

## Active version
- **Current:** `h-000` (baseline) for the app. In EXP-013, `analyst-001` and `tool_forge-001` passed their paired tests and were approved by a fixed rule in the experiment's own store; neither is active in the app, and neither improved answers on the test set
- **Model (frozen):** `meta-models/muse-spark-open-1026` (agent) · patches proposed by `muse-spark-1.3` · temperature `0`

## Version history
| Version | Date | Parent | Surface | Change summary | Approved by | Status |
|---|---|---|---|---|---|---|
| h-000 | 2026-10-29 | – | – | Baseline harness | system | active |
| h-001 | 2026-10-29 | h-000 | response_guidelines | Proposed after tool practice: "the agent called the right tool but the reply didn't match the records" | – | **not activated**: paired test failed (no measurable improvement; held-out 100% → no room), EXP-010 |
| h-002 | 2026-10-29 | h-000 | tool_hints | Proposed from traces: 9–10 calls per single-order draft; route straight to the valid draft | – | candidate, never tested (superseded by the D-037 tools: plan_board, check_load) |

## Candidate corrections
| C-ID | From failure (run_id / E-ID) | Root-cause class | Surface | Patch (diff link) | Targeted fixed? | Paraphrase probes pass | Regressions | Held-out Δ | Cost/latency Δ | Decision | → Version |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | ⬜ approve / ⬜ reject | |

**Root-cause classes:** retrieval-miss · wrong-tool · bad-args · multilingual-misread · sequencing · data-issue · policy-attempt

## Promotion checklist (every candidate)
- [ ] Targeted failure fixed
- [ ] Zero critical safety failures
- [ ] No new high-priority regressions
- [ ] No meaningful held-out drop
- [ ] Cost and latency change shown
- [ ] Human approval recorded
- [ ] Rollback tested

---
## Candidate details
