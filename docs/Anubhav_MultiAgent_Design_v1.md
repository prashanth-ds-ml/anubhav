---
tags: [design, multi-agent, ui, benchmark]
status: FINAL (all sections and decisions #1-16 confirmed by owner, Oct 31; delivery plan 4.9 confirmed)
date: 2026-10-31
supersedes: React_UI_Brainstorm (kept as history)
---
# Anubhav multi-agent system and React platform: design v1

History and discussion trail: [[React_UI_Brainstorm]]. Related: [[Home]], [[submission_checklist]], [[decisions]], [[risks]].
Deadline: Thu Nov 5, 7:30 AM IST (Nov 4, 9 PM ET). Target submit: Nov 4.

## 1. Understanding summary
- Build an **orchestrated multi-agent system** for the logistics domain: a **Planner** (orchestrator) delegates to fixed sub-agents **Analyst, Tool Forge, Lesson Miner**, collects results and gives the user one reply (Claude-workflow style).
- Agents are **not hardcoded**: they are specs in a registry; tools are in a registry. **Any agent can discover and call any tool and any other agent**, within limits. Routing is **learned**.
- **Each agent has its own instructions, knowledge base and learning loop** (propose patch -> paired test -> human approval -> rollback). No fine-tuning.
- Code stays authoritative: **Validator, Evidence Gate, Reply Checker, Leak Check** are not agents. Harness Coach + Judge are shared machinery for the loops. Humans approve everything that becomes active.
- Multi-agent becomes the **app default**; the **old single Planner stays as A/B baseline and fallback**.
- Show clearly, **live and historically**: which agent acted, what it decided, which lessons and tools it used, what it learned and how each agent improved.
- Frame the product as a **self-improving agentic system with governed autonomy**: Act -> Observe -> Learn -> Verify -> Approve -> Improve. "Acts" = drafts only, never dispatches.
- Benchmark the whole system and each agent; budget about **$30**.
- Hosting: **React + FastAPI in one Docker Space on Hugging Face**, replay (no keys) and live (keys in Space secrets, spend caps kept).
- Non-goals: Autonomy dial (future work, a note only), free-form agent creation, fine-tuning, changes to the code guards, parallel sub-agent calls in v1.

## 2. Assumptions
1. All agents use the same base model (Muse Spark Open) unless cost or quality says otherwise.
2. Tool Forge's LLM only names and describes tools; code parameterizes and tests them; a person approves.
3. The existing 336 tests keep passing throughout.
4. Vite + React + TypeScript; English UI; Telugu input and replies unchanged; desktop-first, usable tablet layout.
5. Synthetic data, no login, per-visitor drafts and lesson store.
6. Retry means up to 3 corrected attempts per failed step, each shown as an event.
7. Old EXP-011R numbers apply only to the fixed-tool single Planner and are labelled so.

## 3. Current state this design builds on (verified in code, Oct 31)
- `uv sync` + `pytest`: **336 passed**, 0 failed. Technically complete single-agent system; open work is submission tasks plus this redesign.
- 27 registry tools in 9 categories (+2 analysis, + dynamic learned tools), all belonging to the Planner today (`runtime/broker.py:864-948`); broker filters only by session role, not by agent.
- Only the Planner is a runtime agent; Miner, Harness Coach, Judge are offline Muse calls; Tool Forge is code in `learning/newtools.py`.
- `graph.run()` returns the whole trace at the end (no streaming); tool errors already feed back to the model; `run_query` fallback and reused-query -> new tool exist, with no explicit `tool_missing` event.
- Harness surfaces (`harness/store.py`) are shared by every client and role.

## 4. Design

### 4.1 Architecture and hosting
```
HF Docker Space (port 7860)
 FastAPI
  /                   built React app (static)
  /api/dashboard/*    orders, fleet, drafts, company
  /api/learning/*     lessons, timeline, agent versions
  /api/agents         roster + live status
  /api/ledger         decision history
  /api/chat/stream    SSE typed events (replay or live)
 Existing Python: runtime, learning, harness, agent loop
```
One container, one origin (no CORS). `ui/core.py` (Streamlit-bound: `st.session_state`, spend caps) is extracted into a framework-free service module; caps (8/session, 60/day) carry over. Per-visitor state via session cookie. Secrets in Space secrets; no keys = replay only. The demo world is baked into the image to avoid the ~1 min cold start. Risk: Space storage resets unless persistent storage is attached. Streamlit stays as fallback until React is verified.

### 4.2 Agent registry and `delegate` (Approach A)
- **Agent spec (data):** `agent_id`, one-line `purpose`, versioned `instructions`, own `knowledge`, own `limits`, `model`.
- **One loop, many agents:** `graph.run()` takes an agent spec; the system message = base prompt + instructions + knowledge + routing hints. All existing behaviour stays (limits, wrap-up, draft re-check, reply check).
- **`delegate(agent_id, brief)`:** broker tool visible to every agent. Checks target exists, depth < 2, no self-call, shared budget has room; runs the target's loop; returns a summary (reply, drafts, cost, stop reason); writes a `handoff` event; tags nested steps with `agent_id`.
- **Discovery:** `discover_capabilities` lists agents as well as tools. A new agent = a new spec, no code.
- **Who replies:** only the Planner's final message reaches the user.
- **Safety unchanged:** `delegate` does not bypass the broker. Access is by **action class**: read open; drafts always pass the Validator whoever calls; appends logged; new tools, lessons, patches and packs always need a person.
- **New work:** registry, `delegate`, depth/budget in `Session`, `agent_id` on every trace step, nested-trace handling in saved runs.

### 4.3 Per-agent learning
- **Signals per agent:** tool errors, wrong-tool calls, retries, `tool_missing`, delegation outcomes (needless or missing), cost and limit hits, tester feedback attributed to the answering agent.
- **Loop (extends `harness/loop.py`):** code collects problems for one agent -> Coach proposes one small patch to that agent's instructions or routing hints -> paired test old vs new on that agent's held-out set -> gate (no lost drafts, no new tool errors, cost within limit, real improvement) -> human approval -> version v(n+1) for that agent only; rollback per agent.
- **Knowledge bases:** Planner = site/vehicle lessons + tool hints; Analyst = schema notes + query patterns collected by code from successful queries; Tool Forge = tool catalogue + approved/rejected names and parameters; Miner = accepted/rejected mining notes with gate reasons.
- **Learned routing:** new surface type "routing hints" (e.g. weekday-count questions -> Analyst). Code computes evidence from traces (task pattern x agent/tool x success); the Coach only phrases it; the paired test decides.
- **`tool_missing`:** fires only after `discover_capabilities` returns no match; the UI shows an alert; the Analyst/`run_query` fallback runs; a reused query becomes a Tool Forge candidate for approval.
- **Honesty:** a patch with no gain is rejected and stays visible (as EXP-010).

### 4.4 Benchmark
Pre-register, freeze files by hash before any model call, fresh unseen world seed, report either way.
- **Arms:** S (single Planner, baseline), M0 (multi-agent at v0), M1/M2 (after approved per-agent versions). Same base model and cases.
- **Case sets:** Planner cases (EXP-011 builder, 38 in RT/TE/EN), data questions (EXP-012 style, 16), tool-reuse checks, mining precision/recall vs hidden rules (EXP-009b), plus a new **routing label** per case.
- **Train/test split:** learning failures come from a separate practice set; the evaluation set is frozen and never seen by a loop.
- **Metrics:** correct, unsafe drafts, tool calls, cost, latency, delegations, retries, routing accuracy. **Learning curve:** each agent at v0, v1, v2 on the same held-out set.
- **Proposed bars (freeze before running):** unsafe drafts 0 in every arm; M0 not worse than S by more than 5 points on correctness; routing accuracy +15 points from v0 to best version; cost per question <= 1.5x S.
- **Budget:** about $30 (assumes multi-agent runs cost 1.5-2x the earlier ~$0.06/run): about 114 planner runs, 48 data-question runs, about 60 learning/paired-test runs, about 10 recordings. One repeat, not three; state this limit in the README.
- **Caveats:** cases and hidden rules come from our own generator; small samples; multi-agent may not beat S and will be reported anyway. Development uses a fake model client (no cost).

### 4.5 Showcase (live and history)
- **One event store** feeds everything. Event: `run_id`, `agent_id`, `caller`, `ts`, payload. Types: `agent_start`, `tool_call`, `tool_result`, `retry`, `tool_missing`, `handoff`, `lesson_used`, `validator_check`, `draft_created`, `agent_done`, `learning_event`. Live stream and history read the same store; saved replay runs are converted offline.
- **Views:** (1) chat stream timeline of cards, indented by depth and tagged by agent (replaces graphviz; graph as a secondary toggle); (2) "Why this plan" card next to each draft (lessons with evidence, agents and tools, Validator verdict, outcome); (3) decision ledger (filterable history); (4) agent cards (version, instruction diff, knowledge size, v0/v1/v2 curve, rejected patches with reasons); learning timeline feed; Proof tab with arms side by side, per-agent curves and limitations.
- If an event is not recorded it cannot be shown, so `agent_id` tagging comes first.

### 4.6 Error handling and edge cases
- **Delegation:** limit violations return `DELEGATION_LIMIT`; unknown agent returns `NOT_FOUND` with valid ids; a budget hit uses the existing wrap-up at top level.
- **Sub-agent failure:** returns `stop: "error"` with partial results; the Planner always owes an answer and says what it could not check; the reply checker treats delegated results as run evidence.
- **Retry:** at most 3 attempts with the error fed back; each is an event; a third failure is reported and the agent delegates or tells the user.
- **Stream/hosting:** reconnect fetches missed events by `run_id`; no keys or cap hit falls back to replay with a banner; replay cannot answer unsaved typed requests (UI says so); demo world baked into the image.
- **Learning:** no-gain patches rejected and kept; a patch that harms another agent's held-out score is blocked (gate runs all agents' sets); rollback is per agent. Each visitor has their own session store.

### 4.7 Testing strategy
- **Unit (fake client, no cost):** registry and discovery; `delegate` (depth, self-call, budget, caller/target recording, partial results); access by action class; `agent_id` tagging and parent links; 3-attempt retry; `tool_missing`; per-agent surfaces and blocked cross-harm patches; event store round-trip and replay conversion.
- **Regression:** the single-Planner path and replay of saved runs keep working (protects arm S).
- **API:** contract tests for dashboard, learning, agents, ledger; SSE with scripted run, reconnect, missed events.
- **UI (Playwright, replay mode, no keys):** dashboard loads; replay shows handoff and `tool_missing` cards; "Why this plan" shows lessons and tools; ledger filters; keyboard navigation and focus; contrast; no horizontal scroll at 1024 and 1440 px.
- **Benchmark harness:** case builder, scoring and frozen-hash check tested with fake outputs; a run refuses to start if a frozen file's hash changed.
- **Live checks last:** small smoke run per agent, then the benchmark, then recordings, each within the $30 budget (check the spend-cap file first).
- **Definition of done per stage:** old and new tests pass; the stage runs end to end in replay; the hosted Space is checked in an incognito window.

### 4.8 Visual system (proposal; mockups to be approved before building)
- Clean operations dashboard, light default + dark; accent Anubhav teal `#0F7A74`. All colours, spacing, radii and type sizes are CSS variables (charts read the same tokens).
- **Agent identity (colour + icon + label, never colour alone):** Planner teal/compass; Analyst blue/magnifier; Tool Forge amber/wrench; Lesson Miner violet/book; code guards neutral grey/shield labelled "code".
- **Status:** green validated/approved; amber warning/retry; red error, `tool_missing`, rejection; each with icon and text.
- **Type:** Inter (UI), JetBrains Mono (ids, SQL, logs, diffs), **Noto Sans Telugu** (replies in Telugu script); body >= 16px, line height 1.5-1.6. Icons: Lucide SVG, no emoji icons.
- **Layout:** top strip (loop + roster), centre tabs (Orders, Route plans/drafts, Fleet, Company; secondary Learning, New tools, Proof), right chat panel about 35% (resizable, collapsible); 12-column grid, consistent max widths; checked at 1024 and 1440 px.
- **Motion:** 150-250 ms, opacity/transform only, pulse on acting agent, respects `prefers-reduced-motion`. **Accessibility:** contrast >= 4.5:1, visible focus, `aria-live` for the log, table alternative for every chart. Skeleton loading; actionable empty states.

### 4.9 Delivery plan and fallback rules (CONFIRMED by owner, Oct 31; updated for decisions #13, #14, #16)
| When | Work | Done when |
|---|---|---|
| Oct 31 - Nov 1 | Registry, `delegate`, `agent_id` tagging, event store, retry loop, `tool_missing`; fake-client tests | Old + new tests pass; scripted Planner -> Analyst handoff |
| Nov 1 - 2 | Per-agent surfaces and loops, routing hints, benchmark harness, frozen case files and bars; in parallel FastAPI + React on replay fixtures | Files hashed; dashboard and stream render replayed events |
| Nov 2 - 3 | Practice runs, pre-registered benchmark (<= $30), deploy to HF Space | Numbers recorded; Space opens in incognito |
| Nov 3 | Dry run, fixes, README results and limitations | Full run-through, no dead ends |
| Nov 4 | Owner's demo video, README GIF and links, submission | Submitted before deadline |

Fallbacks: any unsafe draft by the multi-agent system on the practice set by end of Nov 2 -> single Planner stays default, sub-agents ship as an optional mode; React unstable by Nov 3 -> Streamlit stays the hosted link, React shown as a preview Space; benchmark incomplete within budget -> report partial results and limits, never as the full result; every stage ends deployable. Owner provides: review of the real React shell on replay fixtures (first look about Nov 2, replaces separate mockups, decision #16), keys in Space secrets, the demo video.

## 5. Decision log
| # | Decision | Alternatives considered | Why |
|---|---|---|---|
| 1 | Run tests in a project `.venv` | scratchpad venv; system Python 3.14; skip | owner's choice |
| 2 | React + FastAPI in one Hugging Face Docker Space, replay + live | static replay only; static now, backend later | owner has Pro; one container; live and replay |
| 3 | Honest roster, no overclaiming | labels only; full supervisor | accurate to the benchmarked system |
| 4 | Fixed named roster (specs in a registry), not dynamic agent creation | many/dynamic agents | safety, benchmark validity, clarity |
| 5 | Closed-loop framing; Autonomy dial = future work (note only) | dial as stretch or core | keeps README claim "every lesson needs a person" true |
| 6 | Layout A "Mission Control" single screen | multi-page + drawer (B); guided demo (C) | whole story visible at once; best for the video |
| 7 | 4th agent = Lesson Miner | Critic/Verifier; only 3 agents | exists already; core thesis; Validator already critiques in code |
| 8 | Multi-agent default; single Planner kept as baseline/fallback | toggle only; full replace | A/B evidence + safe fallback |
| 9 | Everything in scope, built in deployable stages | staged cut; parallel UI+agents | owner's choice; stages protect the deadline |
| 10 | Budget about $30 for new runs | $15; $60 | one system A/B + per-agent sets + recordings |
| 11 | Any agent can call any agent, depth <= 2, no self-calls, shared budget; access by action class | hub-and-spoke; fully open | matches owner's "access to all"; limits prevent loops and cost spikes |
| 12 | Approach A: agent-as-tool in the existing loop (`delegate`) | B LangGraph swarm; C plan-then-execute | smallest change; reuses broker guarantees, Validator and tested loop |

| 13 | "Route plan" = a draft shown as ordered stops with estimated km/time, from one new deterministic tool `sequence_stops` (nearest-neighbour from the depot over town coordinates; labelled "estimated, not optimized"; no LLM; not in the benchmark) | display only; real multi-stop optimization with time windows | route data today is a depot-to-site haversine estimate (`get_route_info`), no sequencing; this adds a real route view with small, testable scope |

| 14 | Tool Forge becomes an LLM agent for **naming, description and example only**; code still parameterizes, runs the equivalence + held-out checks, and a person approves; the existing code name (`suggest_name`) is the fallback; its loop learns from approved/rejected names and is measured by learned-tool use rate on held-out questions | keep as code and label it a guard (3 learning agents); LLM also writes the SQL template | EXP-012 vs 012b showed naming drives reuse (0/16 -> 14/16); keeps the tested safety path in code |
| 15 | Dashboard content: Orders, Route plans and drafts (ordered stops, est. km/time, fill %, Validator verdict, "Why this plan"), Fleet, Company (profile + written rules); "learned here" badges; ledger click-through; no real map tiles (simple stop diagram); no editing or dispatching | add a real map; editing views | uses data that exists; map tiles need services and synthetic coordinates add little |

| 16 | No separate mockups: build the real React shell on replay fixtures and review it live in the browser | one HTML mockup; Figma mockups | saves a step on a 4-day clock; accepts the cost of visual rework |

## 6. Risks acknowledged
- Four days to deadline; demo video and README still open; "everything, no cuts" mitigated by deployable stages and the fallback rules in 4.9.
- Four agents with open routing multiply testing; the 336 existing tests must stay green.
- Multi-agent adds model calls (cost, latency) and may not beat the single Planner; results are reported either way.
- $30 does not allow 3 repeats of the system benchmark; state it in limitations.
- Extracting `ui/core.py` from Streamlit; HF Space cold start and storage; SSE through HF's proxy (verify early).
- Benchmark numbers apply to the version measured; old EXP-011R numbers apply to the single Planner only.
- Replay may lack retry and `tool_missing` moments; a few live recordings may be needed.

## 7. Open items
- None blocking. Section 4.9 is confirmed; mockups are no longer a gate (decision #16). Next step: implementation plan, once the owner says go.
- New scope added by decisions #13-#14: `sequence_stops` tool with tests; Tool Forge LLM naming loop with a held-out use-rate metric.
- Ready for implementation planning once 4.9 is confirmed.
