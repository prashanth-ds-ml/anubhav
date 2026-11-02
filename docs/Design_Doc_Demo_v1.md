---
tags: [design, ux, react, api, audit]
status: APPROVED by the owner (Nov 2, evening; D-052). Build plan: [[Build_Plan_Demo_v1]].
date: 2026-11-02
---
# Design doc: the judge-ready demo (React app and API)

Related: mock screens (canvas, 12 screens: https://claude.ai/artifact/J4uRdnB62rnyJdDrSEZTvt), [[UX_Revision_Plan_v1]] (§9 polish pass), [[demo_plan]] (scenarios S1–S5), [[Backend_Report]], [[Handoff_Web_to_AI_Engineer]], [[experiments]], [[decisions]] (D-049 to D-051), `contracts/api.md`.

## 1. Purpose
Judges score Impact (30%), Meta AI tooling (25%), Technical depth (20%) and Demo (25%), and the final round tries the hosted app themselves. This doc audits what the backend and the React app do today and designs the version the mocks show: six main tabs, six scenarios, visual evidence, benchmarks, and a claim trail a judge can check.

**Goals**
1. A judge understands the product and finishes one scenario in about 60 seconds, unguided.
2. Every claim on screen links to its data: a run record, a lesson's evidence, a result file or a commit.
3. Each Muse model's role is visible where it acts.
4. Failures and unmeasured things are shown as plainly as successes.

**Non-goals:** new agent capabilities, new experiments other than EXP-014 if the owner approves it, a road map or turn-by-turn routing, login, real customer data.

## 2. Audit: what exists today (Nov 2)

### 2.1 Backend (FastAPI, `src/anubhav/api/`)
50 routes. They are grouped below with whether today's page uses them.

| Area | Routes | Used by the page | Notes |
|---|---|---|---|
| Session, health, voice | `/health`, `/session`, `/voice`, `/companies`, `/suggestions`, `/session/reset-drafts` | yes (5 of 6) | Live caps: 8 runs a session, 60 a day; voice counts as a live run |
| Chat and runs | `/chat`, `/chat/stream`, `/runs/{id}`, `/runs/{id}/resume`, `/runs/{id}/feedback`, `/handoffs` | chat, stream, run JSON | Resume and feedback have no UI |
| Dashboard | `/dashboard/orders`, `/fleet`, `/drafts`, `/drafts/{id}/cancel`, `/drafts/{id}/decide`, `/company` | reads only | **Approving or rejecting a live draft has no UI** (the S4 mock needs it) |
| Learning | `/learning/lessons`, `/lessons/{id}/decide`, `/learning/timeline`, `/learning/mine` | yes, except mine | Lessons carry gate evidence (3 shipment ids), events and the reviewer |
| Tools | `/tools`, `/tools/candidates`, `/candidates/{key}/check`, `/tools/{id}/decide`, `/tools/{id}/retire` | yes | |
| Agents | `/agents`, `/agents/{id}` | list only | `/agents/{id}` has instructions, versions tried and knowledge counts |
| Logs | `/logs/runs`, `/logs/runs/{id}`, `/logs/events`, `/logs/tools`, `/logs/routing`, `/logs/agents`, `/logs/models`, `/ledger` | ledger only | **Per-agent calls, errors and cost already exist** (`/logs/agents`), as does model attribution (`/logs/models`) |
| Proof | `/proof`, `/proof/curve`, `/compare` | proof, compare | `/proof` has 7 entries (011, 011R, 012, 012b, 013, 009, 009b). `/proof/curve` says EXP-014 has not run |
| Harness, practice, packs, review, report | 13 routes | none | Local-only actions are refused on the public host (`READ_ONLY_PUBLIC`) |

**Fixed today:** a hosted visitor sees only demo runs and their own (E-026); plan explanations list only lessons for the draft's sites (E-027); lesson seeding is safe under parallel first requests (E-028); idle visitor files are pruned after 2 days.

### 2.2 React app (`web/`)
- **Layout:** one screen. Chat on the left. **Nine tabs** on the right: Orders, Route plans, Fleet, Company, Ledger, Agents, Learning, New tools, Proof.
- **Built today (D-050, D-051):**
  - Five scenario cards with a stepper guide.
  - A plan card that checks the truck against the gate rule.
  - Before/after pairs.
  - Live mode on Muse Spark 1.3.
  - `/?tour=S1` deep links.
  - Proof headline figures.
  - Readable run steps.
  - A New tools tab.
- **Charts:** none beyond tiles and bars drawn with CSS. No chart library.
- **Tests:**
  - 95 browser tests, 13 unit tests and 549 Python tests, all passing (Nov 2).
  - Axe accessibility checks on key views.
  - Browser tests run with the keys blanked.

### 2.3 Gaps between the app and the mocks

| Mock screen | Exists | Missing | Size |
|---|---|---|---|
| 1 Dispatch Desk, first screen | Cards, chat, right-hand tabs | Six main tabs; right panel limited to 5 tabs; S6 card; Meta Muse strip; the impact line | M |
| 2 S1 without lessons | Plan card, gate check | Truck drawn to scale against the gate line; the code-checks strip; language chips | S |
| 3 S1 done | Before/after pair | Framing sentence; both trucks on one scale; Approve/Improve lit in the loop strip | S |
| 4 S4 live | Live runs, retire and undo | LIVE badge with run blocks; the retired-lesson card in chat; **approve or reject the live draft** | M |
| 5 Phone | Stacks | Section menu for the main tabs | S |
| 6 Learning | Lesson cards, actions, timeline | Two-pane layout; **evidence chart of every trip to the site** (new API); life cycle track | L |
| 7 Kazipet (S6) | Expired lesson in the store | **Weekly delays and drivers' notes** (new API); the S6 guide | M |
| 8 Tools | Candidates, checks, approve | Full-width layout; before/after bars next to Approve; held-out values in plain words | S |
| 9 Runs | Timeline per run, run JSON | Run list; **swimlane by agent**; work per agent; "mistake → fixed" detection | L |
| 10 Agents | Agent cards | How each agent learns; measured numbers per agent; team line; EXP-014 frames | M |
| 11 Benchmarks | Some figures | Before/after dots by company; mining over 3 experiments; open-weights table; **17-experiment scoreboard** (new data) | M |
| 12 Check our claims | Tiles | Slope charts; **chain of custody** (new data: plan commit → result commit) | M |

### 2.4 Risks found
1. **All of today's work is uncommitted:** the merge, the scenarios, the polish and the server fixes. One disk problem would lose a day. Commit before the build starts.
2. **Nothing is deployed.** The judges' link is still Streamlit. A Docker Space needs the Space name and a go-ahead.
3. **Live mode on the host** needs `meta_api` as a secret. With EXP-014 possibly spending $20–30, the daily cap should drop to about 40 runs during judging.
4. **Cold start:** a fresh container generates the world on first boot (about 1 minute). The first visitor waits.
5. **Demo lessons were approved by a fixed rule, not a person.** The screens say so. S1's undo-and-approve step is where a person approves.
6. **README screenshots** (`web/readme-assets/`) show the old layout.
7. **The S2 tool check's held-out values** are not shown in plain words yet (`[n] of [n]` in the mock).

## 3. Design

### 3.1 Information architecture
Six main tabs, each with its own address, so a link can open any of them.

| Main tab | Address | Contents |
|---|---|---|
| Dispatch Desk | `#desk` (default) | Chat, scenario guide, composer. Right panel: Orders, Route plans, Fleet, Company, Ledger (`#desk/plans` and so on) |
| Learning | `#learning`, `#learning/L-T01-002` | Lesson list (active, waiting, expired); detail with the evidence chart and life cycle; timeline (folded) |
| Tools | `#tools` | Candidates, checks, approve, before/after; benchmark panel |
| Agents | `#agents` | Team line; one card per agent; EXP-014 frames |
| Runs | `#runs`, `#runs/{run_id}` | Run list; swimlane; work per agent; selected step; mistake → fix; final answer |
| Proof & audit | `#proof/bench`, `#proof/claims` | Benchmarks; Check our claims |

- **The scenario guide** is app-level state. It stays visible across main tabs as a slim bar, and a step can open any tab and highlight an item there (`focusOn`, already built).
- **Deep links:** `/?tour=S1…S6` opens a scenario; `#runs/{id}` and `#learning/{lesson}` open an item.
- **The phone layout** turns the main tabs into a section menu, and the right panel stacks under the chat.

### 3.2 Scenarios

| | Kind | Steps | Payoff on screen |
|---|---|---|---|
| S1 | Recorded | Play without lessons → see the lesson → undo and approve → play with lessons | Red 32 ft card, then green 22 ft; trucks on one scale |
| S2 | Recorded | Ask → check and approve in Tools → ask again | Before/after bars: 5 → 1 calls |
| S3 | Recorded | Switch company → without → with the shared pack → Benchmarks | 32 ft → 22 ft on day 1; 33% → 100% |
| S4 | Live | Retire → send live → bring back → send live → approve or reject the draft | The live plan follows the rule |
| S5 | Live | Four challenges, or anything typed or spoken | Refusals by code; nicknames understood |
| **S6** | Recorded data | Open the road story → read the notes → see the delays chart → see that the lesson expired | Route knowledge learned, shared and expired |

### 3.3 New and changed API (all read-only, no model calls)

**`GET /api/learning/lessons/{id}/evidence?company=`.** This is the data behind a lesson, read from the company's own records by lesson kind, with no knowledge of the world written into code.
- `site_access`, `night_only`, `receiving_hours`, `weekly_off`: every trip to the lesson's site.
  `{kind:"trips", site, rows:[{date, vehicle_id, length_ft, status}], limit_ft?}`
- `closure`: closure delays by week, plus the drivers' notes that mention the place.
  `{kind:"closure", place, window:{from,to}, weeks:[{week, delays}], notes:[{ts, lang, source, text}]}`
- Other kinds return `{kind:"none"}`, and the page hides the chart.

**`GET /api/proof/registry`.** Every pre-registered experiment, from a new committed file `artifacts/experiments_index.json`. It's written once from [[experiments]] and git, never computed at runtime.
- Each row: `{id, question, verdict: met|not_met|finding|not_run, plan:{date, commit}, result:{date, commit, file}, runs, cost_usd, note}`.
- A test checks that every row's `file` exists and every `commit` resolves in git.

**`GET /api/proof`** gains EXP-004 (the open-weights table) and EXP-008 (mining on the demo world), both read from their existing result files.

**Contract:** `contracts/api.md` adds the two routes. `/api/logs/agents`, `/api/logs/models` and `/api/runs/{id}` are reused as they are.

### 3.4 Front-end structure
- **`App`** owns the main tab, the scenario state and the company. **`DeskPage`, `LearningPage`, `ToolsPage`, `AgentsPage`, `RunsPage` and `ProofPage`** are the pages.
- **Charts:** small components drawn with plain SVG and CSS, with no chart library (bundle size, and full control of the labels):
  - `TruckScale`: trucks against the gate line
  - `EvidenceStrip`: trips by date and truck length
  - `WeeklyBars`: delays by week, with pins for notes
  - `Swimlane`: one lane per agent
  - `Slope`: before and after, one line per repeat
  - `Dumbbell`: before and after per company
  - `ProgressBars`
- **Swimlane data** is built from `/api/runs/{id}` events, in the same way as today's `buildLanes`.
  - A **mistake → fix** is detected when a `tool_result` has `ok:false` and a later result from the same agent and tool has `ok:true`.
  - Only real recorded or live runs are shown.
- **Live draft decisions** use the existing `/dashboard/drafts/{id}/decide`. Approve re-checks the plan in code; reject needs a note. Neither dispatches.

### 3.5 Visual rules
- **Colours:** the existing tokens. Teal is recorded and the system; amber is live; green ✓ fits or met; red ✕ breaks or missed; dashed grey is not measured or expired.
  - Red and green always come with a shape (✕ or ✓) and a word, never colour alone.
- **Chart titles state the takeaway** ("Learning lifted accuracy from 48% to 90%"). The subtitle names the experiment, sample size, repeats and model.
- **Numbers:**
  - Every number comes from an API response or a committed result file, never typed into the page.
  - Where a value isn't available, the page says "not measured yet".
- **Every chart has a data link** (the run JSON, the rows or the result file) and an `aria-label` that states its result in words.
- **Labels on every run:** recorded or live, model, date, lessons on or off.

### 3.6 Honesty rules (from [[decisions]] D-046 to D-051)
1. Don't claim the team is more accurate than one Planner.
2. Don't claim that each agent, or the whole team, improves until EXP-014 has run and met its rules.
3. Say "approved by a fixed review rule" where no person approved.
4. Label a live run as "behaved as described once in our test", not as a measured rate.
5. Keep every failed bar visible: EXP-007, 009, 012, 012b, and EXP-013's learning round.

### 3.7 Accessibility and screens
- Keyboard: tabs use the existing arrow-key pattern; every action is a real button or link; touch targets are at least 44 px.
- Text contrast is at least 4.5:1 in both themes, and axe checks run on every main tab.
- Layout targets: 1440×900, 1280×720 (scenario cards visible without scrolling), 1024 px, and a 390 px phone.

### 3.8 Testing
- **Python:** the two new routes for each lesson kind and an unknown kind; registry rows resolve to real files and commits.
- **Browser:**
  - each main tab loads with no errors
  - each scenario S1–S6 runs end to end (S4 and S5 with a mocked live chat)
  - the evidence chart shows 18 trips with 3 turned back
  - the Kazipet chart shows 0 closure delays after 29 Sep
  - the swimlane shows the hand-off
  - the mistake → fix appears for `demo:new-tool-before`
  - the scoreboard lists 17 experiments
- The full suites stay green before each commit.

## 4. Decisions (owner, Nov 2, D-052)
1. Design approved.
2. EXP-014: run after the build is complete (re-frozen, Meta API, cap $40).
3. Today's work committed before the build (`e63472f`).
4. Deploy (Space name, `meta_api` secret): after the build.
5. Daily live cap stays 60. **New requirement:** a demo always shows clearly how many live runs are left.

### Open decisions as first proposed
1. **Approve this design** (the six main tabs, S6, the two read-only routes, the registry file).
2. **EXP-014 tonight on the Meta API** (re-frozen with the model change recorded, cap $40), or not.
3. **Commit today's work now**, before the build starts. Recommended.
4. **Deploy target:** a Hugging Face Docker Space name, and the go-ahead to add `meta_api` as its secret.
5. **Daily live cap during judging:** 60 (current) or about 40.

Once this doc is approved, the build doc follows: sprints, tasks, tests and a cut order for the Nov 4 deadline.
