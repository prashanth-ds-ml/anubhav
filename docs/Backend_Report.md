---
tags: [report, backend, api, ui]
status: Written Nov 1, 2026 from commit 3866489 (working tree also has the uncommitted benchmark guide and checker)
date: 2026-11-01
---
# Anubhav backend report, for building the UI and UX

Related: `contracts/api.md`, `contracts/events.schema.json`, [[demo_plan]], [[benchmark_data_guide]], [[decisions]].

**How this was checked:**
- Written from the source code, plus real responses captured from the running API in public replay mode with no keys. No model was called and no credits were spent.
- Flows that need a live model (sign-off, reject and revise, ask and resume) were not repeated for this report. Their behaviour comes from the code, the 537 tests and the $0.39 Spark 1.3 test in `artifacts/smoke_supervised.json`.
- Where `contracts/api.md` and the code differ, this report follows the code and lists the difference in section 14.

> **Since this report (build sprints, Nov 2):** new routes `GET /api/learning/lessons/{id}/evidence`, `GET /api/proof/registry` and `GET /api/runs/{id}/steps` (events, work per agent, mistake → fix pairs); `/api/proof` adds EXP-004, EXP-008 and EXP-011R per-company totals; a live run's drafts can be approved or rejected from the chat. The contract is `contracts/api.md`.

## Contents
1. [Summary](#1-summary)
2. [Architecture](#2-architecture)
3. [What happens on one request](#3-what-happens-on-one-request)
4. [The agents](#4-the-agents)
5. [The tools](#5-the-tools)
6. [Checks the model can't skip](#6-checks-the-model-cant-skip)
7. [How the system learns](#7-how-the-system-learns)
8. [Data and storage](#8-data-and-storage)
9. [Models, modes and spend limits](#9-models-modes-and-spend-limits)
10. [Events and logs](#10-events-and-logs)
11. [Full API reference](#11-full-api-reference)
12. [Saved demo runs](#12-saved-demo-runs)
13. [Measured results and what we can claim](#13-measured-results-and-what-we-can-claim)
14. [Gaps the UI must handle](#14-gaps-the-ui-must-handle)
15. [Backend to UI map, page by page](#15-backend-to-ui-map-page-by-page)
16. [The other session's React app](#16-the-other-sessions-react-app)
17. [Build, hosting and tests](#17-build-hosting-and-tests)

## 1. Summary
Anubhav is a Python agent system on Meta Muse. It plans truck drafts for a regional logistics company, in Telugu, Roman Telugu or English. It learns the company's unwritten rules from its own records. Code checks the evidence, and a person approves anything before it takes effect. It only ever makes drafts and never dispatches.

| Area | Built |
|---|---|
| Agent loop | Bounded LangGraph loop with limits on turns, tool calls and cost |
| Team | Planner leads Analyst, Tool Forge and Lesson Miner through `delegate` |
| Tools | 27 built-in tools, 2 analysis tools, 5 team tools, plus approved learned tools |
| Guards | Draft validator, reply check, evidence gate, leak check, SQL sandbox, per-visitor isolation |
| Supervision | Plan sign-off, reject with notes, ask a person, resume, hand-off after 3 refusals |
| Learning | Business rules (Loop B), how agents work (Loop A), new tools, shared packs, nightly review |
| Records | Full run traces, typed events, lesson and tool history, decision ledger |
| API | FastAPI with 54 routes, streaming events, one error shape, per-visitor cookie |
| Tests | 537 tests; lint, tests and build pass in GitHub Actions |

**What the UI does not have to fake:** turn-by-turn traces, teammates' steps, lessons used, before and after, and the learning history are all real saved data.

**What is still not real or not measured:** see sections 13 and 14.

## 2. Architecture
```text
Browser (React, later)
   |  /api/*  (JSON and server-sent events), cookie anubhav_sid
FastAPI: src/anubhav/api/
   |  routes.py translates HTTP to the service; deps.py gives each visitor a workspace
Service: src/anubhav/service/         no web framework; Streamlit and FastAPI both call it
   |  session.py    workspace, companies, spend guard
   |  runs.py       live runs, saved runs, replay matching, draft decisions
   |  stream.py     worker thread + event store, follow by seq
   |  checkpoints.py where a stopped run can resume
   |  views.py      dashboard read models, "why this plan"
   |  knowledge.py  what each agent knows
   |  proof.py      measured results from committed files
Agents: agent/graph.py (the loop), agents/team.py (delegate), agents/registry.py, agents/forge.py
Runtime: runtime/broker.py (tools), safety.py (validator), company.py (records and drafts), query.py (SQL sandbox)
Learning: learning/* (rules, gate, packs, new tools, profile), harness/* (Loop A), review.py (nightly)
Records: trace.py (runs), events.py (events), ui/logs.py (log read models)
Models: muse.py (Muse Spark 1.3, Muse Spark Open, Muse Voice Transcribe)
Also: mcp_server.py (the same tools over MCP), preflight.py (readiness check), data/ (world generator), eval/ (benchmark)
```

**Principles the UI should reflect:**
- The model proposes, code decides, and a person approves.
- A draft is never a dispatch. Approved means a person signed it off, and it is still not dispatched.
- No business facts are written into agent code (D-034). They are learned as lessons.
- Agents are data in `configs/agents.yaml`, not code.

## 3. What happens on one request
1. The browser sends `POST /api/chat` with the company, message, mode, model, `use_lessons` and `team`.
2. **Replay:** the server finds a saved run with exactly the same company, request text and lessons setting, and returns its `run_id`.
3. **Live:** the spend guard checks the key and limits. A worker thread starts and `run_id` returns immediately.
4. The browser opens `GET /api/chat/stream?run_id=...` and receives events.
5. The Planner reads the system prompt, business profile, approved lessons and harness guidance.
6. It calls tools through the broker. Every call is checked for company and role, then logged.
7. It may delegate to a teammate. The teammate's steps appear in the same stream, one level deeper.
8. A draft goes through the validator. If it passes, it holds the truck for that day.
9. Before finishing, the run re-checks its drafts and checks the reply. A failing reply goes back to the model in supervised runs.
10. The run ends as `answered`, `limit`, `error` or `needs_person`. A stream `end` event closes it.
11. The run is saved with its events, and a checkpoint is saved so it can resume.

**Limits on a lead run:** at most 8 turns, 12 tool calls and $0.40. The last turn is kept for a wrap-up, so the person always gets an answer about what was found and what is left.

## 4. The agents
From `configs/agents.yaml`. All four are active and default to Muse Spark 1.3 for live runs.

| Agent id | Name | Job | Talks to the person | Limits (turns, tools, $) |
|---|---|---|---|---|
| `planner` | Planner | Talks to the planner, plans drafts, hands off work | **Yes, the only one** | 8, 12, 0.40 |
| `analyst` | Analyst | Answers record questions with existing tools; never drafts | No | 6, 8, 0.12 |
| `tool_forge` | Tool Forge | Answers what no tool can, with one read-only query; names reused queries | No | 6, 8, 0.12 |
| `lesson_miner` | Lesson Miner | Reads a digest of records and proposes lessons | No | 5, 6, 0.12 |

**Delegation rules:**
- At most 2 levels deep, and an agent can't call itself.
- One shared budget of $0.40 for the whole request.
- A brief of 10 to 1,500 characters is required.
- `find_capability` ranks tools and teammates for a need. If nothing fits, it reports `tool_missing` and points to Tool Forge.

**Each agent has its own:**
- Instructions and versions. Baselines are `h-000`, `analyst-000`, `tool_forge-000` and `lesson_miner-000`.
- Knowledge: Planner 9 items for T01 in the capture, Analyst 6, Tool Forge 7, Lesson Miner 1.
- Totals from saved runs. These are below, for T01, from the current local history, and the numbers grow as runs are added:

| Agent | Runs | Answered | Stopped early | Tool calls | Tool errors | Cost |
|---|---|---|---|---|---|---|
| Planner | 75 | 74 | 1 | 386 | 5 | $3.00 |
| Tool Forge | 6 | 4 | 2 | 17 | 0 | $0.34 |
| Analyst | 6 | 4 | 2 | 27 | 4 | $0.51 |
| Lesson Miner | 2 | 0 | 2 | 12 | 0 | $0.19 |

**Show the Lesson Miner honestly.** Its only saved team run reached its limit and proposed no lessons. The measured mining results came from the offline miner. Its instructions were changed afterwards, and that change has not been tested on a real model.

## 5. The tools
Every tool has a name, description, input schema, action class (`read`, `draft` or `append`), and a category. Results use `{ok, result}` or `{ok: false, error: {code, message}}`.

| Category | Tools |
|---|---|
| Orders and sites | `find_site`, `list_sites`, `list_open_orders`, `get_order`, `get_site_constraints`, `get_route_info` |
| Fleet and drivers | `list_vehicles`, `check_vehicle_availability`, `list_drivers` |
| Planning | `plan_board`, `check_load`, `create_dispatch_draft`, `create_dispatch_drafts`, `list_dispatch_drafts`, `get_dispatch_draft`, `cancel_dispatch_draft` |
| Trips and documents | `list_trip_outcomes`, `trip_documents`, `record_driver_note` |
| History and performance | `trip_history`, `order_history`, `performance` |
| Knowledge | `get_transport_policy`, `search_notes`, `list_lessons` |
| System | `discover_capabilities`, `inspect_contract` |
| Analysis | `describe_tables`, `run_query` |
| Team | `delegate`, `find_capability`, `sequence_stops`, `records_digest`, `propose_lesson` |
| Supervised lead only | `ask_person` (handled by the agent loop) |
| Learned tools | Added per company after checks and a person's approval |

`sequence_stops` gives an estimate only: nearest town first from the depot, with no time windows. The UI must keep its label, "estimated, not optimized".

**The SQL sandbox (`run_query`):** one SELECT over an in-memory copy of that company's records, with time, row and length limits. Text from the records is marked as untrusted.

## 6. Checks the model can't skip
| Check | When | What the person sees |
|---|---|---|
| **Draft validator** | Every draft, whoever asks | Refusal or draft, with warnings such as the e-way bill |
| **Re-check at the end of a run** | Each draft the run made | `validator_check` with `tool: final_recheck` |
| **Re-check on approval** | When a person approves | Approval refused with reasons if the plan no longer holds |
| **Reply check** | Every lead reply | IDs must come from this run, and no dispatch may be claimed |
| **Reply sent back** | Supervised runs | `validator_check` with `tool: reply_check`, `attempt` n of 3 |
| **Tool retry cap** | Team or supervised runs | `retry` attempt 2 and 3 of 3, then `RETRY_LIMIT` |
| **Hand-off to a person** | Third refused tool or reply, or `ask_person` | `needs_person`, with the run stopped |
| **Ask rules** | `ask_person` | `LOOK_FIRST` if nothing was looked up, `ALREADY_ASKED` if repeated |
| **Evidence gate** | Every proposed lesson | Candidate, needs evidence, rejected or expired |
| **Tool checks** | Every tool candidate | Same rows as the originals, and works on held-out values |
| **Paired test gate** | Every agent change | Old vs new on the same requests |
| **Leak check** | Every shared pack | Private details found, normally none |
| **Per-visitor isolation** | Public host | Each visitor has their own drafts and lessons |

**The validator covers:** capacity, volume, site access, cold chain, segregation, availability, duplicates, order status and date, and fill. Its written thresholds come from `configs/operating_rules.yaml`. Approved policies block a draft, while advice appears as a warning.

### Draft states
```text
draft ---approve (re-checked)--> approved ---reject (notes)--> rejected
  |---reject (notes)--> rejected
  |---cancel--> cancelled
```
`draft` and `approved` hold the truck and orders. `rejected` and `cancelled` release them. Only a `draft` can be cancelled. Rejecting with `revise: true` sends the notes back to the agent as a new live run.

### Stopped runs
A run that ended as `needs_person`, `limit` or `error` can resume with a person's reply, as a new linked run with `resumed_from`.
- A run can only be resumed once, so a double click can't pay twice.
- If the resumed run crashes before saving, the person can try again.
- A resume needs a live model, so it counts against the spend limits.

## 7. How the system learns
There are three kinds of learning. **The UI should keep them separate, along with self-correction inside a run, which is not stored as learning.**

### Loop B: the business's unwritten rules
```text
records -> digest (code) -> Muse Spark 1.3 proposes -> evidence gate (code) -> person approves -> used in next run
```
| Lesson state | Meaning |
|---|---|
| `CANDIDATE` | Repeated, consistent evidence. Can be approved as advice or, if enforceable, as a policy |
| `NEEDS_EVIDENCE` | Only one piece of evidence. Can be approved as advice only |
| `ACTIVE_ADVISORY` | In use, as a warning and knowledge |
| `ACTIVE_POLICY` | In use, and the validator enforces it |
| `CHALLENGED` | New contradicting evidence |
| `REJECTED` | Refused by the gate or a person |
| `RETIRED` | Taken out of use |
| `EXPIRED` | A time-bound fact that ended |

- **Lesson kinds seen in the code and data:** `site_access`, `receiving_hours`, `night_only`, `time_window`, `moved_site`, `weekly_off`, `alias`, `real_capacity`, `vendor_reliability`, `closure`.
- Only `site_access` can become an enforced policy.
- The gate ignores the model's wording and confidence. A habit is not a rule; a rule needs something failing because of it.
- Every state change is an append-only event, so any approval can be audited and rolled back.

**The saved T01 lessons (11):** 9 advisory, 1 policy and 1 expired. The main demo lesson is `L-T01-002`, "Lakshmi Agencies, Jangaon: vehicles longer than 22 ft can't enter", with the evidence "3 refusal(s) of vehicles over 22 ft, none delivered". In the capture, no T01 lesson was waiting for approval, so **a fresh visitor has nothing to approve unless the UI offers a rollback first or the demo store is changed.** See gap 9 in section 14.

### Loop A: how each agent works
```text
problems in traces + feedback -> Muse proposes one small patch -> paired test -> person approves -> new version
```
- **Changeable parts:** response guidelines, tool hints, glossary, routing hints. A change affects one agent only.
- **Signals:** tool errors, repeated calls, too many calls, limit hits, feedback.
- **The gate refuses a change that:** loses drafts, adds tool errors, costs too much more, gets fewer correct answers, shows no improvement on the problem, or harms a teammate.
- **Current state:** Planner is on baseline `h-000`, with candidates `h-001` (tested, failed its gate) and `h-002` (proposed). No other agent has a trial version in the app's store.
- Changes are local-only because the harness is shared by everyone, so the public host shows them read-only.

### New tools
```text
No tool fits -> find_capability says so -> Tool Forge writes a query -> the query recurs for 3+ different requests
  -> candidate -> code parameterizes and checks it -> Tool Forge or code names it -> a person approves -> usable tool
```
- A person can promote a query early, and the checks stay the same.
- A learned tool is private to its company and never travels in a pack.
- The capture found 20 query groups for T01, and 3 had reached the threshold.
- Code built, checked and activated `weekday_wnum_by_town` in a test visitor without a model call.
- **Naming matters:** the suggested code names are clumsy, like `rows_by_dates`. On the public host code does the naming, because the paid naming step is off there.

### Sharing packs
- `POST /api/packs/publish` takes approved regional knowledge from T01 and T02 to TNEW and reports `items`, `skipped` and `leaks`.
- In the capture, the leak lists were empty.
- A receiving company can revoke everything it received.
- A fresh visitor's TNEW already has lessons from the bundled pack.

### Nightly review
`POST /api/review/run` reads recent runs and sends each problem to the right mechanism: tool-use problems to Loop A, corrections to Loop B, written queries to new tools. It runs free on the public host; the paid proposals only run locally.

### Per-agent knowledge and business profile
- `service/knowledge.py` keeps what each agent knows apart, counted from recorded data with no model.
- **Business profile:** code computes facts from the records (service area, clients, fleet, volume, goods, languages, busy days, written policies), and the owner can add fields: industry, what we move, priorities, key customers, notes. Each save is a new version, and the agent reads it as information rather than instructions.

### Self-correction inside a run (not learning)
The agent reads an error and fixes its next call, but nothing is stored. The saved example is `demo:new-tool-before`: `run_query` refused with `no such column: delivery_date`, and the next query worked.

## 8. Data and storage
**Synthetic world:** `src/anubhav/data/` generates 4 companies from a seed. Hidden rules are stored separately in `truth/`, and only evaluation may read them.

| Id | Name | Sites | Vehicles | Towns | Replays |
|---|---|---|---|---|---|
| `T01` | Sri Kakatiya Logistics | 45 | 18 | 12 | Yes |
| `TNEW` | Bhadrakali Transport Co (new) | 34 | 13 | 14 | Yes |
| `T02` | Ramappa Carriers | 50 | 14 | 16 | None |
| `T03` | Deccan Freight Services | 83 | 29 | 11 | None |

Each company uses a different database layout. The demo date is delivery on `2026-10-30`, with 14 open orders for T01. Worlds: demo `full_seed20261104`, test worlds 4111 and 5279, and the unused `7919` for the next benchmark.

| Stored in | What | Survives |
|---|---|---|
| `data/traces/*.jsonl` | Every run in full | Local or storage-backed host |
| `data/traces/events.sqlite` | Live events | Same |
| `data/traces/checkpoints.sqlite` | Conversations for resume | Same |
| `data/worlds/.../learning/` | Lesson stores, one per public visitor | Same |
| `data/worlds/.../runtime/sessions/` | Drafts and holds, one per visitor | Same |
| `data/harness/harness.sqlite` | Agent versions, feedback, practice | Same |
| `demo/` | Saved runs and lessons for a fresh install | In git |
| `artifacts/` | Experiment results shown on Proof | In git |

Space storage resets on restart unless persistent storage is attached. Bundled demo data comes back; visitors' work doesn't.

## 9. Models, modes and spend limits
| Picker label | Key in API | Model id | Used for | Credit |
|---|---|---|---|---|
| Replay (free) | none | none | Saved runs | $0 |
| Muse Spark 1.3 | `spark` (default) | `muse-spark-1.3` | Live agent, miner, patches | Meta |
| Muse Spark Open | `open` | `meta-models/muse-spark-open-1026` | Live agent; all measured results | Baseten |
| Muse Voice Transcribe | n/a | see `muse.py` | Voice input; no API route yet | Meta |

**Keys:** `meta_api` and `baseten_api_key`, in `.env` locally or the host's secrets. They are never returned or printed.

**Limits:**
- 8 live runs per visitor session.
- 60 live runs per day across the app.
- Muse Spark Open: 30 live runs per day.
- Each lead request: $0.40 at most.

**Credit position by our ledger:** Meta about $133.50 left, with $50 kept for the demo and judges. Baseten about $35.30 left, kept only for the demo and judges. The billing pages have not been checked, and live spend on the host is not logged to the ledger automatically.

**Reasons returned when a model can't run:**
| Situation | Message |
|---|---|
| No key | ``Live mode is off here (no `meta_api` set). Use Replay.`` |
| Session limit | `This session used its 8 live runs. Use Replay, or run it locally.` |
| Daily limit | `The demo's daily budget of 60 live runs is used up. Use Replay, or run it locally.` |
| Model limit | `This model's daily budget of 30 live runs is used up. Pick another model, or use Replay.` |

## 10. Events and logs
### The event
```json
{"run_id": "70176369a1", "seq": 0, "agent_id": "planner", "agent_run_id": "70176369a1", "caller": "person",
 "depth": 0, "ts": "2026-10-29T17:09:50", "type": "agent_start",
 "payload": {"request": "Plan a truck...", "model": "meta-models/muse-spark-open-1026", "lessons_in_prompt": 10}}
```
`run_id` is the whole request, and `agent_run_id` is that agent's part. `depth` is 0 for the lead and 1 or 2 for teammates, so use it for indenting. `seq` has no gaps.

### The 12 event types
| Type | Payload | Show as |
|---|---|---|
| `agent_start` | `request, model, lessons_in_prompt` | Agent starts; show the model and lesson count |
| `tool_call` | `tool, arguments` | Combine with its result as one card |
| `tool_result` | `tool, ok, result` (trimmed JSON text) or `error` | Success, or refused with its code |
| `retry` | `tool, attempt, of` | "Attempt 2 of 3" |
| `tool_missing` | `need, next_step` | Alert: no tool for this |
| `handoff` | `from, to, brief` | Hand-off card with the brief |
| `lesson_used` | `tool, lessons: [{id, rule, evidence}]` | Rule applied, with its evidence |
| `validator_check` | `tool, pass, draft_id?, error?, errors?, attempt?, of?, unknown_ids?, claims?, checked?` | Check passed or refused |
| `draft_created` | `draft_id, vehicle_id, orders, load` | Plan card |
| `learning_event` | `kind, agent, decision, ref?, state?, note?` | Proposal or decision |
| `needs_person` | `rule, question, agent, drafts, tools_used`, and `tool, last_error` or `refused_reply` | Alert and reply box |
| `agent_done` | `reply, stop, cost_usd, tool_calls, drafts, reply_check` | The answer; for a teammate, its summary |

### The stream
```text
event: agent_start
id: 0
data: {...event JSON...}

: keepalive

event: end
data: {"run_id": "...", "stop": "answered", "mode": "replay"}
```
- Reconnect with `after=<last seq>` or `Last-Event-ID`; only missed events come back.
- Replay paces events at 0.05 s by default.
- A live run keeps the connection open with a keepalive every 15 s.
- A reader gives up following after 300 s and then sends `end`, so check `stop` for null.

### Getting every turn
**Events do not include turn numbers, the model's text, tokens, per-step cost or latency.** Those are in the saved run:
```json
{"type": "model", "turn": 1, "content": null,
 "tool_calls": [{"name": "find_capability", "arguments": "{\"need\": \"...\"}"}],
 "tokens_in": 6038, "tokens_out": 371, "cost_usd": 0.00912425, "latency_s": 2.475, "agent_id": "planner", "depth": 0}
```
| Need | Use |
|---|---|
| Live card-by-card progress | `/api/chat/stream` |
| Every turn with tokens and cost | `/api/runs/{id}`: `trace`, and `children[].trace` for teammates |
| Ready-made readable timeline | `/api/logs/runs/{id}`: rows of `plan`, `act`, `observe`, `refused`, `answer`, `check`, `error`, with `agent` on teammates' rows |

Recommended: stream for progress, then fetch `/api/runs/{id}` after `end` for token and cost detail.

**Trace step types:** `model`, `tool`, `reply_refused`, `model_error`, `wrap_up`, `finish`.

### Log views
| Endpoint | Gives |
|---|---|
| `/api/logs/runs` | Run list: agents, tool calls, drafts, stop, cost, issues |
| `/api/logs/tools` | Each agent and tool: calls, failed, last used; plus missing tools |
| `/api/logs/agents` | Each agent's totals, with teammate costs separated |
| `/api/logs/routing` | Task kind, who handled it, how it went |
| `/api/logs/models` | What each Meta model did |
| `/api/logs/events` | Merged history with streams `run`, `lesson`, `harness`, `tool`, `review`, `feedback` |
| `/api/ledger` | Hand-offs, drafts, checks, lessons used, missing tools, learning decisions |
| `/api/learning/timeline` | Every learning decision |

## 11. Full API reference
54 routes under `/api`: 34 GET, 19 POST, 1 PUT. Interactive docs are at `/docs`. `company` defaults to `T01`.

**Session:** a public host sets the `anubhav_sid` cookie on first use, so the frontend must send credentials. There is no login. Locally, everyone shares one workspace.

**Errors always look like:**
```json
{"error": {"code": "NO_REPLAY", "message": "No saved run for this request and setting.", "suggestions": ["Roman Telugu", "Telugu"]}}
```

### Session and setup
| Route | Purpose | Response fields |
|---|---|---|
| `GET /health` | Alive | `ok` |
| `GET /session` | Model picker and limits | `public, default_mode, default_team, models{label: {available, reason}}, live_runs_left, caps{per_session, per_day}` |
| `GET /companies` | Company selector | `company, name, sites, vehicles, towns, plan_date` |
| `GET /suggestions?company&use_lessons` | Request chips | `label, request, has_replay` |
| `POST /session/reset-drafts?company` | Start over | `ok` |

### Chat and runs
| Route | Body | Response |
|---|---|---|
| `POST /chat` | `company, message (1-2000), mode, model, use_lessons, team` | `run_id, mode`, plus `replay_of, reason` when they apply |
| `GET /chat/stream?run_id&after` | | Event stream |
| `GET /runs/{id}` | | Whole run, with `trace` and `children` |
| `POST /runs/{id}/resume` | `reply (1-2000), model` | `run_id, resumed_from, mode` |
| `POST /runs/{id}/feedback` | `rating 0 or 1, category, note` | `feedback_id` |
| `GET /handoffs?company` | | `run_id, request, handoff, saved_at` |

Feedback categories: `not_from_data`, `language`, `wrong_plan`, `wrong_tool`, `other`, and `good`.

### Dashboard
| Route | Body | Response |
|---|---|---|
| `GET /dashboard/orders` | | `delivery_date, orders[order_id, site_id, site, town, window, priority, kg, m3, value_rs, cases, handling_classes, in_draft]` |
| `GET /dashboard/fleet` | | `delivery_date, vehicles[vehicle_id, class, length_ft, payload_kg, volume_m3, body, owner, vendor, reg_no, status, document dates, held_today, workshop_day_of_month, free, reason]` |
| `GET /dashboard/drafts` | | `{drafts, source: "live"}` for this visitor's plans |
| `GET /dashboard/drafts?run_id` | | `{drafts, source: "run"}` for what a saved run made |
| `POST /dashboard/drafts/{id}/decide` | `decision, notes, revise, model` | `draft_id, status, revise_run_id`, and `reason` if no revision started |
| `POST /dashboard/drafts/{id}/cancel` | | The cancel result |
| `GET /dashboard/company` | | `company, facts, owner, owner_fields, agent_reads, version, versions, written_rules` |
| `PUT /dashboard/company/profile` | `owner{...}` | Same as above |

**A draft contains:** `draft_id, status, vehicle_id, delivery_date, orders, load{kg, m3, value_rs, stops, sites, handling_classes}, warnings[{code, message}], stops{from, stops[stop, site_id, name, town, leg_km, total_km, est_minutes_total], total_km, method}, why{run_id, request, lessons, lessons_in_prompt, agents, tools, checks}, source`. A live draft also has `decisions`. A replay's `status` is the text `draft (not dispatched)`.

### Agents
| Route | Response |
|---|---|
| `GET /agents?company` | `agent, name, purpose, status, voice, model, handles, version, versions_tried, knowledge_items` |
| `GET /agents/{id}?company` | Adds `instructions, limits, active_surfaces, knowledge, versions[... diff, test_passed, test_reasons], paired_tests, scores, totals` |

### Lessons
| Route | Body | Response |
|---|---|---|
| `GET /learning/lessons?company&state` | | `lesson_id, kind, params, claim, state, effect, gate{verdict, reason, support, counter, strength, enforceable}, miner{evidence, counter_evidence, alternatives, confidence, model, cost_usd...}, source, reviewer, verified, what, events[...]` |
| `POST /learning/lessons/{id}/decide` | `decision: approve, reject, retire, rollback; effect; verified; why` | The lesson |
| `GET /learning/timeline?company&agent` | | `ts, kind, agent, decision, ref, by, what, state, note` |
| `POST /learning/mine` 🔒 | `by: agent or offline` | `new, cost_usd`, plus `run_id, stop` |

Reject and retire need a `why`.

### New tools
| Route | Body | Response |
|---|---|---|
| `GET /tools?company&status` | | `tool_id, name, description, template, params, status, checks...` |
| `GET /tools/candidates?company` | | `key, template, requests, uses, agents, params, reached_threshold, threshold, suggested_name, suggested_description` |
| `POST /tools/candidates/{key}/check` | `name?, description?` | The candidate, with `checks{pass, same_rows, held_out...}, named_by` |
| `POST /tools/{id}/decide` | `approve, note` | The tool |
| `POST /tools/{id}/retire` | | The tool |

### Learning views
| Route | Response |
|---|---|
| `GET /compare?company&request` | `request, cold, with_lessons, with_learned_tools`; each is null or `run_id, reply, drafts, tool_calls, cost_usd, agents, lessons_in_prompt, learned_tools` |
| `GET /packs?target` | `published, received` |
| `POST /packs/publish` | `sources, target, accept_rules`, returning `pack, from, to, items, skipped, leaks, imported` per source |
| `POST /packs/revoke?target` | `revoked` |
| `POST /review/run?company` | `since, runs, feedback, tool_use, by_agent...` |
| `GET /review/history?company` | Past reports |
| `GET /report/weekly?company` | `company, markdown` |

### Tuning
| Route | Response |
|---|---|
| `GET /harness?agent` | `agent, active, versions[... diff], feedback, categories` |
| `GET /harness/problems?agent` | `trace_issues, feedback, routing_evidence` |
| `GET /practice` | `round, version, split, questions, answers_right, fitting_tool, no_lookup, tool_errors, cost_usd` |
| `POST /harness/propose` 🔒, `/harness/{v}/probe` 🔒, `/harness/{v}/decide` 🔒, `/harness/rollback` 🔒, `/practice` 🔒 | Local only |

### Proof and logs
| Route | Response |
|---|---|
| `GET /proof` | Results `EXP-011, EXP-011R, EXP-012, EXP-012b, EXP-013, EXP-009, EXP-009b`, each with `id, file, measured_on` and its numbers |
| `GET /proof/curve` | `{measured: false, note}` today |
| `GET /ledger?company&agent&type&limit` | Events, newest first |
| `GET /logs/*` | See section 10 |

🔒 returns 403 `READ_ONLY_PUBLIC` on the public host. Disable these with a visible reason.

### Error codes to handle
| Code | Status | Meaning | UI response |
|---|---|---|---|
| `NO_REPLAY` | 404 | No saved run; `suggestions` are labels | Offer the chips |
| `NOT_FOUND` | 404 | Unknown item | Plain message |
| `BAD_ARGS` | 422 | Invalid input | Show on the field |
| `NOT_ALLOWED` | 409 | Approval re-check failed or wrong state; has `errors` | Show the reasons |
| `NOT_WAITING` | 409 | The run isn't waiting | Send a new message |
| `ALREADY_RESUMED` | 409 | Already resumed | Refresh |
| `CAP_REACHED` | 409 | A limit was reached | Offer Replay |
| `NO_KEY` | 409 | No model key | Offer Replay |
| `CONFLICT` | 409 | State conflict | Show message and refresh |
| `PATCH_REFUSED`, `NOTHING_TO_FIX`, `NOTHING_TO_ROLL_BACK` | 422, 409 | Tuning | Local only |
| `READ_ONLY_PUBLIC` | 403 | Local-only action | Disabled with reason |
| `PERMISSION_DENIED` | 403 | Role not allowed | Plain message |
| `INTERNAL` | 500 | Server error; no detail by design | Retry or Replay |

**A live request without a key doesn't fail.** `POST /chat` returns 200 with `mode: "replay"` and a `reason`. Always read `mode`, and show the reason.

## 12. Saved demo runs
`demo/replay_runs.jsonl` holds 32 real runs, **all on Muse Spark Open**. 6 are team runs and 26 are single Planner.

| Label | Company | Who | Shows | Cost |
|---|---|---|---|---|
| `demo:team:cold` | T01 | Planner | Roman Telugu request, no lessons: **V11, 32 ft** | $0.062 |
| `demo:team:lessons` | T01 | Planner | Same request with lessons: **V08, 22 ft** | $0.055 |
| `demo:team:nickname` | T01 | Planner | "Pedda godown" resolved by a learned nickname: V05, 14 ft | $0.052 |
| `demo:team:new-tool` | T01 | Planner + Tool Forge | Real hand-off and a written query | $0.110 |
| `demo:team:data` | T01 | Planner + Tool Forge + Analyst | A data question across teammates | $0.086 |
| `demo:team:miner` | T01 | Lesson Miner | Reached its limit, proposed nothing | $0.096 |
| `demo:new-tool-before` | T01 | Single | 5 calls, **a refused query it then fixed** | $0.066 |
| `live:c5-learned-tool` | T01 | Single | Same question using the learned tool: 1 call | $0.016 |
| `exp008:T01:cold:*`, `:lessons:*` | T01 | Single | en, rt, te, mix: V11 32 ft vs V08 22 ft in all 4 | ~$0.05 each |
| `exp008:TNEW:cold:*`, `:lessons:*` | TNEW | Single | New company without and with a pack | ~$0.05 each |
| `probe:gaps-dev`, `live:c2-check` | T01 | Single | Data questions in 3 languages | $0.03-0.08 |
| `golden_path:ambiguous` | T01 | Single | "Warangal load", answered without stopping | $0.011 |

### Which chip replays when
| Chip | T01, lessons on | T01, lessons off | TNEW |
|---|---|---|---|
| Roman Telugu, Telugu, English, Mixed | Yes | Yes | Yes, on and off |
| Nickname | Yes | **No** | No |
| Ambiguous | **No** | Yes | No |
| New tool | **No** | Yes | No |

**The UI must send the matching `use_lessons` value for each chip, or use `has_replay` from both settings.** Otherwise the last two chips return `NO_REPLAY` on the default setting.

### What the replays do not contain
| Moment | In the demo replays? | Where it exists |
|---|---|---|
| `needs_person` | No | Fixture; Spark 1.3 test artifact; live |
| `tool_missing` | No | Fixture; live |
| `retry` event | No | Fixture; live |
| Reply refused | No | Spark 1.3 test artifact; live |
| A refused tool then fixed | **Yes**, as a failed step in `demo:new-tool-before` | |
| `learning_event` | No | Timeline endpoint instead |

Fixtures in `web/fixtures/` come from the real agent loop with a **scripted mock model**. They are for building and testing the UI. If ever shown to judges, they must be labelled as scripted.

## 13. Measured results and what we can claim
**All measured on Muse Spark Open, and every case was generated by our own code.**

| Result | Number | Applies to |
|---|---|---|
| EXP-011R: learns unwritten rules | 48% to 90%, replicated 3 of 3 repeats | Single Planner |
| EXP-011R: new company, day 1 | 33% to 100%, 3 of 3, leak check 0 | Single Planner |
| EXP-011R by company | T01 21/42 to 36/42; T02 26/36 to 36/36; new 18/36 to 36/36 | Single Planner |
| EXP-011R safety | Unsafe with learning: 0 | Single Planner |
| EXP-009b: mining quality | 90% precision, 69% recall, 0 traps | Offline miner |
| EXP-012b: learned tools | Used in 14/16; 20% fewer calls (30% bar **not met**); 24% cheaper | Single Planner |
| EXP-013: team vs one | 47/54 vs 48/54; 0 unsafe; 1.36x the cost | Team |
| EXP-013: after learning | 46/54; routing 91% to 98% (bar not met) | Team |
| EXP-010: tool practice | 16/16 before and after; change rejected | Single Planner |
| Real capacity lesson | 0/6 with lessons; **not improved** | Single Planner |

**Spark 1.3 test ($0.39, 6 runs, not a benchmark):**
- Worked: approve, reject with notes (V08 to V09), asking "Which site is the extra load for?", resume, and the reply check (`O00871` refused, then corrected to `T01-O00871`).
- Didn't happen: on "Warangal load" it drafted all three orders instead of asking.

### The UI must not say
- The team is more accurate than one planner.
- Each agent, or the whole team stage by stage, has improved. EXP-014 hasn't run, and `/api/proof/curve` returns `measured: false`.
- The agent learned to pick the right tool. It was already at 100%, and the one change was rejected.
- The Lesson Miner agent works. Its one real run proposed nothing.
- The measured numbers apply to Muse Spark 1.3.
- A replay was recorded on the model the visitor selected. Replays are all Muse Spark Open.

### The UI can say
- Same request, same model: 32 ft without lessons, 22 ft with the learned rule, citing it.
- A new company gets the benefit on day 1.
- A repeated query became a tool: 5 calls to 1, $0.066 to $0.016. This is one example, from when the threshold was 2.
- It refused a change that showed no gain, and that refusal is visible.
- Nothing takes effect without a check and a person.

## 14. Gaps the UI must handle
| # | Gap | Impact | Recommended handling |
|---|---|---|---|
| 1 | `POST /api/voice` doesn't exist; `muse.transcribe` does | No voice input through the API | Port the route; test once on Meta credits |
| 2 | `GET /api/capabilities` doesn't exist | The other session's app calls it | Use `/session`; add voice status there |
| 3 | Events have no turn, token or cost data | No per-turn numbers while streaming | Fetch `/api/runs/{id}` after `end` |
| 4 | Replay isn't matched by model | Picking a model doesn't change a replay | Label each run with `agent_start.model` |
| 5 | Replay needs the exact text | Typed variations return `NO_REPLAY` | Use chips; optional closest-match on the client |
| 6 | No saved `needs_person`, `tool_missing` or `retry` | Replay can't show them | "Ask me" runs live; add a recording if budget allows |
| 7 | Replay drafts aren't real | Approve returns `no draft` | "Saved run" label and **Try this live** |
| 8 | T02 and T03 have no replays | Empty experience | Offer only T01 and TNEW in the selector |
| 9 | No T01 lesson is waiting for approval | The approve step can't be shown from fresh | Decide: seed a waiting lesson in the demo store, or show saved history |
| 10 | Per-agent `scores` and curve are empty | No improvement chart | Show "not measured yet" |
| 11 | `/compare` prefers single-Planner runs | It won't show team pairs | Fine for before and after; link team runs separately |
| 12 | `/compare` needs a saved pair | Most requests return nulls | Offer the fixed pairs: planning and New tool |
| 13 | Two labels vs keys in the picker | `/session.models` uses labels, while `/chat` uses `spark` and `open` | Map: 1.3 to `spark`, Open to `open` |
| 14 | Tool names from code can be clumsy | Odd labels on the public host | Show the description first |
| 15 | Docs and code differ on `/dashboard/drafts` | `api.md` shows a list; code returns `{drafts, source}` | Follow the code; I'll correct the doc |
| 16 | The Dockerfile doesn't build React | Host serves the API only | Add a Node build stage; `web/dist` is served automatically |
| 17 | No CORS is set | Vite dev server can't call the API directly | Use a Vite proxy for `/api` |
| 18 | Log endpoints re-read the trace files on each call | Could feel slow as history grows | Show loading states; revisit only if slow |
| 19 | Host storage resets on restart, including the daily count file | The limit could reset | Attach storage or accept it; billing alerts are the backstop |

## 15. Backend to UI map, page by page
### Every page: top bar
| Element | Source |
|---|---|
| Company selector, T01 and TNEW | `/companies` |
| Model picker with reasons | `/session` |
| Live runs left | `/session.live_runs_left` |
| Replay or live badge | `/chat.mode`, `/chat.reason` |

### Page 1: Try it
| Element | Source | Notes |
|---|---|---|
| Request chips | `/suggestions` | See section 12 for `use_lessons` |
| Text box | `/chat` | Handle `NO_REPLAY` |
| Voice | Gap 1 | Transcript stays editable before sending |
| Lessons on or off | `use_lessons` | Makes the before and after obvious |
| Agent activity cards | `/chat/stream` | Indent by `depth`, tag by `agent_id` |
| Turn details | `/runs/{id}` | Tokens, cost and time per turn |
| The answer | `agent_done` at depth 0 | May be Telugu; needs the right font |
| Plan card | `/dashboard/drafts` | `?run_id=` for replay; stops marked estimated |
| Why this plan | `draft.why` | Lessons, agents, tools, checks |
| Approve or Reject with notes | `/drafts/{id}/decide` | Live only; notes required on reject |
| Following a revision | `revise_run_id`, then stream | |
| Waiting for you | `/handoffs`, `needs_person` | Reply through `/runs/{id}/resume` |
| Thumbs up or down | `/runs/{id}/feedback` | |
| Orders and trucks, collapsed | `/dashboard/orders`, `/fleet` | |
| Start over | `/session/reset-drafts` | |

### Page 2: What it learned
| Element | Source | Notes |
|---|---|---|
| Before and after | `/compare` | Fixed pairs |
| Rules list | `/learning/lessons` | `what`, `state`, `gate`, `miner.evidence` |
| Approve, reject, roll back | `/learning/lessons/{id}/decide` | Per-visitor, and safe to try |
| Rejected or expired rules | Same, filter by state | Shows it doesn't learn just anything |
| Tool candidates | `/tools/candidates` | Show requests vs threshold |
| Run checks, approve | `/tools/candidates/{key}/check`, `/tools/{id}/decide` | No model needed on the public host |
| Tool before and after | `/compare` with New tool | 5 calls to 1 |
| Share with new company | `/packs`, `/packs/publish`, `/packs/revoke` | Show `leaks` |
| Business profile | `/dashboard/company` | Editable owner fields |

**Label the three kinds:** fixed itself in this run, learned for next time, tried and refused.

### Page 3: Proof
| Element | Source | Notes |
|---|---|---|
| Headline numbers | `/proof`: EXP-011R | Say what each measured |
| Team vs one planner | `/proof`: EXP-013 | Say it isn't more accurate |
| Mining quality | `/proof`: EXP-009b | Precision, recall, traps |
| New tools | `/proof`: EXP-012, EXP-012b | Include the missed bar |
| Tool-use loop | `/practice`, `/harness` | No gain, so rejected |
| Whole-system curve | `/proof/curve` | "Not measured yet" until EXP-014 |
| Limits | Fixed text from the README | Always visible |
| Weekly report | `/report/weekly` | Link |

### Page 4: Under the hood
| Element | Source | Notes |
|---|---|---|
| Runs list | `/logs/runs` | Filter by issues |
| One run, turn by turn | `/runs/{id}`, `/logs/runs/{id}` | Teammates in place |
| Mistakes and recoveries | `tool` steps with `ok: false` | Start with `demo:new-tool-before` |
| Agent selector | `/agents`, `/agents/{id}` | Instructions, versions, knowledge, tests |
| Each agent's totals | `/logs/agents` | |
| Tool tracking | `/logs/tools` | Calls, failures, missing |
| Routing | `/logs/routing` | |
| Decision ledger | `/ledger` | Filter by agent and type |
| Learning timeline | `/learning/timeline` | Filter by agent |
| Models and cost | `/logs/models` | |
| Nightly review | `/review/run`, `/review/history` | Free on the public host |
| Tuning | `/harness`, `/harness/problems` | Read-only on the public host |

### The states each page needs
| State | Example |
|---|---|
| Loading | First call while the company loads |
| Empty | "No plans yet. Try a request." |
| Replay label | "Saved run · Muse Spark Open · date" |
| Live label | "Live · Muse Spark 1.3 · 5 runs left" |
| Fell back | The `reason`, then the replay |
| Not measured | Text only, never a placeholder chart |
| Disabled action | Button off, with the reason |
| Stream cut | Reconnect with `after` |
| Unsafe claims | Never "dispatched"; always "draft" or "approved, not dispatched" |

## 16. The other session's React app
The web handoff was built against an older backend (336 tests). Its React app in `web/` is useful, but its server and contract are out of date.

| In the handoff | Repo today | Action |
|---|---|---|
| `web/` app and tests | No app yet | **Take it** |
| Root `api/app.py` | `src/anubhav/api/` is newer | **Don't take** |
| `src/anubhav/ui/core.py`, `service.py` | `service/` package | **Don't take** |
| `contracts/*`, `web/fixtures/*` | Newer here | **Keep ours** |
| `Dockerfile` | Ours has the current packaging | Merge in only the Node build |
| `POST /api/voice`, `web/src/components/Mic.tsx` | No route | Port the route |
| Tests in `tests/api/` | Different API | Reuse only the voice ideas |

**Field changes the React app needs:**
| It reads | Backend sends |
|---|---|
| `agent_start.brief` | `agent_start.request` |
| `agent_done.summary` | `agent_done.reply` |
| `tool_result.summary` | `tool_result.result` or `error` (trimmed JSON text; build a readable line on the client, or add a server field) |
| `retry.max_attempts`, `retry.error` | `retry.of` only |
| `tool_missing.searched` | `tool_missing.next_step` |
| `handoff.caller`, `handoff.target` | `handoff.from`, `handoff.to` |
| `lesson_used.lesson_id`, `.text` | `lesson_used.lessons[]{id, rule, evidence}` |
| `validator_check.verdict` | `validator_check.pass` |
| `draft_created.stops` | `draft_created.orders`, with stops from `/dashboard/drafts` |
| `learning_event.detail` | `learning_event.decision`, `.note` |
| `/api/capabilities` | `/api/session` |
| `/api/learning/agents` | `/api/agents` |
| Not handled | `needs_person`, `agent_run_id`, `seq` as required |

## 17. Build, hosting and tests
```text
uv sync
uv run uvicorn anubhav.api.app:app --port 7860     # API, and /docs
uv run streamlit run streamlit_app.py              # the current UI
uv run pytest -q                                   # 537 tests, no keys, no credits
uvx ruff@0.14.0 check .                            # lint
uv run anubhav-preflight                           # readiness, lists models only
```
| Setting | Effect |
|---|---|
| `ANUBHAV_PUBLIC=1` | Per-visitor drafts and lessons, and local-only actions locked |
| `meta_api`, `baseten_api_key` | Turn on each live model |
| `ANUBHAV_HOME` | Where `configs/` and `data/` live |

**Hosting:**
- The Dockerfile is a non-root image on port 7860 with the demo world built in, and it was rebuilt and checked on Nov 1.
- `create_app` serves `web/dist` at `/` when it exists.
- The API can run with or without keys. Without them, it is replay only and costs $0.
- Streamlit stays hosted until React passes in an incognito window.
- Keys and the Space are the owner's steps, in the host's secrets.

**Tests by area (537 in total):** agents, API, data generator, benchmark, harness, learning, runtime, safety, service including streaming and supervision, and UI helpers. Tests use a scripted model, so they spend nothing. CI ran on GitHub for `3866489`: lint, tests and package build all passed.

**Not verified:**
- The hosted app since the latest pushes.
- Supervised runs on Muse Spark Open.
- The three-refusal hand-off on a real model.
- Voice through the API, because there is no route yet.
- Actual spend on the billing pages.

**Open items that affect the UI:**
- The React and hosting merge (section 16).
- Benchmark question set and EXP-014 on Meta credits, which needs the owner's go-ahead.
- Gap 9: how a fresh visitor sees a lesson approval.
