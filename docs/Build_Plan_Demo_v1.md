---
tags: [plan, build, sprints, react, api]
status: PROPOSED (Nov 2, evening). Starts on the owner's go-ahead.
date: 2026-11-02
---
# Build plan: the judge-ready demo

Implements [[Design_Doc_Demo_v1]] (approved, D-052). Mock screens: https://claude.ai/artifact/J4uRdnB62rnyJdDrSEZTvt. Baseline commit: `e63472f`.

**Deadline:** Wed Nov 4, 9:00 PM ET = **Thu Nov 5, 7:30 AM IST**. We aim to submit on the evening of Nov 4 IST, leaving the night as a buffer.

**Order (owner, D-052):** build (sprints 1–7) → EXP-014 overnight → deploy → video → submit.

## 1. Ground rules for every sprint
1. **Commit at the end of each sprint,** as `prashanth-ds-ml` only, with no co-author or attribution. Push only when the owner says so.
2. **Every sprint ends green:** `uvx ruff check .`, `uv run pytest -q`, `cd web && npx tsc --noEmit && npm test && npm run build`, plus the browser tests that sprint touches. The full browser suite runs at sprints 4 and 7.
3. **No number typed into the page:** every figure comes from an API response or a committed result file. Missing means "not measured yet".
4. **No world knowledge in runtime code** (place names, rules, word lists). Scenario scripts are UI copy and say so.
5. **No model calls and no credits** in sprints 1–7. Live behaviour is tested with a mocked chat.
6. **Trackers are updated as we go:** [[decisions]], [[errors_and_fixes]], [[todo]] and the daily note.

## 2. Timeline at a glance

| Sprint | When (IST) | Goal | Size |
|---|---|---|---|
| 0 | Nov 2, done | Baseline committed, design approved | — |
| 1 | Nov 2 night | App shell: six main tabs, addresses, scenario state at app level, **live runs meter** | ~3 h |
| 2 | Nov 2 night | Backend: lesson evidence route, experiment registry, proof entries, contract | ~2.5 h |
| 3 | Nov 3 morning | Learning tab and the S6 Kazipet story (evidence chart, weekly bars, life cycle) | ~3 h |
| 4 | Nov 3 midday | Dispatch Desk: truck scale, code-checks strip, language chips, Meta Muse strip, S4 live card, live draft approve/reject | ~3 h |
| 5 | Nov 3 afternoon | Runs (swimlane, work per agent, mistake → fix), Agents, Tools layout | ~4 h |
| 6 | Nov 3 evening | Proof & audit: Benchmarks and Check our claims | ~3 h |
| 7 | Nov 3 night | Hardening: full tests, accessibility, 4 screen sizes, README screenshots, docs | ~2 h |
| After | Nov 3 night → Nov 4 | EXP-014 overnight; then deploy, video, README results, submit | — |

**The squeeze:** the video moves from Nov 3 to Nov 4 (see §5 for what we cut if we fall behind).

## 3. Sprints

### Sprint 1: app shell and the live runs meter
**Goal:** the six main tabs exist, each tab has an address, the scenario guide survives tab changes, and a demo always shows the live runs left.

| # | Task | Files |
|---|---|---|
| 1.1 | `App` owns the main tab (`#desk`, `#learning`, `#tools`, `#agents`, `#runs`, `#proof`), the scenario state and the company; the old nine-tab panel is split | `App.tsx`, new `pages/*.tsx` |
| 1.2 | The right panel on Dispatch Desk keeps only Orders, Route plans, Fleet, Company and Ledger (`#desk/plans` and so on) | `Dashboard.tsx` |
| 1.3 | Learning, New tools (renamed Tools), Agents and Proof move to their own pages; the content moves unchanged for now | `pages/` |
| 1.4 | The scenario guide moves up to `App` and shows on every page; `openTab` switches main tabs; `focusOn` still highlights | `Scenarios.tsx`, `Chat.tsx` |
| 1.5 | **Live runs meter (new requirement).** `GET /api/session` adds `live_runs_left_today` (the app's daily budget left). The header shows `LIVE · Muse Spark 1.3` and **one block per run left** with "N of 8 left in this visit" whenever live is available. Live scenario cards and the composer repeat "N left". At 0 it says so plainly ("No live runs left in this visit; recorded scenarios still work"); when the day's 60 are used, it says that instead. It refreshes after every live run | `routes.py`, `session.py`, `ctx.tsx`, new `LiveMeter.tsx` |
| 1.6 | Phone: the main tabs become a section menu | `App.tsx`, CSS |

**Done when:**
- Each address opens its tab.
- A scenario started on the Desk is still visible on Learning.
- The live meter matches `/api/session` before and after a mocked live run, and its 0 states read correctly.

**Tests:** browser: tab addresses; guide persists; meter counts down (mocked live); meter at 0 and the daily cap state. Python: `live_runs_left_today` in the session response.

### Sprint 2: backend for the new screens
**Goal:** the two read-only routes and the registry data, with tests. No model calls.

| # | Task | Files |
|---|---|---|
| 2.1 | `GET /api/learning/lessons/{id}/evidence`, by lesson kind, read from the company's records. Site kinds return every trip to the site (date, vehicle, length, status, limit). `closure` returns delays by week inside and after the window, plus drivers' notes that mention the place. Other kinds return `{kind:"none"}` | `service/views.py` (or new `service/evidence.py`), `routes.py` |
| 2.2 | `artifacts/experiments_index.json`: the 17 pre-registered experiments (id, question, verdict, plan date and commit, result date, commit and file, runs, cost, note), written from [[experiments]] and git | new file |
| 2.3 | `GET /api/proof/registry` serves it | `routes.py` |
| 2.4 | `/api/proof` adds EXP-004 (open weights against Spark 1.3) and EXP-008 (mining, demo world) from their result files | `service/proof.py` |
| 2.5 | Contract: the two routes and `live_runs_left_today` | `contracts/api.md` |

**Done when:**
- Evidence for L-T01-002 returns 18 trips, 3 of them refused, all 32 ft.
- Evidence for L-T01-011 returns 45 closure delays, all inside 1 Aug–29 Sep, 0 after, and 12 notes.
- The registry has 17 rows.

**Tests:** the evidence route for each kind and an unknown one; a visitor can't read another company's evidence; every registry `file` exists and every `commit` resolves in git; the route list test includes the new paths.

### Sprint 3: Learning and the S6 road story
| # | Task |
|---|---|
| 3.1 | Learning becomes two panes: lesson list (Active, Waiting, Expired) and detail; address `#learning/{lesson_id}` |
| 3.2 | `EvidenceStrip` (SVG): trips by date and truck length, the learned limit as a dashed line, refused trips as ✕, a legend, an `aria-label` in words, and a "see the trips" link |
| 3.3 | `LifeCycle`: proposed → evidence checked → approved (by whom: person or fixed rule) → in use → ends or expired, from lesson events |
| 3.4 | Lesson actions move into the detail pane; S1 step 3 highlights them |
| 3.5 | `WeeklyBars` (SVG): closure delays by week, the window shaded, note pins, "0 after" called out |
| 3.6 | The S6 scenario and road story: notes in three languages (from the API), the chart, the life cycle, "why this is regional knowledge" |
| 3.7 | The learning timeline stays folded under the list |

**Done when:** both charts render from the API with no typed numbers, and S6 runs end to end. **Tests:** the evidence chart shows 18 marks and 3 ✕; the Kazipet chart shows 0 after 29 Sep; S6 steps; axe on Learning.

### Sprint 4: Dispatch Desk payoff
| # | Task |
|---|---|
| 4.1 | `TruckScale`: the plan card draws the truck against the learned limit; the S1 finish draws both trucks on one scale |
| 4.2 | A code-checks strip on the plan card (load, documents, final re-check from `why.checks`) with "The code checks passed. Only the learned rule says no" when only the lesson fails |
| 4.3 | Language chips on S1 ("also recorded in తెలుగు · English · Mixed"), each playing that saved request |
| 4.4 | The S1 finish framing sentence; Approve and Improve light up in the loop strip when a scenario reaches them |
| 4.5 | S4: the "You retired a lesson [Undo]" card in the chat; the live plan card |
| 4.6 | **Live draft decisions:** Approve (re-checked in code) and Reject with a note, on live drafts only, via `/dashboard/drafts/{id}/decide`; recorded drafts keep the neutral note |
| 4.7 | First screen: six scenario cards (S6 added), the "Built on Meta Muse" strip, the impact line with its source; it still fits 1280×720 |

**Done when:** S1–S5 run end to end with the new visuals. **Tests:** truck scale widths follow the lengths; approve and reject on a mocked live draft; first-screen fit at 1280×720; **full browser suite**.

### Sprint 5: Runs, Agents, Tools
| # | Task |
|---|---|
| 5.1 | Runs page: list from `/api/logs/runs` (title, agents, calls, mistakes fixed), address `#runs/{id}` |
| 5.2 | `Swimlane` (SVG or positioned blocks) from run events: one lane per agent with its model, hand-offs as arrows, tool calls as blocks, failures red, fixes green; selecting a step shows its arguments and answer (raw behind a toggle) |
| 5.3 | Work per agent: calls, errors and cost bars for the run |
| 5.4 | Mistake → fix detection (a failed tool result followed by a later success from the same agent and tool), shown as a pair; it appears for `demo:new-tool-before` |
| 5.5 | Agents page: team line (EXP-013); one card per agent with how it learns, measured numbers, and calls, errors and cost from `/api/logs/agents`; EXP-014 frames read `/api/proof/curve` and say "not measured yet" until it has run |
| 5.6 | Tools page full width: the story candidate first, checks in plain words (held-out values named), before/after bars beside Approve, and the benchmark panel |

**Done when:** the S2 team run shows Planner → Tool Forge with 2 and 4 calls; the mistake pair shows the real SQL error and fix. **Tests:** swimlane lanes and hand-off; mistake → fix; the Agents numbers match the API; the S2 approve step still ticks only after approval.

### Sprint 6: Proof & audit
| # | Task |
|---|---|
| 6.1 | Sub-tabs: Benchmarks (`#proof/bench`) and Check our claims (`#proof/claims`) |
| 6.2 | `Dumbbell`: EXP-011R per company with unsafe drafts beside it; the "not improved" line |
| 6.3 | Mining precision over EXP-008, 009 and 009b against the 85% bar; the open-weights table (EXP-004) |
| 6.4 | Scoreboard of the 17 experiments from `/api/proof/registry`, with verdict marks, plus a "your seed" card with the command |
| 6.5 | `Slope`: lessons and day-1 sharing, one line per repeat |
| 6.6 | Chain of custody table: plan → run → result → verdict → links, from the registry |

**Done when:** every figure traces to `/api/proof` or the registry. **Tests:** the scoreboard has 17 entries and the failed ones are marked ✕; the slope shows 3 repeats; the links resolve.

### Sprint 7: hardening
| # | Task |
|---|---|
| 7.1 | Full suites green; axe on every main tab in light and dark |
| 7.2 | Screenshot pass at 1440×900, 1280×720, 1024 and 390 wide; fix overflow and clipping |
| 7.3 | Regenerate `web/readme-assets/`; README "Try it" lists the six scenarios with `/?tour=` links and the main tabs |
| 7.4 | Docs: the UX plan, the demo plan and the video storyboard follow the new screens; trackers and the daily note updated |
| 7.5 | Remove dead code from the old nine-tab layout; check the bundle size |
| 7.6 | Commit; the build is done |

## 4. After the build (owner's order)
1. **EXP-014, overnight (Nov 3 → 4).** Re-freeze with the model change recorded (agents on Muse Spark 1.3, Meta API), cap $40, and commit the re-freeze before the first call. Run in the background with resume. In the morning, read the result, apply its fixed rules and fill the Agents and Benchmarks frames from `/api/proof/curve`. A flat result is published as flat.
2. **Deploy (Nov 4 morning).** Needs the owner's Space name and the `meta_api` secret. Build the Docker image, push to the Space, then run the incognito check: health, the first screen, S1 to S3, and the live meter with a real key.
3. **Video (Nov 4).** Record S1 → S2 → S3 through `/?tour=` links, then about 15 seconds of S4 live with the meter visible, then Proof & audit.
4. **Submit (Nov 4 evening IST):** the submission checklist, a dry run, then submit. Keep the night as a buffer.

## 5. Cut order if we fall behind
Cut from the top first. Each cut is safe: nothing it removes is promised elsewhere.
1. Phone section menu (sprint 1.6): the phone keeps the stacked layout.
2. Language chips (4.3).
3. Note pins on the Kazipet chart (in 3.5): keep the bars and the window.
4. Mining progression chart (6.3): keep the open-weights table.
5. Work-per-agent bars on Runs (5.3): the Agents page keeps the totals.
6. S6 as a guided scenario (3.6): keep the road story as a Learning view, without the guide.
7. EXP-014 (after the build): skip and leave "not measured yet". This frees the night.

**Never cut:** the main tabs, the live runs meter, S1–S5, the evidence chart, the swimlane with the real mistake → fix, Benchmarks with the scoreboard, Check our claims.

## 6. Risks
| Risk | Effect | Response |
|---|---|---|
| Sprints run long | Video squeezed | Cut order §5; record recorded scenarios first |
| Front-end restructure breaks tests | Time lost | Sprint 1 moves content unchanged; restyle later |
| EXP-014 fails midway or hits rate limits | No curve | It resumes; if not done by Nov 4 noon, leave "not measured yet" |
| Space cold start or build issues | First judge waits or a broken link | Deploy on Nov 4 morning, not at the deadline; Streamlit stays as the fallback link |
| A live run misbehaves on video | Weak moment | S4 is honest-labelled; record it after the recorded ones and keep a second take |
