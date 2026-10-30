---
tags: [plan]
date: 2026-10-30
---
# Implementation plan: from today to submission (Oct 30 → Nov 4)

Written on Oct 30 after the three-part audit, the workshop review and the owner's demo brief. It combines the open items in [[todo]] with the new demo plan (D-039, D-040). Day-by-day status lives in [[todo]] and [[progress]]; this page explains *what* and *how*.

**Deadline:** Wed Nov 4, 9:00 PM ET = Thu Nov 5, 7:30 AM IST. Target: submit on Nov 4 IST.

## 1. The demo we are building toward

The owner's goal is to prove that the agent **learns from its own actions**: it uses the right tools, and when it gets something wrong, it learns and corrects itself. The judges should be able to see every step.

**Story (session 1 → nightly review → session 2), one company (T01):**

| Session 1: three different failures | What the nightly review sends it to | Session 2: the same requests |
|---|---|---|
| A 32 ft truck is drafted for a site with a narrow gate (a fact nobody wrote down) | **Business facts** (Loop B): a proposed lesson → evidence check on the records → a person approves it | The safe vehicle is drafted, and the lesson is cited |
| The agent calls the same tool repeatedly, or runs out of steps | **Tool use** (Loop A): one small change to the instructions → old vs new test → a person approves it | Fewer calls, same answer |
| "What is our on-time % by weekday?": no tool can answer it | **New tool** (new): the agent writes a read-only query, it gets reused, and the query becomes a saved tool → a person approves it | One call to the new tool |

The **Logs page** shows all three streams on one timeline: what the agent planned, which tool it called, what came back, what it learned, and who approved it.

**Two other businesses (hospital, call centre): not built.**
- Building each one means a simulated company, tools, evidence checks and an experiment: 2–3 days per industry.
- "Medical" is on the hackathon's anti-project list.
- "A new business is added" is already proven: T03 went from 33% to 100% with a pack (EXP-011), and onboarding a client is an adapter mapping (D-030).
- In the video, other industries get one slide as future work, not a claim. See [[ideas_parking_lot]].

## 2. Audit of the to-do items recorded earlier (Oct 30)

| Item | Status | Evidence |
|---|---|---|
| Step 1: 1.1–1.11, W1, W2, W6, W7 | ✅ done, **not committed** | 147 tests (+19, one per bug); `tests/ui/test_app.py`; hosted-style copy checked on localhost:8502; D-038 |
| W3 reply check | ⬜ not started | `graph.finish` re-checks drafts but not the reply text |
| W4 refusals name the next step | ⬜ not started | `safety.py:76-78` says only "x kg > payload" |
| W5 plan → act → observe timeline | 🟨 partial | The workbench lists tool steps and draws a run graph; the model's plan text and refusals in red are missing |
| Step 2: README test count | ⬜ | README says "238 tests"; it is now 147 + 128 archived = 275 |
| Step 2: README "Limitations" | ✅ exists | The submission checklist already ticks it; re-read it after this plan |
| Step 2: Harness² credit | ⬜ | Not in README or `LICENSES_AND_ATTRIBUTION.md` |
| Step 2: FR-19 → 🟨 (arm D not run) | ⬜ | [[progress]] still shows ✅ |
| Step 2: risks R-04/R-17/R-22, R-18/R-21 | ⬜ | Still marked "open" or "watching" with old text |
| Step 2: questions I-01/I-02/I-03/Q-06, ask Q-05/Q-07 | ⬜ | Still ⬜ in [[questions]] |
| Step 2: [[cost_ledger]] totals, [[harness_versions]], [[rubric_scorecard]] | ⬜ | Templates are still unfilled (harness_versions "Model: `<muse model id>`"; the rubric has no scores) |
| Step 2: `Untitled*.canvas` in the repo root | ⬜ | 3 files are still there |
| Step 2: spend alerts on Meta and Baseten | ⬜ owner | Cost ledger: "Spend-limit notification set: ⬜" |
| Step 3: deploy, video, README links, submit | ⬜ | [[demo_video]] storyboard is the old one (Jangaon only); no URL |
| Oct 30 daily "optional build" list | see below | Question bank → folded into C6; "plan tomorrow" replay → E2; real-capacity fix → W4; judge seed challenge, double-booking UI → cut |

## 3. Workstreams

Each workstream lists its files, tests and when it counts as done. Estimates are for one person with Claude.

### P0. Commit step 1 (tonight, 15 min)
- One commit by prashanth-ds-ml, with no co-author trailer (D-028), after the owner has checked localhost.
- **Done when:** `git log -1` shows the owner as author, and the tests pass on the commit.

### A. Step 1b: reply check and helpful refusals (Oct 31, ~1.5 h)
**A1 · W3 reply check** (`agent/graph.py: finish`, plain code):
- every draft id and vehicle id mentioned in the reply exists in this run's drafts or tool results;
- the reply never says the goods were dispatched or confirmed. The words to look for (English, Roman Telugu, Telugu) live in `configs/operating_rules.yaml: reply_claims`, beside the other written rules, not in code (D-034);
- result: `reply_checks` in the finish step, shown as a warning on the workbench;
- tests: a fake model reply with an invented draft id is flagged, and so is one saying "dispatched".

**A2 · W4 refusals name the next step** (`runtime/safety.py`, `runtime/broker.py`):
- `CAPACITY_EXCEEDED` / `VOLUME_EXCEEDED` add the load needed and up to 3 vehicles that are free that day and big enough (from the same data `plan_board` uses);
- this is the EXP-011 "real capacity" miss (the agent refused to overload but didn't offer another truck). It is a UX fix: any claimed gain needs a new pre-registered run;
- tests: an overloaded draft's error lists a vehicle that fits; it never lists one that's busy or in the workshop.

### B. Logs page: everything the agent did and learned (Oct 31, ~3 h)
Builds on W5. New page `app_pages/logs.py`, plus helpers in `ui/core.py`. It reads only what is already recorded:

| Stream | Source | Row shows |
|---|---|---|
| Agent runs | `data/traces/*.jsonl` (`trace.load`) | Request → for each turn: the model's plan text, the tool call and its arguments, a short result; refusals in red; the reply check; the cost |
| Business facts | lesson store `events` table | proposed → gate verdict with support/counter counts → approved / rejected / retired, by whom |
| Tool use | harness store (feedback, versions, paired tests) | issue found → patch proposed → old vs new → activated / rejected |
| New tools | tool store (workstream C) | query used → candidate → checks → approved |
| Reviews | review reports (workstream D) | what each nightly review found and where it sent it |

- Filters: company, stream, date. Each row expands to the raw JSON ("what the model saw").
- In hosted mode it shows the visitor's own session plus the saved demo runs.
- Tests: the page opens with no keys (add it to `PAGES` in `tests/ui/test_app.py`); a recorded run shows one row per tool call, with refusals marked.
- **Done when:** a judge can follow the three session-1 failures and their fixes on this page alone.

### H. Onboarding: the agent learns what the business is (Oct 31, ~4–5 h; D-041)
> **Oct 31 (D-042): slimmed after the deep audit.** Only H1 and H4 are built (profile from the records, editable, in the prompt; page). H2 (Muse questions) and H3 (answer checks) are cut. Deploy moved to Oct 31.

Today the agent knows only "the dispatch-planning assistant of T01, a regional transport company". New: **session 0**.

**H1 · Draft profile from the data** (`learning/profile.py`, code only, no model call):
- facts computed from the company's own records: towns and site count, client brands, fleet (own vs hired, by class), orders per day, goods handling classes, planner languages, busiest weekdays;
- every number cites the table it came from.

**H2 · Questions** (Muse Spark, one call): given the draft, pick 5–7 questions about what the records can't show: priorities (cost / on-time / fill), customers that must never be late, rules applied but not written, who approves what, peaks, the company's own words. Each question is in the owner's language.

**H3 · Answers are checked against the records** (Muse structures the answers into fields; code checks them):
- stated rules of a kind the gate knows (weekly off, receiving hours, site access, vehicle requirement…) are run through `gate.check`: supported → a lesson candidate (`source = owner`, needs approval as usual); contradicted → shown back with the count ("14 Sunday deliveries in September");
- priorities, key customers and words are saved as stated, labelled "owner said".

**H4 · Saved and used** (`profile` table in the lesson store, versioned):
- the agent prompt gets an "About this business" block (≤ 600 characters; data, not instructions), replacing "a regional transport company";
- a "Business profile" page shows the draft, the questions, the answers, the checks and the versions. It works in replay without keys (a recorded onboarding).
- Off in frozen experiment configs (`profile=False`), so EXP-009/011 stay as they were.

**Tests:** the draft profile matches the records; an answer that contradicts the records is flagged with the right count; a supported rule becomes a candidate (not active); the prompt block is capped and has no markup; the page opens without keys.

### I. Evidence for Impact and Meta tooling (Oct 31 – Nov 2; D-043)
| # | Item | Who | Est. |
|---|---|---|---|
| I1 | README honesty pass: test count, a real Limitations section (n per claim: 20 and 9 cases, one run each; synthetic data; generator-made cases; the D-038 version gap), "by our leak check", Harness² and Meta-workshop credit (also in `LICENSES_AND_ATTRIBUTION.md`), FR-19 → 🟨 | Claude | 1 h |
| I2 | Meta models on screen: each model's role and its calls/cost in this deployment (Spark Open plans, Spark 1.3 mines lessons and names tools, Voice Transcribe hears Telugu); Best Open Weights pitch in README | Claude | 1 h |
| I3 | 1–2 cited freight statistics (sources checked, quoted exactly) for README and video | Claude | 0.5 h |
| I4 | Dispatcher review kit: 10–15 learned lessons as a sheet (English + Telugu), true / false / unsure / "not in my region", plus a timing protocol for "plan tomorrow". Results recorded as-is, anonymised, with permission | Claude prepares, **owner** runs it | 1 h + owner |
| I5 | "Who uses this on Monday": import a company's spreadsheet export (orders, sites, vehicles) through an adapter mapping (D-030) into a new company, then the profile and the agent work on it | Claude | 3–4 h, **cut first** |

### J. Measurement on the shipped version (Nov 2; D-043)
- **J1 EXP-011R:** the EXP-011 protocol, 3 repeats, on the current commit (after D-038 and Oct 31 changes), on the unseen world. Pre-registered in [[experiments]] with frozen file hashes before the first call. ~$15 on Spark Open. Reports mean and spread; replaces "one run each" in the README.
- **J2 EXP-012:** new-tool creation on the C6 gap questions, pre-registered, ~$3 (from C6).

### C. New tool creation: the agent writes a query, and good ones become tools (Oct 31 PM – Nov 1, ~8 h)
Design: D-040. **The agent writes read-only SQL, never Python.** Running Python the model wrote on a public host has no safe sandbox on Windows or Streamlit Cloud. SQL over a read-only copy of the company's own records gives the same "write code to analyse" ability with a small attack surface.

**C1 · Query sandbox** (`runtime/query.py`, new):
- builds an in-memory SQLite database from the company's canonical tables (`CompanyData.t`): its own records only, never `truth/`, other companies, the runtime store or the audit log;
- the schema shown to the model is generated from the data (table → columns → types), so no business fact is hardcoded (D-034);
- `PRAGMA query_only = ON`, plus an authorizer that allows only SELECT and read functions (no ATTACH, PRAGMA, writes or `load_extension`);
- a time cap through `set_progress_handler` (2 s), a 200-row cap and a 4 kB SQL length cap;
- text from people (notes, messages, feedback) comes back marked `untrusted_text`, as in the other tools;
- tests: an INSERT, ATTACH, PRAGMA or a never-ending recursive CTE is refused; another company's data can't be reached; untrusted text is marked.

**C2 · `run_query` tool** (`runtime/broker.py`):
- `Tool("run_query", "Answer a question no other tool covers by writing ONE read-only SQL SELECT over the company's records. Use the existing tools first.", Query, "read", …, "analysis")`, with `describe_tables` as its partner (or the schema in the tool description if it stays under ~1.5 kB);
- action class `read`, so viewers and reviewers may use it; it never drafts or dispatches;
- off by default in frozen experiment configs, so EXP-009/011 replays stay as they were;
- tests: the broker offers it; bad SQL returns `BAD_ARGS` with the SQLite message (the model can fix it and retry); a timeout returns `LIMIT`.

**C3 · Remembering useful queries** (`tools/store.py`, new SQLite `data/.../tools.sqlite`, per company):
- every successful `run_query` is saved with the request, SQL, row count and run id;
- code turns the SQL into a template: string, number and date literals become named parameters (a tokenizer, not an LLM), and the template is hashed;
- **candidate rule:** the same template used in ≥ 2 different requests (configurable; 2 for the demo). A person can also mark a single query "make this a tool".

**C4 · Promotion with checks** (`tools/promote.py`):
1. Muse Spark 1.3 proposes a name, a one-line description and a description for each parameter (JSON). Code checks the name is new and snake_case, and the parameters match the placeholders.
2. **Same answer:** with the original values, the template returns exactly the rows of each original query.
3. **Generalises:** it runs without error, within the time limit, on 5 held-out parameter values drawn from the company's own data (other towns, sites, months).
4. **Read-only:** it passes the C1 sandbox.
5. **A person approves** on a new "Tools" tab (in `skills.py`), shown with the SQL, test results and example rows. It can be retired or rolled back.
- Generated tools are **company-private**, like lessons. They never travel in a domain pack.
- Tests: a template that only works for one value fails check 3; a template whose rows differ fails check 2; nothing becomes active without approval.

**C5 · Using an approved tool** (`runtime/broker.py`):
- `Broker(..., learned_tools=…)` adds each approved tool as a `Tool` (category `learned_tools`, action `read`) whose function runs the stored SQL with bound parameters in the C1 sandbox;
- its manifest says `capability_id: company.<name>.v1` and "learned on <date>, approved by <who>";
- tests: an approved tool is offered and returns the same rows as the query it came from; a retired one is gone; T02 never sees T01's tool.

**C6 · Gap questions to measure it** (`harness/practice.py` TYPES + oracle):
- 4 question types that none of the 27 tools answers: on-time % by weekday, month-on-month orders per town, the busiest receiving hour per site, and hired-truck late arrivals by vendor and week. Each has RT, TE and EN text and a Python oracle (evaluation-only, never shown to the agent);
- they are also the start of the planner question bank (Oct 30 optional item);
- measured per question: correct, tool calls and cost, at three points: before (no `run_query`), with `run_query`, and after promotion;
- if we want to *claim* a gain, pre-register **EXP-012** (frozen files plus hashes, ~$3 on Spark Open) before the first call. Otherwise the video says "shown working", not "measured".

### D. Nightly review: the agent reads its own logs and sends each problem to the right fix (Nov 2 AM, ~4 h)
Design: D-039. New `src/anubhav/review.py` plus a CLI (`python -m anubhav.review --company T01 --since 2026-10-30`), and a "Run nightly review" button on the Logs page. In production this runs on a schedule; in the demo a person presses the button.

**Inputs since the last review:**
- run traces;
- thumbs-down feedback and its notes;
- driver notes the agent recorded (`record_driver_note`);
- drafts the planner cancelled.

**Sorting is done by code; Muse only proposes.**

| Signal | Route | What already exists |
|---|---|---|
| Tool errors, repeated calls, step limit, "wrong tool" feedback | Loop A: `harness.loop.collect` → patch proposal → paired test → approval | Everything; the review only collects and schedules it |
| A correction or new fact (feedback note, new driver note, cancelled draft with a reason) | Loop B: a small "run digest" → `miner.mine` → **the same evidence gate** over the records plus the new notes → the reviewer | Miner, gate and store; new: the run digest and `source = review:<date>` |
| `run_query` used, or the reply says no tool could answer | Tool creation: C3 candidates → C4 checks | Built in workstream C |

- A correction that the records don't support stays "needs more evidence". The gate is not bypassed because a person said so in a chat; the reviewer can still approve it as a verified note, as today.
- Output: a short report ("what I learned from yesterday's runs"), saved under the world's `reports/` and shown on the Logs page.
- Tests: on a recorded set of runs, a repeated call goes to Loop A, a feedback note about a site becomes a lesson *candidate* (not active), and a `run_query` pair becomes a tool candidate.
- **This answers the owner's question "how far does it already learn from history?"** Today, Loop A already reads the agent's own traces and feedback, and Loop B reads the company's records. Both start from a button press, and Loop B never reads the agent's own runs. D closes those two gaps.

### E. Demo recordings and deploy (Nov 2)
- **E1 Deploy** without keys: Streamlit Community Cloud, `ANUBHAV_PUBLIC = "1"` ([[deploy]]). Walk the video flow in an incognito window.
- **E2 Recorded runs** (live, ~$2): the three session-1 failures, the review, and session 2, saved as replays so the hosted demo plays them without keys. This includes the "plan tomorrow" replay (Oct 30 optional item).

### F. Step 2: honest docs (Nov 2 PM, ~1.5 h)
- Everything in the step-2 rows of the audit above. In addition:
  - the README describes the three learning routes and the Logs page;
  - the tool-creation limits are stated: read-only, SQL only, company-private, human approval required;
  - "shown working" vs "measured" is stated for C and D.

### G. Video and submission (Nov 3 – Nov 4)
- Rewrite [[demo_video]] around the session 1 → review → session 2 story, with EXP-011 numbers for the proof and the Logs page as the visual thread.
- Record with English subtitles.
- README: hero GIF, 1–2 cited stats, quotes only with the interviewee's permission, demo and video links.
- Dry-run the submission and check commit authorship (Nov 3). Submit on Nov 4 IST.

## 4. Schedule

| Day (IST) | Work | Hours |
|---|---|---|
| Thu Oct 30 (tonight) | P0 commit step 1 · docs (this plan, trackers) | 0.5 |
| Fri Oct 31 | A1, A2 · B Logs page · H onboarding (slim) · E1 deploy (owner) · I1 README honesty · I2 models on screen | 8 |
| Sat Nov 1 | (I3, I4 if not done) · C1 sandbox + C2 `run_query` · C3 capture · C4 promotion + Tools tab · C5 broker · C6 gap questions · (EXP-012 pre-register + run, optional) | 8 |
| Sun Nov 2 | J1 EXP-011R + J2 EXP-012 (pre-registered) · D nightly review (slim) · E2 recorded runs · I5 if time | 8 |
| Mon Nov 3 | G video script, recording, subtitles · README GIF · submission dry run | 8 |
| Tue Nov 4 | Buffer · final checks · **submit** | — |

## 5. Cut order (if a day slips)
1. I5 spreadsheet import.
1. EXP-012 (C6 stays as practice questions; claims become "shown working").
2. Muse naming in C4: code names the tool from the request words, and the person edits it.
3. D shrinks to a button that runs Loop A and tool candidates; the Loop B run digest is cut.
4. W4 next-step hints.

**Never cut:** the commit of step 1, the Logs page, the deploy, the video day, or the C1 sandbox checks (no query tool without them).

## 6. Risks added by this plan
- **R-24 model-written code:** a query escapes its limits, reads other data or hangs the app. *Mitigation:* SQL only; in-memory copy of the company's own tables; authorizer plus query_only; time, row and length caps; tests for each. No Python execution.
- **R-25 scope vs video:** new features eat video day. *Mitigation:* the cut order above; Nov 3 is reserved for the video.
- **R-26 claims without evidence:** "learns new tools" or "learns from its runs" said as measured when they're only shown. *Mitigation:* EXP-012 or "shown working" wording; D-038 already separates the measured commits.
- **R-27 the query tool changes measured behaviour:** the agent reaches for SQL instead of the proper tools. *Mitigation:* off in frozen configs; the description says to use other tools first; Loop A already flags "wrong tool"; the Logs page shows it.

## 7. What we will and won't claim
- **Measured (EXP-011, frozen commit):** lessons beat raw-note search, 35% → 90%; pack transfer to a new company, 33% → 100%; 0 unsafe drafts, 0 leaks.
- **Shown working (unless EXP-012 runs):** the nightly review sends each problem to the right fix; a query becomes an approved tool, and the next request uses it in one call.
- **Not claimed:** other industries (a slide, as future work); executing actions (drafts only); autonomous changes (every lesson, patch and tool needs a person).
