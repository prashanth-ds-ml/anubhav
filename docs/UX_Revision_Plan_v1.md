---
tags: [design, ux, plan, react]
status: IMPLEMENTED U1-U8 and moved onto the AI engineer's backend (Nov 1-2). 85 Playwright, 13 web unit, 99 API and 545 whole-suite Python tests green (Nov 2). U9 (cold 60-second test by a person outside the project) still open; `POST /api/voice` awaits the AI engineer's sign-off
date: 2026-11-01
---
# UX revision plan v1: judge-ready React app

> **Nov 2:** the layout here (one Desk with nine tabs) was replaced by [[Design_Doc_Demo_v1]] and built in sprints 1–7 ([[Build_Plan_Demo_v1]]): six main tabs with addresses, a guide that stays across tabs, evidence charts, Runs, Agents and Proof & audit. The audit findings and principles below still hold.

Source: UX audit of the running app (Nov 1) played as a first-time judge. Builds on [[Anubhav_MultiAgent_Design_v1]] (section 4.8 visual system) and [[Implementation_Plan_Sprints]] (this becomes "Sprint 3b", between Sprint 3 and the Sprint 4 freeze). Deadline: Thu Nov 5, 7:30 AM IST; nothing new after Nov 3 evening.

## 1. Understanding summary
- **What:** a chat-first revision of the React app that answers the 13 audit findings: intro, layout, text and voice input, plain language, honest placeholders, loop strip, mobile, ledger, accessibility.
- **Why:** a judge should understand the product and complete a run within about 60 seconds, unguided.
- **Who:** hackathon judges via a hosted link (desktop first, phone possible). The web engineer owns the work; the AI engineer integrates and owns agent behaviour and benchmark data.
- **Constraints:** two working days; replay mode answers only saved runs; existing tests stay green (336 Python, 16 API, 4 web, 10 Playwright); changes in `web/` and `api/` plus agreed contract edits; no names in code or commits.
- **Non-goals:** live-mode build-out, new agent features, a real map, filling the placeholder tabs with data (that comes from the AI engineer's backend).

## 2. Assumptions
1. First meaningful view under 2 s once the demo world is warm; a handful of concurrent judges; synthetic data, no login; fixture fallback with a banner if the backend is down.
2. Voice works only in live mode (keys in Space secrets, existing caps of 8 per session and 60 per day apply). Audio goes to the Muse transcription API and is not stored by us; the UI says so.
3. A typed request in replay mode is matched to a saved prompt by word overlap; no model call.
4. A Telugu-script prompt needs one new saved run from the AI engineer; optional.
5. Dim "Approve" and "Improve" in the loop strip: they happen outside a run, when a person approves a lesson or tool.

## 3. Design
### 3.1 Layout and first impression
Intro strip at the top: one-sentence pitch plus three facts (drafts only, a person approves, replay or live). Chat on the left at about 60% width (conversation, input, prompt chips); dashboard tabs on the right at about 40%. Same two columns at 1024 px; stacks under 860 px with chat first. Roster and loop strip stay at the top with a one-line explanation per item on hover and focus. A run ends with the agent's reply as a normal chat message; the step cards sit under "Show how it got there" (open during replay). The chat auto-scrolls so retry, "No tool for this" and handoff stay in view. Orders rows get a "Plan a truck" button that fills the input.

### 3.2 Text and voice input
Text area with Send (Enter sends, Shift+Enter newline). Replay mode: close match to a saved prompt shows a one-click "Closest saved request" chip; no match says so and offers the chips. Mic button: records in the browser, converts to 16 kHz mono WAV, 30 s max with timer and Stop; posts to `POST /api/voice`, which reuses `muse.transcribe` (town names as hints) behind the existing live-call counter. The transcript lands in the text box with audio length and cost; nothing is sent until the person presses Send. Errors: live off (mic disabled with reason), permission denied, cap reached or network failure (recording kept for retry), silent audio. New contract item: `POST /api/voice` returns `{ transcript, audio_ms, cost_usd }`.

### 3.3 Clarity and honesty
Loop-step explanations; readable summaries in place of raw JSON (with "Show details"); plainer labels (`tool_missing` -> "No tool for this. Asking the Analyst."; "Held-out score" -> "Score on unseen test cases"; "code" -> "Safety checks (code, not AI)"). The loop strip lights only steps backed by a real event (Act, Observe, Verify, Learn). A visible "Sample" badge on anything that is not real data (draft cards, lessons, timeline, Agents, Learning, Proof) until real data lands. Mobile: tables scroll inside their container, roster collapses to one row. Ledger: no wrapping in time and agent columns, summary instead of JSON. Accessibility: tab roles with `aria-controls` and arrow keys, live region announcing only key events. Small items: favicon, meta description, light/dark toggle.

### 3.4 Testing
API contract tests for `/api/voice` with `muse.transcribe` mocked (success, no key, cap reached, silent, oversize); Playwright (replay, no keys, fake microphone device) for layout at 1024, 1440 and 390 px, answer message, auto-scroll, closest-prompt chip, disabled mic reason, "Plan a truck", Sample badges; axe checks kept, arrow-key tab test added; a timed cold test by someone outside the project (state what it does and finish a run in 60 s).

## 4. Tasks (web engineer; Nov 1 evening to Nov 3 before the cutoff)
| ID | Task | Check | Depends |
|---|---|---|---|
| U1 | 60/40 chat-first layout, intro strip, prompt chips, stack under 860 px | Playwright at 3 widths, no sideways scroll | none |
| U2 | Conversation model: user message, answer message, auto-scroll, "Show how it got there", readable summaries | answer visible, alert in view | U1 |
| U3 | Text box and closest-saved-prompt chip | match and no-match cases | U1 |
| U4 | Voice: recorder, `/api/voice`, editable transcript, error states | mocked API tests, fake mic | contract agreed, U3 |
| U5 | Plain-language labels, honest loop strip, tooltips, Sample badges | text and badge tests | U2 |
| U6 | "Plan a truck" on orders; number and date formatting | click fills the box | U3 |
| U7 | Mobile overflow, ledger layout, tab ARIA, live-region trimming, favicon, meta, theme toggle | axe and mobile | U1 |
| U8 | Refresh Playwright suite, screenshots, optional GIF | green | U1-U7 |
| U9 | Cold 60-second judge test; fix showstoppers only | pass | U8 |

**Blocked on the AI engineer (contract items):** `/api/voice` sign-off and live keys in Space secrets; real draft events; real Agents, Learning and Proof data; optional saved Telugu-script run.

**Cut order if late:** Telugu chip, theme toggle, GIF. Never cut U1, U2 or the Sample badges.
**Gate (Nov 3 evening):** Playwright green, the 60-second test passes, a clean patch handed to the integrator under the sprint plan's handoff protocol (section 7: no names in files, no co-author trailers).

## 5. Decision log
| # | Decision | Alternatives considered | Why |
|---|---|---|---|
| 1 | Chat-first layout, about 60/40 | keep the dashboard-first layout | the story happens in the chat, which judges never looked at |
| 2 | Voice via real Muse transcription, live-only | browser speech recognition; canned transcript in replay | consistent with the app and honest; browser recognition is weak for Telugu and sends audio to a third party |
| 3 | Transcript goes into the editable box; sending is a separate step | auto-send after transcription | Telugu mishearings are likely; the old app already works this way |
| 4 | Replay typed input: word-overlap match plus a chip | model-based matching; reject unsaved text | free, predictable, honest |
| 5 | Dim Approve and Improve and explain why | map `agent_done` to "Improve" | the old mapping was not true |
| 6 | "Sample" badges on placeholders | hide the empty tabs | hiding reads as missing features; labelling is honest |
| 7 | Plan expressed as "Sprint 3b" tasks U1-U9 | rewrite Sprint 3 and 4 | fits the sprint plan's format and cut-order rule |

## 6. Risks
- Two working days: cut order above; U1, U2 and the badges are protected.
- Voice depends on live keys and budget; if keys are absent at the demo, voice shows disabled with a reason, and typing plus chips still work.
- Contract drift: `/api/voice` and any new fields need both engineers' agreement before U4 merges.
- Placeholder tabs stay thin until the backend data lands; the badges keep that honest.
- Audio privacy: the UI discloses that audio goes to the transcription API; no audio is stored.

## 7. Open items
- Cold 60-second test by someone outside the project (U9).
- `POST /api/voice` and `session.voice` need the AI engineer's sign-off; real voice has not run (no key).
- A new visitor's first load takes about 3 s (about 10 s with six at once); the page shows placeholders meanwhile. The fix is in the backend (see [[Handoff_Web_to_AI_Engineer]]).
- Deploy to a Space needs the Space name and an explicit go-ahead.

## 8. What changed after this plan (Nov 1-2)
The AI engineer's backend replaced the web-side server, so the plan's assumptions changed:
- **Real data, not samples.** Draft cards, lessons, the Agents tab, the Learning tab and the Proof tab now read the real API and the 32 recorded runs, so the "Sample" badges are gone. A run from the scripted test model is labelled "Scripted example"; a real one reads "Recorded run, date, model, lessons on or off".
- **Telugu prompt.** There is a saved Telugu-script run, so the Telugu chip stays.
- **Replay matching.** Typing in replay mode matches a saved request on the server (`NO_REPLAY` when none fits); the page switches the lessons setting and says so if the saved run used the other one.
- **Company and lessons controls.** A company picker (T01 and the new company) and a "Use approved lessons" switch.
- **Two bugs found by debugging, both fixed with tests.** A request sent before the saved requests had loaded was told "No saved run matches that"; and a card that re-wrapped after the last scroll left the answer about 22 px below the fold.
- **Screenshots** are regenerated (`node web/tools/screenshots.mjs`).
- The older test counts in section 1 (336 Python, 16 API, 4 web, 10 Playwright) are history; see the status line for today's.

## 9. Judge scenarios and polish pass (Nov 2, D-050, D-051)
The app now opens on five scenario cards (S1–S3 recorded, S4–S5 live on Muse Spark 1.3). A UX audit of 27 screenshots (desktop,
1280×720 laptop, dark, phone) found the payoff hard to see; all 16 findings were fixed:
1. A plan card after each run: the truck's length in large type, ✗/✓ against the site's learned gate rule, the lessons it used.
2. Replies render bullet lists and headings instead of raw `*` and `#`.
3. The scenario guide is a slim stepper (one step at a time, progress dots, "All steps" to expand); finished scenarios show the before and after side by side.
4. Steps open the right tab and scroll to and highlight the item: the gate lesson, the tool candidate, the Proof figure; a new plan opens Route plans.
5. Tools have their own tab, "New tools". The approve step ticks only once a tool is approved; panels keep their place while reloading; tools are titled by the questions they answer.
6. The first screen fits a 1280×720 laptop: the problem in two lines with "Read more", compact scenario cards.
7. Proof opens on three headline figures (48% → 90%, 33% → 100%, 0 unsafe), each linked to its result file.
8. Run steps show a readable line; raw JSON is behind "Details".
9–16. Draft cards show the truck size and the gate check; the recorded-run note is neutral, not a warning; ledger times read "29 Oct, 19:44" and long notes are shortened; fleet statuses read "Insurance expired"; the Orders button no longer clips at 1280 px; agent versions read "Version 1"; voice and live-mode reasons are in plain words; `/?tour=S1` opens a scenario directly.
Bugs found on the way: "Why this plan" showed empty lesson rows (the server sends text, not objects); the Fleet tab crashed on a list of reasons.
