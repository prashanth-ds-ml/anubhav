---
tags: [plan, demo, ui]
status: PROPOSED (Oct 31). The UI work starts next; decisions in the last section are the owner's.
date: 2026-10-31
---
# Demo and UI plan

Related: [[backend_plan]], [[demo_video]], [[Anubhav_MultiAgent_Design_v1]], [[decisions]] (D-046). API: `contracts/api.md`, and `/docs` on the running server.

**Ground rule (owner, Oct 31):** build the backend and plan the UI. No experiments and no credits spent. Live use goes on the Meta API, not Baseten. So everything below uses saved runs and results we already have.

## What we can honestly show today
| Claim | Evidence | Show as |
|---|---|---|
| It learns unwritten rules | EXP-011R: 48% → 90%, 3 of 3 repeats (single Planner) | Headline number |
| A new company benefits on day 1 | EXP-011R: 33% → 100%, 0 leaks (single Planner) | Headline number |
| Same request, safer plan | Saved team runs: 32 ft (no lessons) → 22 ft, citing the rule | Before/after, `/api/compare` |
| It makes tools from repeated work | Saved runs: 5 calls, $0.066 → 1 call, $0.016 (one example, threshold 2 then) | Before/after |
| A team works safely | EXP-013: 47/54 vs 48/54, 0 unsafe, 1.36× cost | Proof page; say it isn't more accurate |
| Nothing goes live without a check and a person | Gate, paired test, approvals; code and tests | Approval screens, timeline |
| It doesn't learn just anything | h-001 rejected; gate refuses habits and look-alikes | One rejection on screen |

**Don't claim:**
- that the team gives better answers than one planner;
- that each agent improves on correct answers, or that the whole team improves stage by stage (EXP-014 was not run);
- that the Lesson Miner agent works: its one real run spent its budget on queries and proposed nothing. The measured mining is the offline miner's (EXP-009b);
- that any of the measured numbers apply to Muse Spark 1.3 as the agent. They were all measured on Muse Spark Open.

## Demo story (3 minutes, all saved runs)
| Time | Beat | Screen | Data |
|---|---|---|---|
| 0:00 | The problem: rules live in people's heads | Title, one statistic | README |
| 0:15 | The team and how it's governed: Act → Observe → Learn → Verify → Approve → Improve | Top strip | `/api/agents` |
| 0:30 | Failure: Telugu request, 32 ft truck drafted | Chat + event stream | Replay `demo:team:cold` |
| 0:55 | Learning: the lesson, its evidence, the gate, approval | Learning tab | `/api/learning/lessons`, `/decide` |
| 1:15 | Fixed: same request, 22 ft, "why this plan" | Chat + draft card | Replay `demo:team:lessons`, `/api/compare` |
| 1:35 | No tool fits: Planner → Tool Forge → query | Stream, hand-off cards | Replay `demo:team:new-tool` |
| 1:55 | Reused query becomes a tool: checks, a person approves, 5 calls → 1 | New tools tab | `/api/tools/candidates`, `/check`, `/decide` |
| 2:20 | Every decision is logged, rejections included | Timeline, tool tracking | `/api/learning/timeline`, `/api/logs/tools` |
| 2:35 | Proof: 48 → 90, 33 → 100, team vs one planner | Proof tab | `/api/proof` |
| 2:50 | Close | Repo and link | |

Replays are labelled "replay" on screen. Voice and video remain the owner's.

## UI plan
**Layout (design decision #6):** one screen. Top strip: the loop and the agent roster. Centre: tabs. Right, about 35%: chat and event stream.

| Area | Shows | Endpoints |
|---|---|---|
| Top strip | Loop, agents, who is acting now | `/api/agents`, stream |
| Chat and stream | Request, cards by event type, indented by depth, reply | `/api/suggestions`, `/api/chat`, `/api/chat/stream` |
| Orders | Tomorrow's orders, in a draft or not | `/api/dashboard/orders` |
| Plans | Drafts, ordered stops (labelled estimated), verdict, why this plan; approve, or reject with notes | `/api/dashboard/drafts`, `/decide` |
| Waiting for you | Runs stopped for a person: the question, what was tried, a reply box | `/api/handoffs`, `/api/runs/{id}/resume` |
| Model switch | Replay, Muse Spark 1.3 (default), Muse Spark Open; each live result labelled with its model | `/api/session`, `model` on `/api/chat` |
| Fleet | Vehicles, free or why not | `/api/dashboard/fleet` |
| Company | Profile, written rules | `/api/dashboard/company` |
| Learning | Lessons, approve or reject, timeline | `/api/learning/*` |
| New tools | Reused queries, checks, approve, tool tracking, missing tools | `/api/tools/*`, `/api/logs/tools` |
| Agents | One agent: instructions, versions, tests, rejected changes, totals | `/api/agents/{id}` |
| Before/after | One request, side by side | `/api/compare` |
| Proof | Results, each with what it measured; limitations | `/api/proof` |
| Logs | Runs, one run's timeline, ledger | `/api/logs/*`, `/api/ledger` |

**Stream cards:** `agent_start`, `tool_call` + `tool_result` (one card), `retry` (attempt n of 3), `tool_missing` (alert), `handoff` (with the brief), `lesson_used`, `validator_check` (including refused replies), `needs_person` (alert), `draft_created`, `learning_event`, `agent_done`. Build on `web/fixtures/*.jsonl` first.

**Host:** with no keys it is replay only and costs $0, and judges can't try either model live. Saved replays are all on Muse Spark Open except any recorded later. To let judges switch models live, the host needs both keys, and the caps (8 runs a session, 60 a day, shared) are what limit spend. The 🔒 actions appear disabled with the reason.

**Empty per-agent curves:** `scores` is empty until something measures them. Show "not measured yet", never a placeholder chart.

**Tests:** Playwright on replay, no keys: dashboard loads, hand-off and missing-tool cards show, draft card has why this plan, no dead ends, keyboard focus, 1024 and 1440 px.

## Decisions for the owner
1. **React + FastAPI, or Streamlit on the same service layer?** React matches the design and looks better; Streamlit is already hosted and is the safer path with the video still to record. Recommended: start React on the fixtures, and keep Streamlit as the hosted link until React passes in an incognito window.
2. **Host:** a Hugging Face Docker Space ([[deploy]]), or keep only Streamlit.
Credits: see D-048. Baseten is only for judges and the demo; our own runs use Meta, keeping $50.

3. **Keys on the host: yes (owner, Nov 1); the owner adds them in the host's secrets.** Muse Spark Open is capped at 30 live runs a day. Worst case is 60 live runs a day; at the $0.40 a request ceiling that is at most $24 a day, typically far less. Results differ by model, and all measured numbers are on Muse Spark Open.
