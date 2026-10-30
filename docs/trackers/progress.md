---
tags: [tracker, progress]
---
# Progress tracker

**Overall:** ~80% (as of 2026-10-30 evening: build, learning loops and final benchmark done; audit step 1 fixes done and tested, not yet committed. Next: [[implementation_plan]] (Logs page, new-tool creation, nightly review), then deploy, video, submit)
Plan: [[build_plan]] · Status key: ⬜ pending · 🟨 in progress · ✅ done · ❌ blocked · ✂️ cut
History before Oct 29 (order-desk plan): `archive/progress_order_desk.md`

## Layers
| Layer | Dates (IST) | Focus | Gate | Status | Evidence |
|---|---|---|---|---|---|
| — | Oct 26–28 | Experiments EXP-001–006, interview, direction | Anubhav chosen (D-024) | ✅ | [[experiments]], [[Anubhav_overview]] |
| — | Oct 29 | Repo cleanup, rename, PRD v3.1 + blueprint, build plan | Repo `anubhav` pushed | ✅ | D-025–D-027 |
| 0 | Oct 29 | EXP-007 Arm B check, citations, project setup | Claim survives raw-note baseline; clean `uv sync` + `pytest` | ✅ (raw memory suffices on clean data → pitch reframed; citations verified; 159 tests pass) | [[experiments]] |
| 1 | Oct 29–30 | Data world: 3 companies + T-new, 90 days | Pilot then full, 0 integrity violations | ✅ generator + 31 tests; full 90-day world (seed, rebuilt from code in ~5 s); unseen worlds 4111 and 5279 for testing | [[data_and_benchmark]], [[Data_Spec_v1]] |
| 2 | Oct 29 | MCP, tenant broker, LangGraph, safety, traces, voice | Golden path live in EN/TE/RT/MIX | ✅ live golden path in RT/TE/EN/MIX + ambiguity on Muse Spark Open ($0.29); voice path works (Muse Voice Transcribe); 30 runtime tests, 189 total | [[tool_calling]], `scripts/golden_path.py` |
| 3 | Oct 29 | Loop B lessons + domain pack | Jangaon story end to end; habit rejected; 0 leaks | ✅ EXP-008: T01 0/4 → 4/4 safe and TNEW 0/4 → 4/4 via the pack (first attempt, 0 leaks); mining precision 0.73 (below the 0.85 bar), recall 0.73; 10 learning tests | [[lessons]], [[experiments]] |
| ✅ | **Nov 1, 10 AM** | **Demo-safe checkpoint** | Layers 0–3 done | ✅ reached Oct 29 | |
| 4 | Oct 29– | Loop A harness patch, OR-Tools, specialists | One real patch decided | ✅ Loop A built (feedback, trace signals, Muse proposer, patch rules, paired test, versions, rollback; 11 tests). EXP-010: the patch was correctly rejected (no held-out gain), so none is active. Oct 30: 8 new tools from a user-question audit (D-037; 27 tools in 7 categories) | [[harness_versions]] |
| 5 | Nov 1–2 | 100 sealed cases, review, adversarial, arms A–E | Paired results with counts | ✅ EXP-011 on unseen world 5279: both bars met. Scaled down: 38 cases (not 100), one run each, arm D not run (no active patch), casebook not human-reviewed | [[data_and_benchmark]] |
| 6 | Oct 29– | Streamlit 3 views, judge challenge, hosting | Works in incognito | 🟨 8 pages work from a fresh clone with no keys (replay bundle, world built from seed, 8 live runs per session). Oct 30 (D-038): hosted mode `ANUBHAV_PUBLIC=1` gives each visitor their own drafts and lessons; every live call behind one guard with a 60/day cap; replay offers only saved runs; AppTest suite. Left: Logs page, deploy (`docs/deploy.md`). Judge seed challenge cut | `streamlit_app.py` |
| 7 | Nov 3–4 | README, video, submit | Submitted | 🟨 README, MIT LICENSE, licenses and attribution done; repo public, history clean. Left: screenshot/GIF, video, submit | [[submission_checklist]] |

## Functional requirements (PRD v3.1 §14)
| FR | Requirement | Layer | Status |
|---|---|---|---|
| FR-01 | EN / TE / RT / mixed input | 2 | ✅ live (1 run each; benchmark in Layer 5) |
| FR-02 | Muse is the real planner and lesson proposer | 2–3 | ✅ |
| FR-03 | MCP discovery and invocation | 2 | ✅ tests |
| FR-04 | Adapter normalization (A/B/C schemas) | 2 | ✅ tests (4 clients, 3 schemas) |
| FR-05 | Ambiguous entity → clarification | 2 | ✅ live (1 run) |
| FR-06 | Draft-only side effects | 2 | ✅ no dispatch tool exists |
| FR-07 | Deterministic capacity / dimension / unit checks | 2 | ✅ tests |
| FR-08 | Atomic exclusive holds, idempotency | 2 | ✅ concurrency + retry tests |
| FR-09 | Event trace and replay | 2 | ✅ tests |
| FR-10 | Evidence-backed lesson proposal | 3 | ✅ |
| FR-11 | Conservative promotion (one failure ≠ regional ban) | 3 | ✅ tests |
| FR-12 | Manual reviewer decisions with audit | 3 | ✅ CLI + tests (UI in Layer 6) |
| FR-13 | Contradiction, expiry, retirement, rollback | 3 | ✅ tests |
| FR-14 | Harness patch boundaries | 4 | ✅ tests (surfaces only, no business facts, no safety weakening) |
| FR-15 | Paired patch tests | 4 | ✅ built + tests; live in EXP-010 (patch correctly rejected: no held-out gain) |
| FR-16 | Reject regressing patches | 4 | ✅ gate tests |
| FR-17 | Tenant and role enforcement | 2 | ✅ tests |
| FR-18 | Prompt-injection handling | 2, 5 | ✅ data marked untrusted; adversarial suite (injected notes) passes |
| FR-19 | Four-arm controlled evaluation | 5 | 🟨 arm D (ablation) not run; EXP-011 on unseen world 5279: both pre-registered bars met (+55 pts lessons vs raw notes, +67 pts pack), 0 unsafe with learning |
| FR-20 | Held-out contamination protection | 5 | ✅ fresh unseen-seed worlds (4111, 5279); held-out towns in practice; files frozen by hash before model calls |
| FR-21 | Hosted / replay mode | 6 | 🟨 replay bundle + world from seed; fresh clone checked (8 pages, no keys); per-visitor state in hosted mode (D-038, AppTest); deploy pending (docs/deploy.md) |
| FR-22 | Spend caps and secrets | 6 | ✅ keys only from env/secrets; live mode off without keys (buttons disabled, say why); 8 live runs per session and 60 per day for the app, voice included (D-038) |
| FR-23 | Licensing and originality ledger | 7 | ✅ `LICENSE` (MIT), `LICENSES_AND_ATTRIBUTION.md`, README "built during the hackathon" |
| FR-24 | Domain pack isolation (opt-in, redaction, revocation) | 3 | ✅ tests + EXP-008 (0 leaks) |

## Release gates (must be zero before demoing as safe)
| Gate | Status |
|---|---|
| Unauthorized executed action | ✅ 0 (draft-only boundary: no dispatch tool exists; adversarial suite) |
| Cross-tenant data access | ✅ 0 in tests (full adversarial suite: Layer 5) |
| Unapproved enforced lesson | ✅ 0 (policy requires approval + verification; tests) |
| Duplicate exclusive hold | ✅ 0 under concurrency test |
| Prompt-injection policy bypass | ✅ 0 in adversarial suite (injected driver notes) |
| Unreviewed harness patch activated | ✅ 0 (activation needs a passing test + a person; tests) |

## Next (plan of Oct 30, [[implementation_plan]])
| Workstream | Days | Status |
|---|---|---|
| P0 commit step 1 | Oct 30 | ⬜ |
| A reply check, refusals with next step | Oct 31 | ⬜ |
| B Logs page | Oct 31 | ⬜ |
| C new-tool creation (read-only SQL → approved tool) | Oct 31 – Nov 1 | ⬜ |
| D nightly review (runs → Loop A / Loop B / tools) | Nov 2 | ⬜ |
| E deploy + recorded demo runs | Nov 2 | ⬜ |
| F honest docs | Nov 2 | ⬜ |
| G video, README, submit | Nov 3–4 | ⬜ |
