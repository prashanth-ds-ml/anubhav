---
tags: [tracker, demo]
---
# Demo video (≤ 3:00) and hosted demo

The video is the primary artifact. Final-round judges also try the hosted demo, following the same flow, so every beat below can be reproduced there with no keys. Script rewritten 2026-10-30 around D-039 (one company learning three ways from its own runs) and D-043. Recording: Nov 3 (owner).

**One sentence:** *Same model. It learns what your business never wrote down, how to use its tools, and new tools of its own, and you can see and approve every step.*

**Recording path (rewritten Nov 2 for the build-sprint screens, D-052):** record in the React app, opening each scenario with `/?tour=S1`, `/?tour=S2`, `/?tour=S6`, then the Proof tab and about 15 s of S4 live. Shots to hold on: the truck drawn past the gate line, S1's finish with both trucks on one scale, the Runs swimlane with the mistake and its fix, the Kazipet weekly bars, and the Proof scoreboard with its ✕ marks.

## Storyboard (target 2:50)
Every shot is a real run or a committed file. Recorded runs say "Recorded" on screen (the app does it). Numbers come from the files named.

| Time | Beat | On screen (tab → action) | Narration (draft) | Source |
|---|---|---|---|---|
| 0:00–0:15 | The problem | **Dispatch Desk**, first screen: the problem card, the impact line, "Built on Meta Muse" | "Your best dispatcher knows a 32-foot truck can't get into this godown. No system does. 75% of India's truck operators run fewer than five trucks: their rules live in notes and in people's heads." | Redseer, Dec 2024 (README) |
| 0:15–0:40 | It gets it wrong | `/?tour=S1`, step 1: the Roman Telugu request → the plan card: 32 ft drawn past the 22 ft gate line, "The code checks passed. Only the learned rule says no." Point at the language chips | "I ask in Telugu. It plans with its tools on Muse Spark Open, the open-weights model, and every code check passes. But this truck won't fit the gate, and nothing in the data says so." | replay (T01, lessons off) |
| 0:40–1:05 | It learns from the records | **Learning**, the gate lesson: every trip to the site by truck length, 3 turned back, "limit it learned: 22 ft"; the life of the lesson; Undo and approve | "Muse Spark 1.3 read the company's records and proposed a rule. Code checked the evidence: three long trucks turned back. A person approves it, and can undo it." | `/api/learning/lessons/L-T01-002/evidence`, EXP-008 lessons |
| 1:05–1:20 | Fixed | S1 step 4 → the finish: both trucks on one scale, "Same model, same request…"; Approve ✓ and Improve ✓ light up | "Same request, same model. The only difference is one lesson it learned and a person approved." | replay (T01, lessons on) |
| 1:20–1:55 | A tool it made itself, and a mistake it fixed | `/?tour=S2`: the team run → **Runs**: Planner hands off to Tool Forge (2 and 4 calls); "Busiest weekday, before the tool": step 4 failed "no such column", step 5 corrected. **Tools**: checks pass on towns it never saw → Approve → ask again: 1 call | "No tool answers this, so Tool Forge writes read-only queries. When the database refused one, it read the error and fixed it itself. The query kept coming back, so code checked it on new towns and I approved it as a tool. Next time: one call." | `demo:team:new-tool`, `demo:new-tool-before`, `live:c5-learned-tool` |
| 1:55–2:15 | Roads change | `/?tour=S6`: the Kazipet bridge: drivers' notes in Telugu and English, 45 delays all inside the closure and none after, "Expired on arrival" | "Route knowledge comes from drivers. When the road reopened, the delays stopped, so this lesson was stored as expired and is never given to the agent." | `/api/learning/lessons/L-T01-011/evidence` |
| 2:15–2:35 | Proof, including what failed | **Proof & audit**: the per-company chart (unsafe drafts 2→0, 1→0, 6→0), the scoreboard with its ✕ marks, then **Check our claims**: plan commit before result commit | "On a world it had never seen, run three times: lessons took unwritten rules from 48 to 90 percent, a new company from 33 to 100 on day one, with no unsafe drafts and nothing private leaked. Every experiment was fixed in advance, and the ones that missed their bar are here too." | EXP-011R, `artifacts/experiments_index.json` |
| 2:35–2:45 | Your call (live) | `/?tour=S4`: retire the rule → the "You retired a lesson" card → live run, 32 ft → Undo → 22 ft; runs left shown in the header | "And it's your call: switch the rule off and the live plan follows. Live on Muse Spark 1.3." | live run (label the clip "live") |
| 2:45–2:50 | Close | Repo + hosted link; "Same model. Verified experience. Safer plans." | "Built during the hackathon on Muse Spark Open, Muse Spark 1.3 and Muse Voice Transcribe." | README |

**Also say once, honestly:** the data is synthetic (allowed; it's how we can score against hidden truth), the team of agents is not more accurate than one Planner (EXP-013), and whether each agent improves over versions is not measured yet (EXP-014).

## Shot list and assets
- [ ] Voice request recorded in Roman Telugu (owner), with English subtitles
- [x] S1 replays (T01 cold and with lessons) in `demo/replay_runs.jsonl`
- [x] A genuine failure: the cold 32 ft draft, and the real SQL error fixed by the agent (`demo:new-tool-before`)
- [x] New-tool before/after replays in the hosted bundle (browser tests cover the flow)
- [x] Runs swimlane, Learning evidence charts, Proof scoreboard and chain of custody (screens in `web/readme-assets/`)
- [ ] English subtitles for every Telugu line
- [ ] S4 live clip labelled "live"; recorded segments show "Recorded" in the app

## Recording checklist
- [ ] Screen at 1080p, browser zoom fixed, notifications off, incognito window
- [ ] Hosted demo: open it once a few minutes before
- [ ] Company: Sri Kakatiya Logistics (T01); a fresh visit for each take, so the lessons start as recorded
- [ ] Spoken script timed under 2:55
- [ ] Uploaded; link works in incognito

## Hosted demo
- **URL:** https://anubhav-metahackathon.streamlit.app/ (deployed 2026-10-30, no keys, `ANUBHAV_PUBLIC=1`)
- **Modes:** replay (default, free) · live (only if keys are added; 8 runs per session, 60 per day)
- [x] Spend cap enforced · [x] Per-visitor state · [x] Works in incognito (owner checked 2026-10-30)
