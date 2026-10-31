# API contract v1 (FastAPI ↔ React)

Design: `docs/Anubhav_MultiAgent_Design_v1.md` §4.1 and §4.5 (D-044). Changes here need both the Python and the web tests to pass.

- **Origin:** one container (Hugging Face Docker Space, port 7860). The API is under `/api`, and the built React app is served from `/`.
- **Session:** a cookie `anubhav_sid`, set on the first call, gives each visitor their own drafts and lesson store. There is no login.
- **Modes:**
  - `replay`: the default. It needs no keys and streams saved runs.
  - `live`: needs the model keys in the Space's secrets, and the spend caps apply: 8 runs per session and 60 per day.
  - When a key is missing or a cap is hit, the API falls back to replay and says so with `mode: "replay"` plus a `reason`.
- **Errors:** `{"error": {"code": "...", "message": "..."}}` with HTTP 4xx/5xx. The codes are those of the broker (`NOT_FOUND`, `BAD_ARGS`, `PERMISSION_DENIED`, …) plus `CONFLICT`, `READ_ONLY_PUBLIC`, `CAP_REACHED`, `NO_KEY`, `NO_REPLAY`, `INTERNAL`.
- **Ids:** company ids are `T01`, `T02`, `T03` and `TNEW`. Agent ids are the ones in `configs/agents.yaml`.

## Status
Built and tested (`tests/api/test_api.py`); the running API documents itself at `/docs`. Run it: `uv run uvicorn anubhav.api.app:app --port 7860`.
🔒 = refused with `READ_ONLY_PUBLIC` on the public host (one shared harness, or paid).

## Session and meta
| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{ok}` |
| GET | `/api/session` | `{public, default_mode, default_team, models: {name: {available, reason}}, live_runs_left, caps}` |
| GET | `/api/companies` | `[{company, name, sites, vehicles, towns, plan_date}]` |
| GET | `/api/suggestions?company=&use_lessons=` | `[{label, request, has_replay}]` |
| POST | `/api/session/reset-drafts?company=` | Clears this visitor's drafts, holds and conversation |

## Dashboard
| Method | Path | Returns |
|---|---|---|
| GET | `/api/dashboard/orders?company=` | `{delivery_date, orders: [... , in_draft]}` |
| GET | `/api/dashboard/fleet?company=` | `{delivery_date, vehicles: [... , free, reason]}` |
| GET | `/api/dashboard/drafts?company=` | This visitor's drafts: `[{draft_id, status, vehicle_id, orders, load, warnings, stops, why: {run_id, lessons, lessons_in_prompt, agents, tools, checks}, source}]` |
| GET | `/api/dashboard/drafts?company=&run_id=` | The drafts a saved run made (a replay creates nothing) |
| POST | `/api/dashboard/drafts/{id}/cancel?company=` | Cancels a draft and releases its vehicle |
| POST | `/api/dashboard/drafts/{id}/decide?company=` | `{decision: approve \| reject, notes, revise: true, model}`. Approve re-checks the plan first; approved is not dispatched. Reject needs notes, frees the vehicle and, with `revise`, sends the notes back to the agent: `{draft_id, status, revise_run_id, reason?}` |
| GET | `/api/handoffs?company=` | Runs waiting for this person: `[{run_id, request, handoff: {rule: question \| tool_refused \| reply_refused, question, agent, drafts, tools_used}, saved_at}]` |
| POST | `/api/runs/{id}/resume` | `{reply, model}`: continues a run stopped for a person, at a limit or on an error, as a new linked run (`resumed_from`). Follow it on `/api/chat/stream` |
| GET | `/api/dashboard/company?company=` | `{facts, owner, owner_fields, agent_reads, version, versions, written_rules}` |
| PUT | `/api/dashboard/company/profile?company=` | `{owner: {...}}`: saves a new version |

## Chat (streamed)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/api/chat` | `{company, message, mode: "replay" \| "live", model: "spark" (default) \| "open", use_lessons: true, team: true}` | `{run_id, mode, reason?}` |
| GET | `/api/chat/stream` | `?run_id=&after=-1` or `Last-Event-ID` | Server-sent events |
| GET | `/api/runs/{run_id}` | | A whole saved run with teammate runs |
| POST | `/api/runs/{run_id}/feedback` | `{rating: 0 \| 1, category, note}` | `{feedback_id}` |

The stream:
- Each message is one event (`contracts/events.schema.json`): `event: <type>`, `id: <seq>`, `data: <event JSON>`. Quiet periods send `: keepalive`.
- It ends with `event: end` and `data: {run_id, stop, mode}`.
- To reconnect, send `after=<last seq>` or the `Last-Event-ID` header; only missed events come back.
- A live request that can't run (no key, cap reached) falls back to replay with a `reason`. With no matching saved run: `NO_REPLAY` with `suggestions`.
- Follow-ups use the server's own saved history; a client can't supply earlier turns.
- A visitor can read or stream only saved demo runs and their own live runs.

## Agents, lessons, tools
| Method | Path | Returns |
|---|---|---|
| GET | `/api/agents` | Roster: `[{agent, name, purpose, status, voice, model, handles}]` |
| GET | `/api/agents/{id}` | Adds instructions and limits |
| GET | `/api/learning/lessons?company=&state=` | Lessons with `what`, evidence, gate verdict, `events` |
| POST | `/api/learning/lessons/{id}/decide?company=` | `{decision: approve \| reject \| retire \| rollback, effect, verified, why}` |
| GET | `/api/learning/timeline?company=&agent=` | Every learning decision, newest first |
| POST 🔒 | `/api/learning/mine?company=&by=agent\|offline` | The Lesson Miner agent, or the offline miner |
| GET | `/api/tools?company=&status=` | Candidate, active, rejected and retired tools |
| GET | `/api/tools/candidates?company=` | Queries written, grouped: `requests, agents, params, reached_threshold, threshold, suggested_name` |
| POST | `/api/tools/candidates/{key}/check?company=` | `{name?, description?}`: runs the checks and records a candidate |
| POST | `/api/tools/{id}/decide?company=` | `{approve, note}`: only a person; failed checks can't be approved |
| POST | `/api/tools/{id}/retire?company=` | Retires a tool |

## Tuning (Loop A)
| Method | Path | Returns |
|---|---|---|
| GET | `/api/harness` | `{active, versions (with diff), feedback, categories}` |
| GET | `/api/harness/problems` | Problems found in recent runs |
| POST 🔒 | `/api/harness/propose?company=` | Muse proposes one patch |
| POST 🔒 | `/api/harness/{v}/probe?company=` | Paired test, old vs new |
| POST 🔒 | `/api/harness/{v}/decide` | `{approve, note}` |
| POST 🔒 | `/api/harness/rollback` | Back to the previous version |
| GET | `/api/practice` | Results per round, version and split |
| POST 🔒 | `/api/practice?company=&agent=` | A practice set, by the single Planner or one agent; an agent's score is kept |

## Sharing, review, proof, logs
| Method | Path | Returns |
|---|---|---|
| GET | `/api/packs?target=` | `{published, received}` |
| POST | `/api/packs/publish` | `{sources, target, accept_rules}`: includes each pack's `leaks` |
| POST | `/api/packs/revoke?target=` | Revokes everything received |
| POST | `/api/review/run?company=` | Nightly review report; free on the public host |
| GET | `/api/review/history?company=` | Past reports |
| GET | `/api/proof` | Result files, each with `measured_on` |
| GET | `/api/proof/curve` | EXP-014's stages and agent scores, or `{measured: false}` (it has not run) |
| GET | `/api/compare?company=&request=` | One request from saved runs: cold, with lessons, with learned tools |
| GET | `/api/ledger?company=&agent=&type=&limit=` | Hand-offs, drafts, checks, lessons used, missing tools |
| GET | `/api/logs/events?company=&stream_name=` | Everything done and learned, newest first |
| GET | `/api/logs/runs?company=&limit=` | Run list: agents, tool calls, cost, issues |
| GET | `/api/logs/runs/{id}` | One run as a timeline, teammates in place |
| GET | `/api/logs/tools?company=` | Tool tracking: `{usage: [{agent, tool, calls, failed, last_used}], missing}` |
| GET | `/api/logs/agents?company=` | Each agent's runs, calls, errors and own cost |
| GET | `/api/logs/routing?company=` | Who handled which kind of task, how it went |
| GET | `/api/logs/models?company=` | What each Meta model did |
| GET | `/api/report/weekly?company=` | `{markdown}` |

## Fixtures
`web/fixtures/*.jsonl` holds one event per line, valid against the schema. The UI is built on these with no backend. `scripts/make_fixtures.py` produces them by running the real agent loop, broker and validator, with a scripted mock model in place of Muse. They are labelled as such in each stream's `agent_start` payload.
