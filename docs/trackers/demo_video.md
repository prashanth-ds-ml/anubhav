---
tags: [tracker, demo]
---
# Demo video (≤ 3:00) and hosted demo

The video is the primary artifact. Final-round judges also try the hosted demo, following the same flow, so every beat below can be reproduced there with no keys. Script rewritten 2026-10-30 around D-039 (one company learning three ways from its own runs) and D-043. Recording: Nov 3 (owner).

**One sentence:** *Same model. It learns what your business never wrote down, how to use its tools, and new tools of its own, and you can see and approve every step.*

## Storyboard (target 2:50)
Every shot is a real run. Replays are labelled "replay" on screen (the app does it). Numbers come from the files named.

| Time | Beat | On screen (page → action) | Narration (draft) | Source |
|---|---|---|---|---|
| 0:00–0:15 | The problem | A 32 ft truck and the Jangaon godown gate; one line: 75% of India's truck operators run fewer than five trucks | "Your best dispatcher knows a 32-foot truck can't get into this godown. No system does. 75% of India's truck operators run fewer than five trucks: their rules live in notes and in people's heads." | Redseer, Dec 2024 (README) |
| 0:15–0:35 | Session 0: it learns the business | **Business profile**: facts counted from the records (45 sites, 18 vehicles, ~10 orders a day…) | "Anubhav runs on Meta's open-weights Muse Spark Open. First it learns what the business is, from its own records." | Business profile page |
| 0:35–1:00 | Session 1, failure 1: a fact nobody wrote | **Workbench**, lessons off, voice in Roman Telugu: "Repu Jangaon Lakshmi Agencies load ki bandi pettu" → it drafts the 32 ft truck | "I ask in Telugu, by voice. It plans with its tools, and gets it wrong: the system says the truck fits." | replay (T01, cold); Muse Voice Transcribe live if keys |
| 1:00–1:25 | It learns from the records | **What it learned**: the 22 ft lesson, its evidence (3 trucks turned back), the gate's verdict; approve | "Muse Spark 1.3 reads 90 days of records and proposes a rule. Code checks the evidence. I approve it. A habit that only looks like a rule is rejected." | EXP-008 lessons |
| 1:25–1:40 | Fixed | Workbench, lessons on: same request → the 22 ft truck, the lesson cited | "Same request, same model: now it's safe." | replay (T01, lessons) |
| 1:40–2:15 | Failure 2 → a tool it made itself | Workbench "New tool": "Hanamkonda lo ae weekday lo ekkuva deliveries?" → 5 calls, writes SQL, hedges. **New tools**: the query it reused for other towns, checks pass (same answers, 5 held-out towns) → Approve. Ask again → **1 call, Saturday** | "No tool answers this, so it writes a read-only query. It has needed that query before, so code checks it on towns it never saw, and I approve it as a tool. Next time: one call, a quarter of the cost, and the right answer." | replays: `demo:new-tool-before` ($0.066, 5 calls) and `live:c5-learned-tool` ($0.016, 1 call) |
| 2:15–2:30 | The nightly review | **Logs**: "Run the nightly review" → tool use → Tuning, reused queries → New tools, stated facts → lesson proposals; then one run as Plan / Act / Observe / Code check | "Every night it reads its own runs and sends each problem to the right fix. Nothing changes without a person. And every step is in the logs." | Logs page |
| 2:30–2:45 | Proof | **Proof & audit**: EXP-011 chart; one line for EXP-011R and EXP-012 | "On a world it had never seen: lessons beat searching raw notes, 35 to 90 percent; a brand-new company, 33 to 100 with a shared pack, and zero private details leaked." (+ EXP-011R / EXP-012 lines once known) | `artifacts/benchmark/exp011_*.json`, EXP-011R, EXP-012 |
| 2:45–2:50 | Close | Repo + hosted link; "Same model. Verified experience. Safer plans." | "Built during the hackathon on Muse Spark Open, Muse Spark 1.3 and Muse Voice Transcribe." | README |

**Also say once, honestly:** the data is synthetic (allowed; it's how we can score against hidden truth), and the app is newer than the EXP-011 measurement (EXP-011R covers that).

## Shot list and assets
- [ ] Voice request recorded in Roman Telugu (owner), with English subtitles
- [x] Golden-path replays (T01 cold and with lessons) in `demo/replay_runs.jsonl`
- [x] A genuine failure: the cold 32 ft draft; the 5-call hedged answer before the tool existed (real, not staged)
- [x] New-tool before/after replays in the hosted bundle (app test covers the flow)
- [x] Logs page with "Meta models at work", run timeline, nightly review
- [ ] EXP-011R and EXP-012 lines for the proof beat (running)
- [x] Architecture diagram (README mermaid)
- [ ] English subtitles for every Telugu line
- [ ] Every replayed segment labelled "replay" (the app shows it on the run header)

## Recording checklist
- [ ] Screen at 1080p, browser zoom fixed, notifications off, incognito window
- [ ] Hosted demo: open it once a few minutes before (first start builds the world, up to a minute)
- [ ] Sidebar: company T01; "Reset today's drafts" before each take
- [ ] Spoken script timed under 2:55
- [ ] Uploaded; link works in incognito

## Hosted demo
- **URL:** https://anubhav-metahackathon.streamlit.app/ (deployed 2026-10-30, no keys, `ANUBHAV_PUBLIC=1`)
- **Modes:** replay (default, free) · live (only if keys are added; 8 runs per session, 60 per day)
- [x] Spend cap enforced · [x] Per-visitor state · [x] Works in incognito (owner checked 2026-10-30)
