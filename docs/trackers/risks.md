---
tags: [tracker, risks]
---
# Risk register (live)

Review at the end of each day. Close a risk when it can no longer happen.
**Likelihood/Impact:** H / M / L · **Status:** open / watching / closed / happened

| ID | Risk | L | I | Mitigation | Trigger to act | Owner | Status |
|---|---|---|---|---|---|---|---|
| R-01 | Muse tool calling or Telugu handling not good enough | L | H | Day-1 smoke tests passed (T2/T3/T4b/T5) | Regressions at scale | me | watching |
| R-02 | Muse Voice Transcribe can't handle Telugu | L | M | Telugu officially supported; gated on T6 | T6 fails | me | watching |
| R-03 | BigTool shows no accuracy gain | M | M | Efficiency framing pre-registered (D-007) | Arm B ≈ arm A | me | open |
| R-04 | No real improvement on held-out tasks | M | H | Honest reporting; show the transparent rejection | Day-6 probe flat | me | open |
| R-05 | Benchmark leakage / overfitting | M | H | Locked held-out hash; paraphrases kept separate | Proposer sees expected answers | me | open |
| R-06 | 40 tools dilute quality | M | M | Template + contract tests; fallback to 25 | Day-4 tests failing | me | open |
| R-07 | Credits run out | L | H | Ledger, caps, mock mode | >15% in a day | me | open |
| R-08 | Hosted demo abused or overspends | M | M | Global spend cap, rate limit, replay as default | Unusual spend | me | open |
| R-09 | Demo not reproducible | M | H | Seeded data, replay artifacts, Day-7 freeze | Fresh install fails | me | open |
| R-10 | Originality / rules challenge | L | H | Daily commits, README provenance section, fictional assets | — | me | open |
| R-11 | Secrets or personal info committed | L | H | `.gitignore` for `.env` + `Hackathon_info/`; pre-commit check | — | me | open |
| R-12 | Solo-developer fatigue | M | M | Day-3 checkpoint, cut order, buffer day | Two gates slip | me | open |
| R-13 | Daylight saving shift (Nov 1) causes a missed session or the deadline | L | H | All times in IST in [[day_plan]] | — | me | open |
| R-14 | Git identity uses a work email (`prashanth@sims.healthcare`) | L | M | Repo-local config set to the personal email (D-015) | — | me | closed |
| R-15 | Muse picks the wrong tool or misses one when it can't be forced (`tool_choice` is `auto` only) | M | M | Graph-level turn limits and a verifier; harness patches | Benchmark failures | me | open |
