---
tags: [handoff, web, merge]
status: Merged into the repo Nov 2 (D-049); findings 4, 4c and the tool-test failures fixed on the server side (H1). Not deployed.
date: 2026-11-01
---
# Web app merged onto the current backend

Related: [[Backend_Report]], [[UX_Revision_Plan_v1]], `contracts/api.md`, `contracts/events.schema.json`.

The React app in `web/` now talks to the FastAPI backend in `src/anubhav/api/`. The earlier web-side server (`api/`), its service module and its contract have been dropped, as `Backend_Report.md` section 16 asked.

## What changed

| Area | Change |
|---|---|
| `web/src` | Rewritten against the real API: named server-sent events, the `NO_REPLAY` error, `/api/session` instead of `/api/capabilities`, the real event fields (`reply`, `to`, `pass`, `lessons[]` and so on) |
| Company and lessons | A company picker (T01, TNEW) and a "Use approved lessons" switch. A saved request that was only recorded with the other setting switches it and says so |
| Real recordings | The chat plays the 32 saved runs. The label reads "Recorded run, date, model, lessons on or off". A run from the scripted test model is labelled "Scripted example" |
| Learning tab | Shows the same request without and with lessons (32 ft against 22 ft), every lesson with its evidence, the learning timeline and repeated questions |
| Proof tab | Built from `/api/proof`: learning, new company on day 1, team against one Planner, learned tools, rule mining, and what is not measured |
| Voice | `POST /api/voice` added to `src/anubhav/api/routes.py`, and `session.voice` says whether it is available. Tests mock the transcription call |
| Docker | The Dockerfile has a Node build stage that builds `web/dist`. `.dockerignore` no longer drops all of `web/` |
| Contract | `contracts/api.md`: `POST /api/voice` and `session.voice`. Both need sign-off from the AI engineer |
| Lesson decisions (Nov 2) | Each lesson in the Learning tab has the controls the server allows: a waiting lesson can be approved as advice, approved as a rule (only the enforceable kind, and only with a written note of what was verified), or rejected with a reason; an active lesson can be undone (it goes back to waiting) or retired with a reason; a rejected or retired one can be undone. A lesson with no history, such as the one that expired on arrival, shows no buttons. Uses `POST /api/learning/lessons/{id}/decide`, unchanged. Because "undo approval" returns a lesson to waiting, a visitor can show the whole approve step with the existing T01 lessons, and no change to the demo world is needed. The page says that saved runs stay as they were recorded |
| Tool approval (Nov 2) | In the Learning tab a person checks a repeated question, approves it as a tool or declines it, retires it, and asks the question again in the chat. It uses `POST /api/tools/candidates/{key}/check`, `POST /api/tools/{id}/decide` and `/retire`, which already existed; nothing in the contract changed. A tool that fails its checks cannot be approved. After approval the tab shows the recorded before and after (5 calls, $0.066, hedged answer; 1 call, $0.016, "Saturday") |

Files set aside by the merge are in `handoff/superseded-by-merge/`, outside the repo.

## Test status (Nov 2)

| Suite | Result |
|---|---|
| Web unit (`cd web && npm test`) | 13 passed |
| Browser (`cd web && npx playwright test`) | 85 passed (Nov 2, after the lesson controls and tool approval), one worker, about 11 minutes on this machine; type-check clean |
| API (`uv run pytest tests/api -q`) | 99 passed, including 7 new voice tests |
| Whole Python suite (`uv run pytest -q`) | 545 passed, 0 failed, about 29 minutes on this machine |

The browser tests start the real API on port 7870 in public replay mode with no keys. Run `npm run build` first, because the API serves `web/dist`.

### Please run these and update the results

The machine this was built on has about 16 GB of memory, and the browser run was stopped twice by the system for low memory before it finished once (85 passed, Nov 2). The Python suite was last run Nov 1. Please run all four below on a machine with at least 6 GB free, and put the results in the table above and in the status line of `Implementation_Plan_Sprints.md`.

| Step | Command (from the project root unless stated) | Expected | About |
|---|---|---|---|
| 1. Whole Python suite | `uv run pytest -q` | 545 passed | 29 min |
| 2. API tests only (faster check) | `uv run pytest tests/api -q` | 99 passed | 1 min |
| 3. Web type-check and unit tests | `cd web && npm ci && npx tsc --noEmit && npm test` | no type errors, 13 passed | 1 min |
| 4. Browser tests | `cd web && npm run build && npx playwright install chromium && npx playwright test` | 85 passed | 11 min |

Notes:
- Step 4 starts the API itself on port 7870 in public replay mode and needs no keys. If port 7870 is already in use it reuses what is running there, so stop any other server on that port first. To use a different Python, set `ANUBHAV_PYTHON` to its path.
- Run step 4 with nothing else heavy open. A test that says "element not found" after 30 or 60 seconds, with several others failing near it, has usually been starved of memory, not broken; run it again alone with `npx playwright test e2e/<file>.spec.ts` before treating it as a failure.
- The files in `web/tools/` are not part of the suite. `node web/tools/screenshots.mjs` regenerates the README images against a running API (`BASE_URL`, default `http://localhost:7860`), and the two `*_probe.mjs` files repeat a new-visitor check 12 times.
- Voice is the one thing no suite here can show: the tests mock the transcription call. A real recording with the key set is a manual check.

When you report back, please give for each step the pass and fail counts, the time, the free memory, and the full text of any failure. If a test fails that passed here, that is the useful finding.

## What the merge found

1. **The first visit is slow.** A new visitor's first `GET /api/companies` took 3.3 s, and with six new visitors at once it took about 10 s. The cause is loading all four companies for a new workspace. It is in `src/anubhav/service/session.py`, so I did not change it. Options: load only the requested company, or keep the loaded companies in memory across visitors. The page shows skeletons meanwhile.
2. **A race, fixed in the web app.** A request sent before the saved requests had loaded was told "No saved run matches that". It now waits for them. There is a test for it.
3. **A scroll bug, fixed in the web app.** A card can grow a line after the last scroll (text re-wrapping), which left the answer about 22 px below the fold. The chat now keeps following the newest message unless the person scrolls up.
4. **Visitor folders pile up.** Each visitor creates `data/worlds/<world>/runtime/sessions/<id>/`. My test runs made 866 locally. On a Space with no cleanup this grows without limit.
4b. **One new visitor gets many sessions (found Nov 2, and the likely cause of 4).** The server makes a new workspace for every request that arrives without the session cookie. A new visitor's page fires about 9 requests at once, so the server made 5 to 9 workspaces for one person (7 of 10 test visitors), and the cookie kept whichever answer arrived last. An approval made in the first seconds could land in one workspace while the next read hit another, so it seemed to vanish (2 of 10 lost it). I fixed the web side: the first call is `/api/session` alone and every other call waits for it (`web/src/lib/api.ts`), and a test checks that a new visitor gets exactly one session. The server still creates a session per cookieless request, so any other client would hit it. Options: create the workspace folder only on the first action that changes something, or make the first creation single-flight.
4c. **A new visitor's lessons are copied in without a lock (found Nov 2, `src/anubhav/service/session.py`, `store()` lines 111-116).** `LessonStore(path)` creates the file before `load_exp008_lessons()` has filled it, and the check is `not path.exists()`. Two requests from one new visitor at once then behave in one of two ways: both seed, and the second fails with `sqlite3.IntegrityError: UNIQUE constraint failed: lessons.lesson_id`, which the API turns into a 500 (seen on `GET /api/dashboard/fleet` and `/company`, 3 of 12 new visitors); or the second sees the file, skips seeding and reads an empty or half-filled table, and returns a 200 with no lessons. The second is worse: the Learning tab showed "nothing learned" for a new visitor who opened it in the first seconds (11 of 12 test visitors before the workaround). Suggested fix, about eight lines: one module-level `threading.Lock`; take it when the workspace is public and not yet marked seeded; inside it check again, seed into a temporary file and rename it into place (or mark the workspace seeded only after `load_exp008_lessons()` returns), then release. Workaround in the web app: the first-visit gate also makes one `GET /api/tools?company=T01` alone, which seeds the store in about a second without loading the company; 12 of 12 test visitors then saw their lessons with no failed request. It is harmless once the server is fixed, and then `started()` in `web/src/lib/api.ts` can go back to waiting for `/api/session` only.
4d. **Some first-visit reads are slow even with the company loaded (measured on my machine with other test processes running, so treat as rough).** For a new visitor: `/api/tools/candidates` about 10 s, `/api/agents` about 8 s, `/api/learning/lessons` 1.3 to 2.6 s, `/api/learning/timeline` about 1 s. These read the visitor's runs and lessons each time. Caching the computed result per visitor and invalidating it when a decision is made would cut this.
5. **Replayed drafts cannot be approved.** The Route plans tab says "Saved run" and shows no approve button, as the report's gap 7 describes.

## Suggested edits to files the AI engineer owns

I did not change the README or `docs/deploy.md` beyond what is listed here, because the README is the project's front page.

- **README, "Other commands":** the test line says 537 tests; the whole suite now reports 545 passed. Add `cd web && npm ci && npm run build && npx playwright test` for the web tests, and say the API serves the built app at `/`.
- **README, "Try it":** add the web app next to the Streamlit link once a Space exists, with `web/readme-assets/start.png` and `run-light-1440.png` as screenshots.
- **README, "Repository layout":** add `web/   React app, built into web/dist and served by the API`.
- **`docs/deploy.md`:** the Docker section now includes the web build and the checks I ran (see the file).

## Still open

- The Docker image builds and runs (checked Nov 1, no keys): the page and its script load at `/`, `/api/health` and `/api/session` answer, a saved run plays, and the app runs as a non-root user. It has not been pushed to a Space.
- Real voice transcription has never been run, because there is no key here.
- Live mode (typing any request) is off, so a visitor can only play saved requests.
- Every T01 lesson starts active, so a visitor approves one by first undoing its approval. That works and is tested, but it is not the same as a lesson arriving as a proposal. A pending lesson in the demo world would tell the story more directly (the AI engineer's call).
- Drafts cannot be approved or rejected in the page: a replay creates no draft (gap 7), so this only makes sense for live runs.
- Hand-off reply (`/api/runs/{id}/resume`), run feedback, the nightly review and publishing a pack are not in the page. Of the 55 routes the page uses 23 (it was 18 before this work: the tool approval added four and the lesson decisions one).
- Per-agent improvement over versions is shown as "not measured yet".
- New screenshots are in `web/readme-assets/` (start, run in light and dark, run at 1024 px, orders, why-this-plan, ledger, agents, learning, proof). Regenerate them with `node web/tools/screenshots.mjs` against a running API. The README does not show them yet; that is the AI engineer's file (see below).
- The 60-second test with someone outside the project has not been done.
- Nothing is deployed. A deploy needs the Space name and an explicit go-ahead.
