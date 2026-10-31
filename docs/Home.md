---
tags: [home, index]
---
# Anubhav: Home

**Meta Global AI Developer Hackathon** · Indie track · Push the Frontier

> An agent that learns a business's unwritten rules from its own records, checks the evidence, asks a person to approve risky lessons, and shares safe regional knowledge with the next customer. Telugu, English and Roman Telugu, on Meta Muse.
**Repo:** https://github.com/prashanth-ds-ml/anubhav · **Local:** `C:\Users\prash\projects\meta_hackathon`
**Deadline:** Wed Nov 4, 9:00 PM ET = **Thu Nov 5, 7:30 AM IST** (target: submit Nov 4 IST)

## Plan
- [[Anubhav_MultiAgent_Design_v1]]: **Oct 31 design (from another assistant's session, merged Oct 31):** orchestrated multi-agent system (Planner, Analyst, Tool Forge, Lesson Miner) with per-agent learning, and a React + FastAPI app on a Hugging Face Space. Decisions #1–16, delivery plan §4.9 (D-044). In progress: contract in `contracts/`, Python Sprint 1 done Oct 31; backend next ([[backend_plan]]); status in [[todo]]
- [[backend_plan]]: **resume here.** FastAPI endpoints (~45) and the remaining backend work B1–B10, with 4 open decisions (§6)
- [[React_UI_Brainstorm]]: the discussion that led to it (superseded, kept as history)
- `Implementation_Plan_Sprints.md`: sprint plan for the design; local only, not in git (it names people)
- [[implementation_plan]]: plan from Oct 30. Audit of the to-do list, demo story, workstreams A–G to submission, cut order
- [[build_plan]]: layers, dates, done-criteria, cut order (Oct 29 plan)
- [[PRD_v3.1]]: product requirements (source of truth), scaled per D-027
- [[Data_Benchmark_Blueprint_v1.0]]: data generator, 100-case benchmark, review procedure
- [[Data_Spec_v1]]: the demo world: references, scale, companies, vehicles, schema, **hidden rules (H-01…H-32)**, notes, generator steps
- [[Anubhav_overview]]: the idea, an 18-step walkthrough, experiment findings, hackathon fit
- `diagrams/anubhav_flow.excalidraw`: flow diagram (open at excalidraw.com)
- `archive/`: superseded docs (PRD v1 and v1.1, old day plan); prior experiment files are in the repo's `archive/prototype_experiments/`

## Trackers
| Tracker | Use it for |
|---|---|
| [[todo]] | Open fixes and next steps (audit, workshop review, demo plan; Oct 30) |
| [[progress]] | Layer status, FR status, release gates |
| [[decisions]] | Every decision, with its reason (ADR-style) |
| [[errors_and_fixes]] | Every bug or failure: symptom, cause, fix, prevention |
| [[run_logs]] | Every real model run: run_id, config, outcome, cost |
| [[tool_calling]] | Tool-selection quality: expected vs. actual tool, arguments, language |
| [[smoke_tests]] | Day-1 Muse capability tests and model facts (T1–T8) |
| [[experiments]] | Pre-registered experiments (EXP-001…) and benchmark arms A–E |
| [[data_and_benchmark]] | Generator runs, hidden rules, validation, human review, 100-case casebook |
| [[lessons]] | Loop B: lessons learned, rejected, shared |
| [[harness_versions]] | Loop A: tool-use patches: proposal → probe → decision → version |
| [[cost_ledger]] | Spend against the $150 Meta credit |
| [[risks]] | Live risk register |
| [[questions]] | Open questions, plus questions for Discord office hours |
| [[rubric_scorecard]] | Self-score against the judging rubric |
| [[demo_video]] | Storyboard, shot list, script, recording notes |
| [[submission_checklist]] | Everything needed for a valid submission |
| [[build_in_public]] | X posts, for the Most Viral and Community Vote prizes |
| [[ideas_parking_lot]] | Good ideas we are *not* doing now |

## Notes
- `daily/`: one note per day (use the Daily notes button; it applies the `templates/daily` template)
- `sessions/`: notes from workshops and office hours
- `templates/`: daily, decision, error, experiment, session, run

## Session routine
**Start:** read [[progress]] and [[build_plan]] → pick the next unchecked task → check [[risks]].
**During:** every bug → [[errors_and_fixes]] · every decision → [[decisions]] · every paid run → [[cost_ledger]] + [[run_logs]].
**End:** daily note → [[progress]] → [[risks]] → commit and push.

## Rules
1. Commit daily. Never commit `.env`, keys, `Hackathon_info/`, or real data.
2. **Ground rule:** every commit and push is by `prashanth-ds-ml <prashanth01071995@gmail.com>` only. No co-author trailers, no Claude attribution, no other account (D-028).
3. Never fabricate results, uplift or testimonials. Label any replay as a replay.
4. All companies, people, operating rules and data are fictional.
5. The model proposes, code enforces, people approve. No safety check is done by the LLM.
6. Pre-register every paid experiment (hypothesis, frozen files + hashes, decision rule) before the first call.
