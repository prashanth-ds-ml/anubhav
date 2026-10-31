---
tags: [plan, backend, api, multi-agent]
status: IN PROGRESS (owner's go, Oct 31). Build status in [[todo]].
date: 2026-10-31
---
# Backend plan: FastAPI for the React app, and the rest of the multi-agent work

Design: [[Anubhav_MultiAgent_Design_v1]] (D-044). Contract: `contracts/api.md` and `contracts/events.schema.json`. Status: [[todo]], section "Multi-agent redesign".
**Owner's direction (Oct 31):** finish the whole backend first, with every FastAPI endpoint the UI/UX needs. The React web app comes later.

## 0. Where we are (Oct 31, commit `c5508f8`)
- **Done:** Sprint 0 (the contract and three schema-checked fixtures in `web/fixtures/`).
- **Done:** Sprint 1 in Python:
  - `configs/agents.yaml` and `src/anubhav/agents/registry.py`;
  - `agents/team.py` (`delegate`, `find_capability`, `sequence_stops`);
  - `graph.run(agent=…)` with agent tags and a 3-attempt retry cap;
  - `src/anubhav/events.py` (`from_run`, `EventStore`);
  - `scripts/make_fixtures.py`.
- **Tests:** 356 pass. The single-Planner baseline is unchanged.
- **Not started:** the service layer, FastAPI, live streaming, per-agent learning, Tool Forge and Lesson Miner as agents, the benchmark, Docker.

## 1. Shape
```
src/anubhav/service/     framework-free core (taken out of ui/core.py); Streamlit and FastAPI both call it
  session.py             per-visitor state: companies, lesson store, drafts, spend caps (replaces st.session_state)
  runs.py                replay matching, live run, team run, saving runs and events
  views.py               read models for dashboards (orders, drafts + stops + "why", fleet, profile)
src/anubhav/api/         FastAPI: thin routers only, no business logic
  app.py  deps.py  errors.py  routers/{meta,dashboard,chat,agents,learning,tools,harness,packs,review,proof,logs}.py
```
**Rules for this layer:**
- Routes only translate HTTP to service calls and back.
- Every action still goes through the broker, the validator, the evidence gate and the person-approves steps, as now.
- Errors use the broker's codes plus `CAP_REACHED`, `NO_REPLAY` and `READ_ONLY_PUBLIC`.
- Replay is the default mode. Live mode keeps the caps: 8 runs per session, 60 per day.

**What has to come out of `ui/core.py`** (functions that use `st.session_state` or Streamlit caching):
- `_sid`, `company`, `store`, `live_ready`, `live_client`, `run_live`;
- the cached readers (`ensure_world`, `harness_store`, `recent_runs`).

**What moves unchanged:** `find_replay`, `replayable`, `summarize`, `drafts` and `lessons_used`.

## 2. Endpoints
✱ = changes data · 🔒 = refused on the public host (`ANUBHAV_PUBLIC=1`), as the Streamlit buttons are now.

**Meta and session**
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/health` | Host check | – |
| GET | `/api/session` | Session cookie, mode, live runs left, which models have keys | `live_ready` |
| GET | `/api/companies` | Company list and names | `COMPANIES`, `CompanyData` |
| GET | `/api/suggestions?company=` | Suggested requests that have saved replays | `SUGGESTIONS`, `replayable` |
| POST ✱ | `/api/session/reset-drafts` | "Reset today's drafts" | `runtime.reset` |

**Dashboard** (centre tabs)
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/dashboard/orders?company=` | Open orders for tomorrow, with an "in a draft" flag | broker `list_open_orders`, `orders_in_drafts` |
| GET | `/api/dashboard/drafts?company=` | Drafts with ordered stops, load and fill %, verdict, and **why this plan** (lessons, agents and tools, from the run's events) | `runtime.drafts`, `sequence_stops`, `events` |
| POST ✱ | `/api/dashboard/drafts/{id}/cancel` | Cancel a draft | broker `cancel_dispatch_draft` |
| GET | `/api/dashboard/fleet?company=` | Vehicles, free tomorrow or not, and why | broker `plan_board` / `list_vehicles` |
| GET | `/api/dashboard/company?company=` | Business profile and written rules | `learning/profile.py`, `get_transport_policy` |
| PUT ✱ | `/api/dashboard/company/profile` | Owner edits the profile (a new version) | `profile.save` |

**Chat** (right panel)
| | Path | For | Built on |
|---|---|---|---|
| POST ✱ | `/api/chat` | `{company, message, mode, use_lessons, team, history}` → `{run_id, mode, reason}`. Replay matches a saved run; live starts it in the background | `find_replay`, `run_live`, `agents.team.run` |
| GET | `/api/chat/stream?run_id=&after=` | SSE of typed events; resumes with `after` or Last-Event-ID; ends with `end` | `EventStore`, live queue (B2) |
| GET | `/api/runs/{run_id}` | A whole saved run, nested teammate runs included | `trace.load` |
| POST ✱ | `/api/runs/{run_id}/feedback` | Thumbs up/down, category, note (feeds Loop A) | `HarnessStore.add_feedback` |

**Agents and learning**
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/agents` | Roster: purpose, status, version, knowledge size, live/idle | `registry`, B3 |
| GET | `/api/agents/{id}` | Instructions, versions and diffs, paired tests, rejected changes with reasons, learning curve | B3 |
| GET | `/api/learning/lessons?company=&state=` | Lessons with evidence, gate verdict and approver | `LessonStore` |
| POST ✱ | `/api/learning/lessons/{id}/decide` | Approve or reject a lesson | `LessonStore` |
| POST ✱🔒 | `/api/learning/mine` | "Mine my records now" (live Muse Spark 1.3) | `learning/miner.py` |
| GET | `/api/learning/timeline?company=` | `learning_event`s, newest first | B8 |

**New tools**
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/tools/candidates?company=` | Reused queries, grouped, with check results | `newtools.groups`, `check` |
| POST ✱ | `/api/tools/candidates/{key}/approve` | Approve as a tool: name and description; the checks run again | `newtools.propose`, `decide` |
| POST ✱ | `/api/tools/{id}/retire` | Retire a tool | `newtools.decide` |
| GET | `/api/tools?company=` | Active and retired tools | `newtools.tools` |

**Tuning: Loop A** (all 🔒 on the public host; read-only there)
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/harness?agent=` | Active version, candidates, feedback queue | `HarnessStore` (per agent after B3) |
| POST ✱🔒 | `/api/harness/propose` | Ask Muse for a patch | `loop.propose` |
| POST ✱🔒 | `/api/harness/{v}/probe` | Paired test | `loop.probe` |
| POST ✱🔒 | `/api/harness/{v}/decide` | Turn a version on or reject it | `HarnessStore.decide` |
| POST ✱🔒 | `/api/harness/rollback` | Roll back | `HarnessStore.rollback` |
| GET, POST ✱🔒 | `/api/practice` | Tool-practice results; "Practice now" | `harness/practice.py` |

**Sharing, review, proof, logs**
| | Path | For | Built on |
|---|---|---|---|
| GET | `/api/packs` | Published domain packs | `learning/pack.py` |
| POST ✱ | `/api/packs/publish` | Publish and accept a pack | `pack.publish` |
| POST ✱ | `/api/packs/revoke` | Revoke all packs | `pack` |
| POST ✱ | `/api/review/run?company=` | Nightly review (live part only if keys) | `review.review` |
| GET | `/api/review/history` | Past reviews | `review.reviews` |
| GET | `/api/proof` | EXP-009/009b, 011, 011R, 012/012b and later, each labelled with the version it measured | `artifacts/` |
| GET | `/api/ledger?company=&agent=&type=` | Decision history: hand-offs, drafts, checks, lessons used, learning events | `EventStore` |
| GET | `/api/logs/runs` | Run timeline | `ui/logs.py` `timeline` |
| GET | `/api/logs/runs/{id}` | One run's issues | `run_issues` |
| GET | `/api/logs/models` | What each Meta model did | `model_roles` |
| GET | `/api/report/weekly?company=` | Weekly report | `app_pages/report.py` logic |

About 45 endpoints in all. Many wrap functions that already exist.

## 3. Backend work beyond the endpoints
| # | Work | Why | Design ref |
|---|---|---|---|
| B1 | **Service layer:** take the Streamlit-free parts out of `ui/core.py`; keep Streamlit working on top of it | One core for both front ends; the hosted Streamlit link stays safe | V5 |
| B2 | **Live event streaming:** a hook in `graph`/`broker` emits each step as it happens into a queue and the event store; the live run runs in a worker thread; SSE reads from the queue | The UI shows who is acting right now | P13 |
| B3 | **A learning loop per agent:** Loop A versions keyed by `agent_id`; rollback per agent; the gate runs every agent's held-out set (blocks harm to another agent) | Each agent improves on its own | P8 |
| B4 | **Knowledge per agent:** Analyst query patterns and schema notes; Tool Forge approved and rejected names; Miner gate outcomes | Each agent has its own knowledge | P9 |
| B5 | **Learned routing:** code counts (task pattern × agent/tool × success); the Coach only phrases a hint; the paired test decides | Routing is learned, not hardcoded | P10 |
| B6 | **Tool Forge agent:** the model names and describes; code keeps templating and checks; `suggest_name` is the fallback | Turns on the third agent | P11 |
| B7 | **Lesson Miner agent:** the miner as a teammate with read tools; the evidence gate stays in code | Turns on the fourth agent | design §4.2 |
| B8 | **`learning_event` events** for lesson, tool, patch and pack decisions | Learning timeline and ledger | §4.5 |
| B9 | **Benchmark harness:** arms S, M0, M1 frozen by hash; cases and bars written before any model call; then the run (~$30) | Proof for the multi-agent claim | P12, P15 |
| B10 | **Docker image and Hugging Face Space config**, demo world built in; the API can be checked through `/docs` before React exists | Hosting | V10 |

## 4. Tests (mock model, no credits)
- **API contract tests** for every endpoint, with FastAPI's TestClient.
- **SSE tests:** replay stream, live stream with a scripted run, reconnect with `after`, and the `end` event.
- **Visitor isolation:** two cookies never see each other's drafts or lessons.
- **Public host:** every 🔒 route is refused under `ANUBHAV_PUBLIC=1`, and the spend caps hold.
- **Every event checked against the schema.**
- **Old tests:** all 356 stay green, including the Streamlit app tests after B1.

## 5. Order, cost and new dependencies
1. **B1 + B2:** about half a day. B1 is the riskiest step, because Streamlit must keep working.
2. **Endpoints in the order of §2:** about a day, most of them thin.
3. **B8, then B3–B7:** about a day.
4. **B9 frozen files → the benchmark run (~$30, pre-registered) → B10.**

Steps 1–3 cost no credits. The video still needs Nov 3–4.

New dependencies: `fastapi` and `uvicorn` only. SSE uses Starlette's StreamingResponse.

## 6. Open decisions (owner)
1. **Learning admin on the public host:** keep Tuning, mining and practice refused for visitors (recommended, as now), or allow them with spend caps?
2. **Chat default:** team mode or the single Planner? Recommended: the single Planner until B9 shows team mode is safe, then team.
3. **Fallback if time runs short:** ship the backend with only the Planner and Analyst active, plus the per-agent version store (B3), and leave B6/B7 planned?
4. **Start:** B1 begins on the owner's go.
