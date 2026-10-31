# API contract v1 (FastAPI ↔ React)

Design: `docs/Anubhav_MultiAgent_Design_v1.md` §4.1 and §4.5 (D-044). Changes here need both the Python and the web tests to pass.

- **Origin:** one container (Hugging Face Docker Space, port 7860). The API is under `/api`, and the built React app is served from `/`.
- **Session:** a cookie `anubhav_sid`, set on the first call, gives each visitor their own drafts and lesson store. There is no login.
- **Modes:**
  - `replay`: the default. It needs no keys and streams saved runs.
  - `live`: needs the model keys in the Space's secrets, and the spend caps apply: 8 runs per session and 60 per day.
  - When a key is missing or a cap is hit, the API falls back to replay and says so with `mode: "replay"` plus a `reason`.
- **Errors:** `{"error": {"code": "...", "message": "..."}}` with HTTP 4xx/5xx. The codes are those of the broker (`NOT_FOUND`, `BAD_ARGS`, `PERMISSION_DENIED`, …) plus `CAP_REACHED` and `NO_REPLAY`.
- **Ids:** company ids are `T01`, `T02`, `T03` and `TNEW`. Agent ids are the ones in `configs/agents.yaml`.

## Dashboard
| Method | Path | Returns |
|---|---|---|
| GET | `/api/companies` | `[{company, name, depot, towns, sites, vehicles}]` |
| GET | `/api/dashboard/orders?company=` | Open orders for tomorrow: `[{order_id, site_id, site, town, kg, m3, value, handling, in_draft}]` |
| GET | `/api/dashboard/drafts?company=` | Drafts with ordered stops: `[{draft_id, vehicle_id, orders, load: {kg, m3, fill_pct}, verdict, stops: <sequence_stops result>, why: {lessons, agents, tools}}]` |
| GET | `/api/dashboard/fleet?company=` | `[{vehicle_id, class, length_ft, payload_kg, volume_m3, owner, status, free_tomorrow, reason}]` |
| GET | `/api/dashboard/company?company=` | Business profile (`learning/profile.py`) and the written rules |

## Agents and learning
| Method | Path | Returns |
|---|---|---|
| GET | `/api/agents` | The roster: `[{agent, name, purpose, status, voice, version, knowledge_items}]` |
| GET | `/api/learning/lessons?company=&state=` | Lessons with their state, evidence, gate verdict and approver |
| GET | `/api/learning/timeline?company=` | `learning_event` events, newest first |
| GET | `/api/learning/agents/{agent}` | One agent's versions: instruction diffs, paired-test results, approved and rejected changes |
| GET | `/api/ledger?company=&agent=&type=` | Decision history: events of type `handoff`, `draft_created`, `validator_check`, `lesson_used` and `learning_event`, filterable |
| GET | `/api/proof` | Benchmark summaries (`artifacts/benchmark/*.json`), each labelled with the system version it measured |

## Chat (streamed)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/api/chat` | `{company, message, mode?: "replay" \| "live", use_lessons?: true, team?: true}` | `{run_id, mode, reason?}` |
| GET | `/api/chat/stream` | `?run_id=&after=-1` | Server-sent events, described below |

The stream:
- Each message is one event (`contracts/events.schema.json`): `event: <type>`, `id: <seq>`, `data: <event JSON>`.
- It ends with `event: end` and `data: {"run_id", "stop"}`.
- To reconnect, a client sends `after=<last seq>` (or the `Last-Event-ID` header) and receives only the events it missed.
- In replay mode, a request is matched to a saved run. If there is no match, the API returns `NO_REPLAY` and suggests requests that do have saved runs.

## Fixtures
`web/fixtures/*.jsonl` holds one event per line, valid against the schema. The UI is built on these with no backend. `scripts/make_fixtures.py` produces them by running the real agent loop, broker and validator, with a scripted mock model in place of Muse. They are labelled as such in each stream's `agent_start` payload.
