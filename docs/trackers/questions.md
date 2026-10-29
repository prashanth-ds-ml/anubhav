---
tags: [tracker, questions]
---
# Open questions

Office hours run in Discord #office-hours, weekdays: **Oct 27–30 at 7:30–8:30 PM IST**, **Nov 2–4 at 8:30–9:30 PM IST**. None on Oct 31 or Nov 1.
**Last full day for submission questions: Tue Nov 3.**

## For the Meta team (office hours)
| # | Question | Why it matters | Asked on | Answer | Status |
|---|---|---|---|---|---|
| Q-01 | Does Muse Voice Transcribe support Telugu (and code-mixed speech)? | Voice gate (D-003) | docs | **Yes**: Telugu is among 25 languages, with code-switching | ✅ |
| Q-02 | Is there a limit on tools/schemas per request for Muse Spark? | Arm A feasibility | test T5 | No stated limit; 40 work. Docs suggest `defer_loading` + `tool_search` for large sets | ✅ |
| Q-03 | Is temperature 0 / seed deterministic on Muse Spark? | Repeat strategy | test T8 | **No** (2 of 3 identical) | ✅ |
| Q-06 | Muse's built-in `tool_search` / `defer_loading` vs. our BigTool retrieval: is it worth comparing as another arm? | Meta tooling score | | | ⬜ |
| Q-04 | Can judges try a hosted demo, or is the video primary? Any expectations for a "live product"? | FR-14 effort | user read it in hackathon info (2026-10-27) | **Final-round judges try the demo themselves**, following the same flow as the 3-min video. So the hosted demo must reliably reproduce the video script | ✅ |
| Q-05 | Is using open-source libraries (LangGraph, langgraph-bigtool, MCP SDK) fine if clearly labeled? | Rules / originality | | | ⬜ |
| Q-07 | Is building on a published research method (Harness²-style loop) with attribution fine for originality? | Rules / originality | | | ⬜ |

## Internal / technical
| # | Question | Resolution | Status |
|---|---|---|---|
| I-01 | Which email should commits use (work vs. personal)? | | ⬜ |
| I-02 | Hosting: Hugging Face Spaces vs. Streamlit Community Cloud vs. Modal | | ⬜ |
| I-03 | Embedding model for BigTool retrieval (local vs. API) | | ⬜ |
| I-04 | Sources for the impact stats (Census 2011 Telugu speakers; MSME counts) | | ⬜ |
| I-05 | Do the Harness² repo / arXiv 2610.14224 and the MCP 2026-07-28 spec link actually exist? | Layer 0.2 | ⬜ |
| I-06 | Impact stats for Indian road freight / 3PL (fleet size, share of small operators) with sources | | ⬜ |
| I-07 | Interviewee's permission to quote anonymised lines in README / video | | ⬜ |
| I-08 | Hosting for Streamlit + MCP: Hugging Face Spaces vs Streamlit Cloud vs Modal | | ⬜ |
