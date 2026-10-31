---
tags: [tracker, todo]
---
# To-do (audit, workshop review and demo plan, Oct 30)

Status key: ⬜ pending · 🟨 in progress · ✅ done · ✂️ cut
Sources:
- the three-part audit (context, code, readiness) and the review of `meta-models/legal-agent-workshop`, both on 2026-10-30;
- the owner's demo brief, the same evening.

> **Dates:** the Day column is the plan's schedule. All items marked done so far were done on **2026-10-30** (the real date), ahead of plan.

**How and why: [[implementation_plan]]** (D-039, D-040). Related: [[progress]], [[submission_checklist]], [[risks]].
**Audit of this list on Oct 30 (evening):**
- Step 1 is done and re-tested (147 passed) but **not committed**.
- Of step 1b, W3 and W4 are not started; W5 is partial (it becomes the Logs page).
- Nothing in steps 2 or 3 is done yet.

## Step 0: commit step 1 (tonight)
| # | Item | Status |
|---|---|---|
| P0 | One commit by prashanth-ds-ml, no trailer, after the owner checks localhost:8501 / :8502 | ✅ `8277fa7` (docs `3ed5386`) |

## Step 1: judge-proof fixes (one commit, a test for each bug): done Oct 30, D-038
Items 1, 2, 6 and 7 from the workshop review fold straight into this commit. 147 tests (+19), all pass; also: `pydantic` declared, `requirements.txt` regenerated with `--universal`.

| # | Item | Where | Status |
|---|---|---|---|
| 1.1 | `requirements.txt` pins `pywin32==312` without a platform marker, so the Linux / Streamlit Cloud install fails. Regenerate it with `uv pip compile --universal` | `requirements.txt:169` | ✅ |
| 1.2 | Live buttons crash with `KeyError: 'meta_api'` without keys and skip the spend cap. Put every Muse call behind one guard (`core.live_ready` + counter) and add a global daily cap. Voice counts too | `app_pages/learned.py`, `learning_lab.py`, `skills.py`, `tuning.py`, `workbench.py` | ✅ |
| 1.3 | Replay dead ends (23/48 combinations): show only the suggestions that have a saved run (`core.replayable()`); hide or label companies without runs | `app_pages/workbench.py`, `ui/core.py` | ✅ |
| 1.4 | Shared state on the host: per-session runtime, or hide the destructive buttons when hosted; auto-load the EXP-008 lessons on a fresh start | `ui/core.py:105-112` | ✅ |
| 1.5 | An impossible date (`2026-02-30`) crashes the run: check it with `date.fromisoformat` in `_date`, and add a catch-all `INTERNAL` error in `Broker.call` | `runtime/broker.py:193` | ✅ |
| 1.6 | Revoking a pack retires the recipient's own lesson: retire only `source` = `pack:*` | `learning/pack.py:299-310` | ✅ |
| 1.7 | A reused idempotency key returns a different draft: raise `CONFLICT` | `runtime/broker.py:328-335` | ✅ |
| 1.8 | Duplicate order ids double-count the load: dedupe, or `BAD_ARGS` | `runtime/broker.py` (`CreateDraft`) | ✅ |
| 1.9 | Pack ids collide within the same second: add the date and a uuid suffix | `learning/pack.py:232` | ✅ |
| 1.10 | Pack lesson text goes into the system prompt unfiltered: allow-list and length-cap the params, and render them as quoted data | `learning/pack.py`, `agent/graph.py:173` | ✅ |
| W1 | Muse client as in the workshop: `timeout`, `max_retries`, and a clear `MissingKeyError` instead of `KeyError` | `muse.py:69` | ✅ |
| W2 | A failed model call ends the run cleanly (`stop="error"`, keeps the drafts made so far) instead of a traceback | `agent/graph.py:64` | ✅ |
| W6 | Offline test of the real `MuseClient` on a fake `httpx` transport (timeouts, retries, usage and cost parsing) | `tests/` | ✅ |
| W7 | Move company facts out of code: `"repu" = tomorrow`, "Telangana, 3PL", the e-way-bill limit, max stops, 38 km/h; the `bandi/lorry/truck` list in the gate | `agent/graph.py:27-28`, `runtime/safety.py`, `runtime/broker.py:323,553`, `learning/gate.py:159` | ✅ |
| 1.11 | Low priority: the stop label at the cost cap ✅; temp WAV files deleted ✅; `held` is used (reported in draft checks), so no change; policy approval on the simple page still writes the evidence shown on the card as the verified note: kept, and said so in the README limitations later | `graph.py`, `workbench.py`, `learned.py` | ✅ |

## Step 1b: reply check and helpful refusals, Oct 31 (plan §3 A, B)
| # | Item | Status |
|---|---|---|
| W3 | Reply check in `finish`: every draft or vehicle id in the reply exists in this run; the reply never says "dispatched/confirmed" (words in `operating_rules.yaml: reply_claims`) | ✅ Oct 31: `safety.check_reply`, carried in the finish step and shown on the workbench; 10 tests; 0 false alarms on the 67 saved real runs |
| W4 | Refusals name the next step: `CAPACITY_EXCEEDED` / `VOLUME_EXCEEDED` give the load needed and up to 3 free vehicles that fit. A UX fix only; claiming a gain needs a new pre-registered experiment | ✅ Oct 31: `broker._next_step` in `create_dispatch_draft(s)` and `check_load` (free, big enough, allowed at every stop, cold chain); 3 tests |
| W5 | Plan → act → observe timeline, refusals in red, "what the model saw". **Became the Logs page (B)** | ✅ Oct 31 |

## New: Logs page, new-tool creation, nightly review (plan §3 B, C, D; D-039, D-040)
| # | Item | Day | Status |
|---|---|---|---|
| B | Logs page: runs, lessons, patches, new tools and reviews on one timeline; raw JSON per row | Oct 31 | ✅ `app_pages/logs.py` + `ui/logs.py` (runs as plan → act → observe → code checks, refusals red; lesson events, patches with their paired test, feedback); 3 tests; new tools and reviews plug in when C/D land |
| E1 | Deploy without keys (owner clicks deploy; I push and prepare the steps) — moved up by D-042 | Oct 31 | ✅ https://anubhav-metahackathon.streamlit.app/: health ok, anonymous access works (cookie hop, no sign-in); fresh-clone check of all 9 pages passed before deploy. Owner to click through in incognito |
| H | Onboarding, **slim** (D-041 → D-042): profile computed from the records, editable, in the agent's prompt; Muse questions and answer checks cut | Oct 31 | ✅ `learning/profile.py` + Business profile page: facts counted from 8 record tables (each cites its table), owner fields cleaned and capped, versions per company, ≤600-char block given to live runs only (`graph.run(about=…)`; frozen experiments unchanged); 5 tests |
| C1 | Query sandbox: in-memory copy of the company's own records, SELECT only, time/row/length caps, untrusted text marked | Nov 1 | ✅ `runtime/query.py`: authorizer (SELECT/READ/functions only; `sqlite_*` denied), query_only, 2 s / 200 rows / 4 kB, free-text columns found from the data; schema with values, examples and joins generated from the data; 18 attack and limit tests |
| C2 | `run_query` tool (read class, "use other tools first"), off in frozen experiment configs | Nov 1 | ✅ `describe_tables` + `run_query` (category analysis), only with `Broker(analysis=True)`; on in the app. Live: "worst weekday for on-time in September" (RT) hit the 12-call limit exploring; with the richer schema, answered in 5 calls ($0.07): Thursday, right (82.1% vs true 82.5%), runner-up wrong. 2 tests |
| C3 | Save successful queries; turn literals into parameters; candidate when used in ≥ 2 requests | Nov 1 | ✅ `learning/newtools.py`: queries read from run traces; a literal becomes a parameter only where it is compared (=, IN, BETWEEN…) and it is a date or a value of the company's own name/id columns (found from the data: one value shape, many values, master table first); a person can also check a query used once |
| C4 | Promotion checks: same rows, held-out values, sandbox, a person approves (Tools tab) | Nov 1 | ✅ same rows with the original values; 5 held-out values (other names from the same column, dates moved by months/weeks inside the records' period) must run and mostly find rows; approve only if checks passed and only by a person; New tools page; Logs stream. Name from the agent's stated purpose (Muse naming cut) |
| C5 | Broker offers approved tools per company; retire / roll back | Nov 1 | ✅ `Broker(learned_tools=…)`: typed parameters, dates checked, run in the sandbox, category learned_tools; per company (per visitor when hosted); retire on the page |
| C6 | 4 gap question types with oracles (also the planner question bank); optional EXP-012 (~$3, pre-registered) | Nov 1 | ✅ `practice.build_gaps`: worst on-time weekday, busiest weekday per town, returned cases per town and month, damaged cases per month; RT/TE/EN; held-out by town/month; frozen EXP-010 set unchanged. EXP-012 → Nov 2 |
| C7 | Live result (Oct 31) | Nov 1 | ✅ Dev probe: 6 gap questions 5/6 right ($0.28), but 0 candidates: the model never writes the same SQL twice. Fix: queries with the same parameters that give **equivalent answers** (same row count and a shared numeric column, on original + held-out inputs) are one tool; the ASCII-labelled variant is kept. Probe → 3 candidates, all pass. Approved `busiest_weekday_in_town`, asked about a new town (Hanamkonda): **1 call, $0.016, exactly right** (Saturday, 33 stops); before: 2–5 calls, $0.03–0.05 |
| D | Nightly review: reads runs, feedback, new notes, cancelled drafts → Loop A / Loop B (same gate) / tool candidates; report on the Logs page | Nov 2 | ✅ `src/anubhav/review.py` + CLI + Logs page button: since the last review, code routes tool-use problems → Tuning, reused queries → checked tool candidates (New tools), stated facts (thumbs-down notes, notes the agent recorded) → one Muse Spark 1.3 call → the same evidence gate → reviewer. Free without keys except the Loop B call. On T01's real runs: 46 runs, 25 tool-use issues, 4 tool candidates (all pass), 2 fact notes. Cancelled drafts not read (cut). 4 tests |
| E2 | Record the demo story live (session 1 → review → session 2, plus "plan tomorrow"), saved as replays (~$2) | Nov 2 | ✅ (Oct 30) new-tool story in the hosted bundle: "New tool" suggestion replays the 5-call run ($0.066, hedged answer) until the visitor approves the reused query on New tools, then the 1-call run ($0.016, Saturday); the source runs ship in `demo/` so the page finds the reuse with no keys. Replays now match the visitor's approved tools. App test covers the whole flow. "Plan tomorrow" replay: T03 only locally (not in the bundle) |

## Toward 9/10 (D-043)
| # | Item | Day | Status |
|---|---|---|---|
| I1 | README honesty pass (test count, Limitations with n per claim, version gap, credits, FR-19 🟨) | Oct 31 | ✅ README results with n (7/20 → 18/20, 3/9 → 9/9) and commit `61cc927`; a Limitations section (8 points); 295 tests; Harness² + workshop credits in README and LICENSES; Open Weights paragraph; FR-19 🟨 |
| I2 | Each Muse model's role and calls on screen; Best Open Weights pitch | Oct 31 | ✅ "Meta models at work" on the Logs page (runs and cost of Spark Open, lessons and patches proposed by Spark 1.3, voice), counted from the records; README "Open weights end to end" |
| I3 | 1–2 cited freight statistics | Nov 1 | ✅ README "The problem": Redseer (Dec 2024) 12.5 M trucks, 3.5 M operators, "around 75% … own fewer than five trucks" (quoted from the page); DPIIT–NCAER logistics cost 7.97% of GDP in 2023–24 (secondary report, Sep 2025). Both checked on the page; a road-share figure was not found, so not used |
| I4 | Dispatcher review kit (Claude prepares; owner runs it with the interviewee) | Nov 1 | 🟨 kit ready: `docs/review_kit/dispatcher_review.md` (11 learned lessons with their evidence; "is this kind real in your region" + reviewer decision; timing protocol for T03 plan tomorrow; 3 open questions; honesty rules, EN + TE). **Owner:** run it with the interviewee and fill in the results |
| I5 | Spreadsheet import into a new company (cut first) | Nov 2 | ✂️ cut (Oct 30): first in the cut order; onboarding a client is an adapter mapping (D-030) and is described in the README; time goes to the video instead |
| J1 | EXP-011R: 3 repeats on the current version, pre-registered (~$15) | Nov 2 | ✅ (Oct 31) replicated 3/3: lessons 48% → 90% pooled (+40/+45/+40), pack 33% → 100% every repeat, 0 unsafe with learning, 0 leaks; real capacity still 0/6; $18.59 |
| J2 | EXP-012: new tools on gap questions, pre-registered (~$3) | Nov 2 | ✅ (Oct 30) EXP-012: both rules not met (query +12.5 pts; learned tools never called, 0/16: case-specific names). EXP-012b (general names, pre-registered): learned tools used 14/16 (R2b met), not worse (15 vs 14 right), −20% calls / −24% cost, short of the −30% bar (R2 not met). $7.27 together |

## Step 2: honest docs (~1.5 h, Nov 2)
- ✅ (Oct 30) README: test count; credit for Harness² (arXiv 2610.14224) here and in `LICENSES_AND_ATTRIBUTION.md`; the three learning routes, the Logs page and the tool-creation limits. The "Limitations" section exists: re-read it.
- ✅ (Oct 30) FR-19 → 🟨 (arm D not run); theme and anti-project ticked with a reason in [[submission_checklist]]
- ✅ (Oct 30) Risks R-04/R-05/R-17/R-18/R-19/R-21/R-22 refreshed; questions I-01–I-06, Q-05–Q-07 resolved or cut; I-07 waits for the dispatcher review
- ✅ (Oct 30) [[cost_ledger]] totals and forecast; [[harness_versions]] filled in (h-001 not activated, h-002 never tested); [[rubric_scorecard]] re-scored (6.7 self-score); [[experiments]] has EXP-011R/012
- ✅ (Oct 30) Deleted the three empty `Untitled*.canvas` files
- ⬜ Owner: set spend alerts on Meta and Baseten

## Step 3: deploy and video
- ✅ (Oct 30) Deployed without keys at https://anubhav-metahackathon.streamlit.app/; video flow works in incognito (owner checked). Kept running: with no keys it replays only and spends $0 (Oct 31)
- ✅ (Oct 30–31) [[demo_video]] rewritten around real runs, proof beat uses EXP-011R and EXP-012b
- ⬜ Owner: record the video with English subtitles (Nov 3); not recorded yet
- ✅ README: cited stats (Redseer Dec 2024; DPIIT–NCAER logistics cost) and hosted demo link
- ⬜ Owner: README hero GIF, quotes with the interviewee's permission, video link (Nov 3)
- ⬜ Dry-run submission, check commit authorship again (Nov 3); submit on Nov 4 IST

## Multi-agent redesign (D-044, [[Anubhav_MultiAgent_Design_v1]] §4.9)
Owner and Claude in parallel. The single Planner stays the baseline and fallback; Streamlit stays the hosted link until React is verified.

**Sprint 0: contract (Oct 31) ✅**
| # | Item | Status |
|---|---|---|
| S0.1 | Event schema `contracts/events.schema.json` (11 types) | ✅ |
| S0.2 | API contract `contracts/api.md` (dashboard, agents, learning, ledger, proof, chat + SSE with reconnect) | ✅ |
| S0.3 | Fixtures `web/fixtures/*.jsonl` (`scripts/make_fixtures.py`): a real Muse run (plain plan with lessons and a draft); Planner → Analyst hand-off; tool_missing → hand-off → query fails twice, fixed on attempt 3 (scripted model, real loop, broker and sandbox; labelled) | ✅ |

**Sprint 1: core agents (Oct 31 – Nov 1)**
| # | Item | Status |
|---|---|---|
| P1 | Agent registry as data (`configs/agents.yaml`, `agents/registry.py`): Planner, Analyst active; Tool Forge, Lesson Miner planned | ✅ |
| P2 | `graph.run(agent=…)`: agent's own prompt, `agent_id` + `depth` on every step; baseline untouched without it | ✅ |
| P3 | `delegate` (depth ≤ 2, no self-call, shared budget, partial answers flagged, teammate cost counted), teammates in `discover_capabilities`, audit records the acting agent | ✅ |
| P4 | Event store `events.py` (from any saved run, nested hand-offs, reconnect by seq) | ✅ |
| P5 | Retry cap (3 failed attempts per tool, then `RETRY_LIMIT`), `find_capability` with `tool_missing` | ✅ |
| P6 | `sequence_stops` (nearest town first from the depot; estimated, not optimized) | ✅ |
| P7 | Baseline intact: 336 old tests green; 20 new tests | ✅ |
| V1–V4 | React shell on the fixtures (Vite + TS, tokens, chat stream, Why this plan, roster) | ⬜ |
| V5 | Take the Streamlit-free parts out of `ui/core.py` into a service module | ⬜ |

**Owner's direction (Oct 31, evening): finish the whole backend first (every FastAPI endpoint the UI needs); React later.** Plan: [[backend_plan]] (proposed; 4 open decisions in its §6; B1 starts on the owner's go).

| # | Backend item ([[backend_plan]] §3) | Status |
|---|---|---|
| L0 | **Logs are the base (owner):** team runs saved whole with their events; every reader of runs sees teammates; `tool_usage`, `missing_tools` | ✅ Oct 31 |
| T1 | **Tool creation (owner's decisions):** candidate at 3+ different requests (`MIN_USES = 3`), any agent's query counts; `tool_missing` → Tool Forge (now active) writes the first read-only query; Forge suggests names, code falls back; a person approves; approved tools on the MCP server | ✅ Oct 31 (scripted model only; no live run yet) |
| B1 | Service layer `service/{session,runs,views}.py` (no framework); `ui/core.py` is a thin layer; team mode runs and saves through it; caps live here | ✅ Oct 31 (379 tests) |
| B2 | Live event streaming: `events.Emitter` used live and over saved runs (same stream); `service/stream.py` runs a request in a thread, writes each event at once, resumes by seq | ✅ Oct 31 |
| API | FastAPI: all endpoints in `contracts/api.md` (session, dashboard, chat + SSE, agents, lessons, tools, harness, packs, review, proof, ledger, logs, tool tracking, report); visitors isolated, including their saved live runs; shared or paid actions refused on the public host | ✅ Oct 31 (scripted model only) |
| B3 | A learning loop per agent: versions and rollback per agent, `team_probe`, gate blocks harm to another agent | ✅ Oct 31 |
| B4 | Knowledge per agent (`service/knowledge.py`, from the records; off in EXP-013) | ✅ Oct 31 |
| B5 | Routing evidence from runs (`logs.routing_stats`) and a `routing_hints` surface through the same test and approval | ✅ Oct 31 |
| B6 | Tool Forge: active; writes the first query (real model reaches it, smoke run); suggests names; code keeps the checks | ✅ Oct 31 |
| B7 | Lesson Miner: active; `records_digest`, `propose_lesson` through the evidence gate; a person approves. Not run on the real model yet | ✅ Oct 31 (scripted model) |
| B8 | Learning timeline for lessons, patches and tools, per agent (`/api/learning/timeline`, in the ledger) | ✅ Oct 31 |
| B9 | EXP-013: R1–R3 met (team default in the API), R4 not met; team not more accurate than one planner; $14.21 ([[experiments]]) | ✅ Oct 31 |
| B11 | Record team replays for the demo bundle (hosted replays are single-Planner); run the Lesson Miner on the real model (~$1–2) | ⬜ next |
| B12 | Show team runs in Streamlit, so the work is visible if React slips | ⬜ |
| B10 | Dockerfile built and checked locally (no keys in the image, non-root, replay works, paid routes refused); deploying the Space is the owner's step ([[deploy]]) | ✅ Oct 31 |
| Web | React app (V1–V4, V6–V9, V11–V15) | ⬜ later (owner's direction) |

## Cut
- ✂️ Hospital and call-centre demos, React frontend, government-docs RAG (D-039; [[ideas_parking_lot]])
- ✂️ Judge seed challenge UI, double-booking UI (Oct 30 optional list)
