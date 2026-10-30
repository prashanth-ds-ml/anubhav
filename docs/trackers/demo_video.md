---
tags: [tracker, demo]
---
# Demo video (≤ 3:00) and hosted demo

The video is the primary artifact. Final-round judges also try the hosted demo, following the same flow, so it must reproduce the video reliably. Script drafted by Nov 1; recorded Nov 3. Storyboard from PRD v3.1 §16.

## Storyboard
| Time | Beat | On screen | Narration (draft) | Asset ready? |
|---|---|---|---|---|
| 0:00–0:18 | Problem | A 32 ft truck that passes every check but can't enter one Jangaon entrance | "Your best dispatcher knows this. Your software doesn't." | ⬜ |
| 0:18–0:45 | Baseline | Roman-Telugu request (voice) → MCP calls → wrong draft, with trace | | ⬜ |
| 0:45–1:20 | Learn | Driver note mined → narrow candidate lesson → evidence and counter-evidence | | ⬜ |
| 1:20–1:45 | Review and reuse | Reviewer approves the scoped lesson → new task gets the safe draft | | ⬜ |
| 1:45–2:05 | Safety | Misleading habit rejected; double-booking blocked | | ⬜ |
| 2:05–2:25 | Tool-use patch | Loop A diff tested against baseline; gate decision | | ⬜ |
| 2:25–2:48 | Proof | Arms A/B/C/D (+E new company) with counts; limits stated | | ⬜ |
| 2:48–3:00 | Close | One-line contribution, Meta model roles, repo and demo link | "Same model. Verified experience. Better decisions." | ⬜ |

## Shot list and assets
- [ ] Telugu / Roman-Telugu voice request recorded (self)
- [ ] Golden-path replay artifact saved (safety net)
- [ ] A real failure trace (genuine, not staged)
- [ ] Learning Lab review capture
- [ ] Loop A diff + paired probe capture
- [ ] Benchmark chart (final numbers)
- [ ] Architecture diagram (from `diagrams/`)
- [ ] English subtitles for every Telugu line
- [ ] Any replayed segment labelled "replay"

## Recording checklist
- [ ] Screen at 1080p, browser zoom fixed, notifications off
- [ ] Clean DB reset before each take
- [ ] Spoken script timed under 2:55
- [ ] Uploaded; link works in incognito

## Hosted demo
- **URL:** https://anubhav-metahackathon.streamlit.app/ (deployed 2026-10-30, no keys, `ANUBHAV_PUBLIC=1`)
- **Modes:** replay (default) · live (spend-capped) · judge seed challenge
- [ ] Spend cap enforced · [ ] Rate limit · [ ] Works in incognito
