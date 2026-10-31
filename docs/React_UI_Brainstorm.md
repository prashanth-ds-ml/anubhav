---
tags: [design, brainstorm, ui]
status: SUPERSEDED by [[Anubhav_MultiAgent_Design_v1]] (kept as the discussion history; its section 3 roster and Section 1 architecture are outdated)
date: 2026-10-31
---
# React UI upgrade: brainstorm record

Related: [[Home]], [[submission_checklist]], [[decisions]]. Deadline: Thu Nov 5, 7:30 AM IST (Nov 4, 9 PM ET).

## 1. Audit baseline (Oct 31)
- `uv sync` into project `.venv` (Python 3.12): OK. `pytest`: **336 passed**, 0 failed, 4m54s (README says 335). No model calls in tests.
- `ruff`: 58 findings, mostly style; 4x B023 (loop variable in closure) worth a look.
- No TODO/FIXME markers. The zip has no `.git`.
- Technically complete. Open items are submission tasks: demo video, README GIF, links, platform submit.
- UI weak spots: 11 pages / 4 nav groups (admin pages exposed to judges); `core.replayable()` calls `find_replay()` up to 14x per rerun and each call re-parses every trace file (`ui/core.py:229-246`); internal jargon (T01, Loop A, EXP-008, ACTIVE_ADVISORY); hard-coded colour `#0F7A74` and hard-coded result captions in `proof.py`; dense Workbench; English-only UI; light theme only.

## 2. Understanding summary (confirmed in dialogue)
- Build a **React (Vite + TypeScript) app + FastAPI** to replace the Streamlit demo, hosted as **one Docker Space on Hugging Face** (owner has Pro). Replay mode (no keys) and live mode (keys in Space secrets, existing spend caps).
- **Layout A "Mission Control", single screen:**
  - Top: closed-loop strip (Act -> Observe -> Learn -> Verify -> Approve -> Improve) + **Agent Roster** (acting agent highlighted; Validator and Evidence Gate tagged "code").
  - Centre: tabs Orders, Route plans and drafts, Fleet, Company; secondary tabs Learning, New tools, Proof.
  - Right panel (~35%): agent chat + live event stream + "Why this plan" card (which lessons drove each decision, tools used or created, results).
- Showcase items: (1) clearer tool-call visualisation than graphviz (timeline of cards, graph secondary); (2) visible wrong-tool retry, max 3 attempts ("attempt 2/3"); (3) explicit `tool_missing` alert -> Analyst handoff -> new-tool candidate; (4) clarity on how many agents exist, their tasks, when called, who is acting.
- Framing: **self-improving agentic system with governed autonomy**: Act -> Observe -> Learn -> Verify -> Approve -> Improve. "Acts" = drafts only, never dispatches. "Self-learns" = proposes lessons/tools/patches; code verifies; a person approves.
- Non-goals: rewriting planner, gate, broker or benchmark; new learning algorithms; Autonomy dial (future work, shown as a note only).

## 3. Agent roster (decision #4)
| Layer | Who | When | Task |
|---|---|---|---|
| Runtime (2) | Planner (Muse Spark Open, LangGraph) | every chat message | understands RT/TE/EN, calls tools, drafts; only user-facing agent |
| | Analyst (same model, sub-agent, fixed template) | spawned by Planner when no tool fits | gets a Planner-written task brief; read-only SQL only; cannot draft; returns findings + query |
| Offline (3) | Lesson Miner (Muse Spark 1.3) | on demand / nightly | proposes lessons from history |
| | Harness Coach (Muse Spark 1.3) | after failures / negative feedback | proposes small patches to tool hints and guidelines |
| | Judge (Muse Spark 1.3) | paired tests | scores old vs new |
| Code guards (not agents) | Validator, Evidence Gate, Reply Checker, Leak Check, Tool Forge | every draft/lesson/reply/pack/reused query | deterministic checks |
| Human | Reviewer | before anything goes active | approves lessons, patches, tools, packs |

"One agent creates others" is bounded: the Planner writes the Analyst's *brief*; the Analyst's tools, prompt template and limits are fixed in code. Not free-form agent creation (would void benchmark validity, adds cost, blurs the story).

## 4. Current-state facts the design depends on
- Only the Planner is a true runtime agent today; no sub-agent delegation exists (new capability).
- `graph.run()` returns the whole trace at the end; there is no streaming (new: LangGraph streaming + event mapper).
- In-run tool errors already feed back to the model (self-correction exists, but no explicit attempt counter). `run_query` fallback and reused-query -> new tool flow exist, but no explicit "tool not available" event.
- Hosted Streamlit demo is replay only, no keys.

## 5. Assumptions (proposed; owner has not corrected them)
1. Vite + React + TypeScript talking to a thin FastAPI wrapper.
2. Works without keys (replay of real saved runs streamed event by event); live optional.
3. English UI; Telugu input/replies unchanged.
4. Desktop-first, usable tablet layout.
5. Synthetic data, no login, per-visitor drafts as today.
6. Retry: keep in-run self-correction, make it an explicit visible loop (max 3 attempts per failed step).
7. Missing tool: emit `tool_missing` -> alert card -> Analyst handoff -> (if reused) Tool Forge candidate -> human approval.
8. Typed event protocol shared by replay and live. Saved traces converted offline; some moments (retry, missing-tool) may need new recordings (~$0.05 each) if no saved run shows them.

## 6. Design so far
### Section 1: Architecture (presented; awaiting "looks right")
```
HF Docker Space (port 7860)
 FastAPI
  /                   -> built React app (static)
  /api/dashboard/*    orders, fleet, drafts
  /api/learning/*     lessons, timeline
  /api/agents         roster + live status
  /api/chat/stream    SSE event stream (replay: saved runs -> events; live: LangGraph .stream() -> events)
 Existing Python: runtime, learning, harness
```
- One container, one origin (no CORS). Reuse broker/validator/gate/store/agent loop; add `api/` package + React app.
- Unavoidable refactor: `ui/core.py` uses `st.session_state` (session id, spend caps). Extract into a framework-free service module; spend caps (8/session, 60/day) carry over unchanged.
- New `events.py` maps graph node outputs to typed events: `agent_start`, `tool_call`, `tool_result`, `retry`, `tool_missing`, `handoff`, `lesson_used`, `validator_check`, `draft_created`.
- Per-visitor state via session cookie. Secrets in Space secrets; no keys = replay only.
- Risk: Space storage resets on restart unless persistent storage is attached; bake the demo world into the Docker image to avoid a ~1 min cold start.

### Still to present (in order)
2. Event protocol (schemas, replay conversion, which saved runs demo which moments)
3. Screens: dashboard tabs, chat panel, "Why this plan" card, Agent Roster, Learning, New tools, Proof
4. Error handling and edge cases (no keys, caps hit, stream drop, empty states)
5. Testing strategy (API contract tests, event-mapper tests, UI smoke/Playwright, accessibility)
6. Visual system (tokens, light/dark, typography, icons) and mockups

## 7. Decision log
| # | Decision | Alternatives considered | Why |
|---|---|---|---|
| 1 | Run tests in a project `.venv` | scratchpad venv; system Python 3.14; skip | owner's choice |
| 2 | React + FastAPI in one Hugging Face Docker Space, replay + live | static replay only; static now, backend later | owner has Pro; one container; live and replay |
| 3 | Honest roster + one real Analyst handoff | labels only; full supervisor | accurate to the benchmarked system; still shows delegation |
| 4 | Roster = 2 runtime + 3 offline agents + code guards + human | many/dynamic agents | safety, benchmark validity, clarity |
| 5 | Closed-loop framing; Autonomy dial = future work (note only) | dial as stretch; dial as core | keeps README claim "every lesson needs a person" true; protects deadline |
| 6 | Layout A "Mission Control" single screen | multi-page + drawer (B); guided demo (C) | whole story visible at once; best for the 3-min video; optional guided tour later |

## 8. Risks acknowledged
- 4 days to deadline; demo video and README still open.
- Refactoring `ui/core.py` away from Streamlit; HF Space cold start/storage; streaming through HF's proxy (SSE should work, verify early).
- Benchmark numbers apply to the current Planner, not the Analyst-handoff version; say so in the README.
- Replay may not contain retry / missing-tool moments; may need a few live recordings.

## 9. v3: orchestrated multi-agent redesign (Oct 31, supersedes the roster in section 3)
Owner's proposal: 3-4 fixed agents; **Planner = orchestrator** that delegates to fixed sub-agents, collects results and replies (Claude-workflow style); all confined to the logistics domain; each agent has its **own instructions, knowledge base and learning loop**; show self-learning visibly; benchmark the system; show decisions/learning/improvement live and as history.

Answers: Q1 4th agent = **Lesson Miner**. Q2 multi-agent becomes the **default; old single Planner kept as baseline + fallback**. Q3 timeline = **everything, no cuts** (built as deployable stages). Q4 budget = **about $30**.

### Roster v3
| Agent | Role | Tools (proposed) |
|---|---|---|
| Planner (orchestrator) | talks to the user, decomposes, delegates, collects, drafts; only agent that may create/cancel drafts | ~22 existing tools: orders_and_sites, fleet_and_drivers, planning, trips_and_documents, knowledge, system; calls learned tools; + delegate tools |
| Analyst | read-only data questions | describe_tables, run_query, + history_and_performance (trip_history, order_history, performance) |
| Tool Forge | turns reused queries into named, parameterized, tested tools; human approves | new write tool "propose_tool"; today done by code in learning/newtools.py |
| Lesson Miner | reads history, proposes lessons; Evidence Gate (code) verifies | new read tools over the digest; today an offline Muse call |
Shared machinery (not agents): Harness Coach + Judge (the improvement loop), Validator, Evidence Gate, Reply Checker, Leak Check. Human reviewer approves everything.

### Facts found in code (tool inventory)
- 27 registry tools in 9 categories (+2 analysis, + dynamic learned_tools). All currently belong to the Planner; tools are not scoped per agent (broker filters only by role) -> per-agent allow-lists are new work.
- Harness patches (`harness/store.py`) are one shared surface for all clients/roles -> must become per-agent surfaces.
- Miner and Tool Forge have no registry tools today.

### Per-agent learning (assumption: no fine-tuning)
Each agent: versioned instructions + own knowledge base + own trace signals/feedback + paired-test gate + approve/rollback. KBs: Planner = site/vehicle lessons + tool hints; Analyst = schema notes + good query patterns; Tool Forge = tool catalogue + naming/parameter patterns; Miner = accepted/rejected mining notes.

### Benchmark proposal (pre-register; report either way)
1. System A/B: orchestrated multi-agent vs single Planner on the same unseen world + held-out cases (correct, unsafe, tool calls, cost, latency). Orchestration may not win; say so.
2. Per agent on held-out sets: Planner = EXP-011 cases; Analyst = EXP-012 questions; Tool Forge = same answers + unseen inputs; Miner = precision/recall vs hidden rules (EXP-009b).
3. Learning curves: each agent's score at v0 -> v1 -> v2 on the same held-out set.
4. Rejected patches count as evidence the gate is honest.
Old EXP-011R numbers apply to the single Planner only; label them so.

### Showcase
Decision ledger (agent, decision, lessons cited, tools, result) live + history; per-agent cards with instruction diffs, KB size, version history, before/after scores; handoff timeline in the chat stream.

### Build stages (each deployable; Streamlit demo stays as fallback until React passes)
1. Orchestrator + 3 sub-agents, per-agent tool scopes, delegation events, per-agent instruction surfaces.
2. Benchmark harness + runs (budget ~$30).
3. Per-agent learning loops + history/ledger data.
4. FastAPI + React Mission Control with streaming, roster, ledger, learning curves.

### Decision log additions
| # | Decision | Alternatives | Why |
|---|---|---|---|
| 7 | 4th agent = Lesson Miner | Critic/Verifier; only 3 agents | exists already; core thesis; Validator already critiques in code |
| 8 | Multi-agent default, single Planner kept as baseline/fallback | toggle only; full replace | A/B evidence + safe fallback |
| 9 | Everything in scope, built in deployable stages | staged cut; parallel UI+agents | owner's choice; stages protect the deadline |
| 10 | Budget about $30 for new runs | $15; $60 | one system A/B + per-agent sets + recordings |

### Risks added
- Four sub-agent surfaces and per-agent loops multiply testing; the old 336 tests must keep passing.
- Multi-agent orchestration adds model calls (cost, latency); results may not beat the single Planner.
- With about $30, repeats (3x) of the system benchmark probably won't fit; say so in limitations.

## 9b. Owner correction (Oct 31): nothing hardcoded; open access, learned routing
Owner: orchestrator and sub-agents have access to all other agents and tools; these are not hardcoded; it learns and improves. This **supersedes** "per-agent tool allow-lists" and "fixed Analyst template" above.

- Agents are **data specs** in a registry (name, instructions, knowledge base, limits). Tools are in a registry (`discover_capabilities`, `inspect_contract` already exist). Adding an agent = adding a spec.
- **Every agent can discover and call every tool and every other agent.** Permissions are by **action class**, enforced by code regardless of caller: read = open; drafts always pass the Validator; appends logged; new tools, lessons, patches, packs always need a human.
- Every call records the calling agent (powers "who is acting" and the decision ledger).
- Delegation limits: **depth max 2, no self-calls, one shared budget** (turns, tool calls, dollars). Planner is the only voice to the user.
- **Routing is learned:** each agent stores routing hints (which agent/tool fits which task type) in its own knowledge base; learning curves show routing improving v0 -> v1 -> v2.
- Benchmark: open routing is less predictable, so the multi-agent system needs its own held-out set; old EXP-011R numbers apply only to the fixed-tool single Planner.

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 11 | Any agent can call any agent, with depth/budget limits; access by action class | hub-and-spoke; fully open | matches owner's "access to all"; limits prevent loops and cost spikes |

### Approach chosen (Oct 31)
**A: agent-as-tool in the existing loop.** Every agent runs the same `graph.build()` loop from its spec (base prompt + its instructions + its knowledge base + learned routing hints). Delegation = one new broker tool `delegate(agent, brief)`; the session tracks depth, shared budget and calling agent. Rejected: B (LangGraph supervisor/swarm: rewrite, framework owns calls, highest deadline risk; keep as a "considered" note), C (plan-then-execute workflow: less open than the principle). v1 has synchronous delegation only (no parallel sub-agent calls, YAGNI).

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 12 | Approach A, agent-as-tool in the existing loop | B LangGraph swarm; C plan-then-execute | smallest change; reuses broker guarantees, Validator and tested loop; clean seam for routing learning |

## 10. Open / still to confirm
- Understanding Lock v3 awaiting explicit "yes".
- Defaults I'm assuming unless corrected: same base model for all sub-agents; Tool Forge LLM only names/describes tools while code parameterizes and tests them; Streamlit kept until React is verified.
