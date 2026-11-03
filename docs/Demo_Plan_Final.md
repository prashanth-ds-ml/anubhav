---
tags: [plan, demo, final]
status: FINAL (owner, 2026-11-03). The one demo plan. Anything that is not on this page waits until after submission, or runs in the background only if it costs the demo nothing.
date: 2026-11-03
---
# Final demo plan

**Deadline:** Wed Nov 4, 9:00 PM ET = **Thu Nov 5, 7:30 AM IST**. Target: submit Nov 4 evening IST; the night is buffer.

**The story in one line:** *Start with nothing. Ask a real question in Telugu: it gets it wrong, and every tool call shows why. It learns from the company's own records, code checks the evidence, a person approves, and the same question comes out right. Then the proof, on both models, failures included.*

## 1. Decisions (defaults set; the owner can change any of them)
| # | Decision | Default |
|---|---|---|
| D1 | What "fresh" resets | Lessons, learned tools and agent versions go back to nothing / version 1. What code counts from the records (the business profile) stays: it is not learned by an agent |
| D2 | Which miner runs live | The offline miner pipeline that produced the demo's lessons (EXP-008 method, Muse Spark 1.3), not the Lesson Miner agent (recall 20–30% in EXP-014) |
| D3 | Where the fresh story runs | **Video:** recorded live on the owner's machine with the Meta key. **Hosted app:** a "Start fresh" scenario, mining capped at once per visit; the recorded scenarios stay as the free path |
| D4 | Go / no-go | A ~$1 feasibility check first: fresh mining on T01, 3 times. **Go** if the gate rule (Lakshmi Agencies, 22 ft) passes the gate in at least 2 of 3. **No-go:** keep the recorded S1 and show its tool calls in full instead |
| D5 | Models | Live: Muse Spark 1.3 on the Meta API only. No Baseten |
| D6 | Scope freeze | No new features or bug fixes unless they block the demo |
| D7 | Phase A result (Nov 3) | **Go:** fresh mining on T01 found the 22 ft gate rule in 3 of 3 runs ($0.19, ≈ 50 s and ≈ 10 lessons a run; 2 habits rejected, Kazipet stored expired) |

## 2. The video (target 2:50)
| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:10 | The problem | First screen | "Your best dispatcher knows a 32-foot truck can't get into this godown. No system does." |
| 0:10–0:35 | **Fresh, and wrong** | "0 lessons · 0 tools · agents at version 1". The Telugu request, live. Every tool call opened: what it asked, what came back, the code checks. It drafts **32 ft** | "A new company, nothing learned. I ask in Telugu. It looks up the site, the order, the fleet. Every check passes, and it picks a 32-foot truck." |
| 0:35–1:05 | **It learns from the records** | "Learn from the records": proposals arriving; the gate's verdicts with reasons; the gate rule's evidence (3 long trucks turned back); a person approves | "Muse Spark 1.3 reads ninety days of trips and drivers' notes and proposes rules. Code checks every one against the evidence. A habit that only looks like a rule is rejected. I approve this one." |
| 1:05–1:20 | **Same question, right** | The same request, live; the lesson used; **22 ft**; both trucks on one scale | "Same model, same question. Now it picks a 22-foot truck, and says which rule it followed." |
| 1:20–1:35 | Roads change | S6 Kazipet: weekly delays, the Telugu notes, "expired on arrival" | "Route knowledge comes from drivers, and it ends when the road reopens." |
| 1:35–2:05 | The team | Runs: Planner hands off to Tool Forge; a real SQL mistake fixed by the agent; Tools: a repeated query approved, 5 calls become 1 (**recorded on Muse Spark Open**) | "Agents hand work to each other, read their own errors and fix them, and work they repeat becomes a tool, only after a person approves." |
| 2:05–2:35 | Proof, failures included | Proof → Check our claims: **measured on both models** (45→90%, 33→100%, 0 unsafe, 3 of 3); the scoreboard with its ✕ marks; Agents: the team stage by stage | "Every experiment was fixed in advance and committed before it ran. The results hold on both models. And what didn't work is here too." |
| 2:35–2:50 | Close | Repo + hosted link: "Try it: Start fresh" | "Same model. Verified experience. Safer plans. Built on Muse Spark Open, Muse Spark 1.3 and Muse Voice Transcribe." |

**Say:** learns from the company's own records; code and a person stay in control; measured on both models; failures shown.
**Never say:** that each agent improves, that the team beats one Planner, or that live Spark 1.3 builds tools.

## 3. Work, in order
| Phase | When (IST) | Work | Owner |
|---|---|---|---|
| A | Nov 3, now (~1 h) | Feasibility check (~$1, Meta): fresh mining on T01 ×3 → go / no-go (D4) | Claude |
| B | Nov 3 (~3–4 h, if go) | Build the fresh path: (1) "Start fresh" (empty workspace, D1); (2) "Learn from the records" with live progress and the gate's verdicts; (3) each run's tool calls opened, each result readable, during the fresh scenario; (4) "your lessons, mined just now; the benchmark used these" note; (5) once-per-visit cap on mining; tests | Claude |
| C | Nov 3 night / Nov 4 morning (~1.5 h) | Deploy the Space with the `meta_api` secret; incognito check (first screen, Start fresh, S1–S3, S6, Proof); one real live run and one voice clip (~$0.30) | Owner gives the Space name; Claude does the rest |
| D | Nov 4 (~3 h) | Restart the machine; rehearse once through `/?tour=` links; record the fresh opening live locally, plus the rest; English subtitles for Telugu | Owner records; Claude prepares the script and the takes list |
| E | Nov 4 evening | Submission checklist, dry run, submit | Owner, with Claude |

## 4. In the background, only if free (never blocks A–E)
- Push `de19f3c` (tool detection fixes; already committed).
- One line crediting Harness² (Google Research) in About and on Agents.
- The interview line on the first screen ("planning takes 1–1.5 h, about 10 re-plans a day").
- A dispatcher's review of the lessons (owner, review kit ready).
- The hand-written benchmark (owner writes 40 questions, ≈ 3.5 h; Claude builds scorers and runs it overnight, ≈ $23, capped $30): status and open decisions in [[benchmark_data_guide]] "Status and next steps (Nov 3)".
- An ≈ $1 scaling check (mining from 30, 60, 90 days of history), if the owner says yes.

## 5. Budget
Meta left ≈ $89; keep $50 for judges. This plan spends ≈ $1 (A) + ≈ $1–2 (B tests) + ≈ $0.30 (C) + ≈ $1–2 (D takes) ≈ **$5**.

## Paused here (Nov 3, evening) — resume point
- **Phase A:** done (go).
- **Phase B (fresh path):** built and working live end to end (start fresh → 32 ft → learn from the records: 9 hold, 2 rejected, 1 expired → approve the gate rule → 22 ft, no page errors; three live runs cost ≈ $0.60 in all). Code is **not committed yet**: `src/anubhav/service/fresh.py`, the `/api/fresh/*` routes, `web/src/components/LearnFromRecords.tsx`, scenario S0, plan-card fleet retry, SQLite-backup restore, tests (`tests/api/test_api.py`, `web/e2e/fresh.spec.ts`), `web/scripts/demo-fresh-run.mjs`, screenshots in `docs/demo_screens/`. Last targeted test run was stopped by the pause; rerun before committing: `uv run pytest -q tests/api tests/learning` and `npx playwright test e2e/fresh.spec.ts e2e/desk.spec.ts e2e/scenarios.spec.ts --workers=1`.
- **Queued next:** BM0 (benchmark reference answers through the sandbox), small app items (Harness² credit, interview line, public API lock-down), script sections 3–8 with the new screenshots, deploy (needs the Space name and HF login), scaling check, submission text, commits and push.
- **Owner decisions still open:** Space name; problem statement on the form; Baseten key on the Space; benchmark world (7919 or fresh).

