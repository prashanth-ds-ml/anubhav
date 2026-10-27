# Day-wise plan: Days 1–3 in detail, key dates for the whole event

Companion to `docs/PRD_v1.1.md`. Today is **Tue 27 Oct 2026 (Day 1)**.

## Key dates and times (from the participant guide, converted to IST)

> **Time-zone note:** US daylight saving time ends **Sun Nov 1, 2026**, so the gap between ET and IST changes during the event.
> - Until Oct 31, ET = EDT (UTC−4), and **IST = ET + 9:30**.
> - From Nov 1, ET = EST (UTC−5), and **IST = ET + 10:30**.

| Event (per guide) | ET | **IST** | Relevance to us |
|---|---|---|---|
| Kickoff | Mon Oct 26, 12:00 PM | Mon Oct 26, 9:30 PM | Done |
| **Agents 101: Build a Multimodal AI Agent** (Suraj Subramanian) | **Tue Oct 27, 12:00–1:00 PM** | **Tue Oct 27, 9:30–10:30 PM (tonight)** | Voice input, multimodal Muse usage |
| **Agents 102: Best Practices for Verifiable Agents** (Yash Khare) | **Wed Oct 28, 12:00–1:00 PM** | **Wed Oct 28, 9:30–10:30 PM** | Our verifier and improvement loop. High priority |
| Building Specialized Intelligence on Fireworks: Inference to Training with Muse Open Models (Sinan Ozdemir) | Fri Oct 30, 12:00–1:00 PM | Fri Oct 30, 9:30–10:30 PM | Only matters if we build the open-weights arm |
| Discord office hours (#office-hours, text only, weekdays) | Daily 10:00–11:00 AM | **Oct 27–30: 7:30–8:30 PM** · **Nov 2–4: 8:30–9:30 PM** | Ask the Meta team about blockers. None on Sat Oct 31 or Sun Nov 1 |
| Last full day for submission and technical questions | Tue Nov 3 | Tue Nov 3 (ET day ends Wed Nov 4, 10:30 AM IST) | Ask anything about submission by then |
| Final office hours, **submission deadline**, Meta credit claim deadline | **Wed Nov 4, 9:00 PM** | **Thu Nov 5, 7:30 AM** | Our target: submit on Wed Nov 4 (IST) |
| Judging period | Thu Nov 5 – Sun Nov 8 | Nov 5 – Nov 9 | Keep the hosted demo running and within its spend cap |
| Closing ceremony: top 10 (5 per track), winners | Mon Nov 9, 12:00 PM | **Mon Nov 9, 10:30 PM** | Watch it live |
| Community vote winner announced | Mon Nov 16 | Mon Nov 16 | Keep promoting until then |

### Rules to follow every day
- [ ] **Commit at least once a day.** The commit history is our proof that the work was "new work only".
- [ ] **Never commit:**
  - `.env` or API keys
  - the `Hackathon_info/` PDFs (they contain your email address and form pages)
  - real data of any kind
- [ ] All brands, customers and prices are **fictional**.
- [ ] Record model cost in the cost ledger. Stop and re-plan if any day uses more than about 15% of the $150 credit.
- [ ] Write a 3-line entry in `docs/build_log.md` at the end of each day: what was built, the gate result, and the next step. This material feeds the README and the video.

---

## Day 1: Tue 27 Oct, "Prove Muse can do this"

**Gate:** Muse returns a valid tool call from a Roman-Telugu prompt, **and** the voice decision is made.

### A. Accounts and repo (~1 hr)
- [ ] dev.meta.ai: check that the $150 credit shows on the Billing page, and set a **spend-limit notification**.
- [ ] Create an API key and put it in a local `.env` (gitignored).
- [ ] Skim the Meta docs linked in the guide: Overview, Quickstart, **Model list**, API fundamentals, Muse code recipes. Note the exact model IDs for Muse Spark and Muse Voice Transcribe.
- [x] Create a **public** GitHub repo: ✅ https://github.com/prashanth-ds-ml/meta-hackathon-telugu-agent (renamed from `telugu-order-agent`), with these files in the first commit:
  - [ ] `README.md` stub that says "Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026)"
  - [ ] `.gitignore` that excludes `.env`, `Hackathon_info/`, `*.db` and venvs
  - [ ] `docs/PRD_v1.1.md` and `docs/day_plan.md`
- [ ] Set up Python 3.11 or newer, ideally with `uv` (the machine currently has 3.10). Pin dependencies: `langgraph`, `langgraph-bigtool`, `mcp` (FastMCP), `langchain-mcp-adapters`, `streamlit`, `pytest`.

### B. Muse smoke tests (~3–4 hrs): the most important work today
Put each test in `scripts/smoke/`. Record the results in `docs/day1_smoke_results.md`.

| # | Test | Pass criterion | Record |
|---|---|---|---|
| T1 | Basic chat call to Muse Spark | Response received | model ID, latency, tokens |
| T2 | Tool calling with 3 tools and a Roman-Telugu prompt ("Ravi Traders ki 12 cartons quote cheyyi") | Valid tool call with correct arguments | raw request/response JSON |
| T3 | Same request in Telugu script | Valid tool call | quality notes |
| T4 | Negation: "…order confirm cheyyaku" (don't confirm the order) with a `confirm_order` tool offered | Confirm tool **not** called | pass/fail ×3 runs |
| T5 | Tool-count limit: send 40 dummy tool schemas | Accepted or rejected → decides whether **Arm A** is feasible | max accepted, token cost |
| T6 | **Voice:** record 3 notes yourself (clean Telugu, code-mixed, noisy background) → Muse Voice Transcribe (or Spark audio input) | Transcripts usable enough to drive T2 | **Decision: voice IN or OUT** |
| T7 | Pricing per 1M input/output tokens, for each model | Known | fill in PRD §12 budget |
| T8 | Determinism controls (temperature 0, seed) | Supported or not | affects the repeat strategy |

- [ ] If T2 or T3 fails, try a stricter system prompt, then the JSON tool-call format, and **ask in #office-hours** before redesigning.

### C. Data foundation (~2 hrs)
- [ ] SQLite schema: customers, products (with English, Telugu and Roman-Telugu aliases), inventory, price rules, quotes, quote lines.
- [ ] Fictional seed data: 40 SKUs, 15 customers, a realistic carton-to-unit pack conversion for each product, and stock/discount data rigged so the golden path hits a shortfall (8 in stock, 12 ordered).
- [ ] `reset_db()` snapshot function.
- [ ] Model adapter interface with **mock mode** for all later unit and UI work.

### D. Event
- [ ] **7:30–8:30 PM IST**: Discord #office-hours. Ask whether Voice Transcribe supports Telugu and what the tool-schema limit is, if the tests didn't answer them.
- [ ] **9:30–10:30 PM IST**: Agents 101 livestream. Note anything about multimodal or audio usage.

### End of Day 1
- [ ] Gate passed? Fill in `day1_smoke_results.md`, make the voice decision, record the budget numbers, commit.

---

## Day 2: Wed 28 Oct, "Tools that are correct without any LLM"

**Gate:** the golden quote (12 cartons, 8 in stock, shortfall 4, discount applied) is computed correctly by calling the tools directly, with no LLM involved.

### A. Tool contract template (~1.5 hrs)
- [ ] One template that every tool follows:
  - tool_id, purpose, domain, read/write class
  - JSON schema
  - examples and counterexamples in English, Telugu and Roman Telugu
  - preconditions, authorization class, idempotency, error schema
- [ ] A generator or registry loader so tools 13–40 on Day 4 are cheap to add.

### B. MCP server and the 12 core tools (~4 hrs)
- [ ] FastMCP server exposing:
  - `find_customer`, `get_customer_profile`
  - `search_products`, `get_sku_details`, `get_pack_conversion`
  - `check_stock`
  - `get_standard_price`, `get_customer_price`, `get_discount_eligibility`
  - `create_draft_quote`, `get_draft_quote`, `validate_quote`
- [ ] Pricing and totals live in a **deterministic pricing module**, never in the LLM.
- [ ] Writes are draft-only. No confirm, dispatch or send tools exist on this path.

### C. Tests (~2 hrs)
- [ ] One contract test per tool (schema plus fixture result).
- [ ] Golden-path test that calls the tools in sequence → expected quote state.
- [ ] Edge tests: ambiguous SKU, ineligible discount, zero stock, invalid customer.
- [ ] Run the MCP server and list its tools from a small client script.

### C2. Early baseline prep (D-023, pulled forward from Day 5)
- [x] Business data as CSVs + SQLite, hidden shop slang, 48-task benchmark v1, pricing engine (done Day 1, see [[decisions]] D-022)
- [ ] Check whether Muse `tool_search` / `defer_loading` lets us update tool descriptions between requests
- [ ] Small Muse `tool_search` accuracy test on ~10 Telugu / Roman-Telugu queries vs. all tools loaded

### D. Event
- [ ] **7:30–8:30 PM IST**: #office-hours, if blocked.
- [ ] **9:30–10:30 PM IST: Agents 102, Verifiable Agents.** Take notes. Afterwards, update the verifier design notes in the PRD (§9, §11) with anything we should adopt. Judges from Meta will recognize their own best practices.

### End of Day 2
- [ ] All 12 tool tests and the golden-path test are green. Commit and log.

---

## Day 3: Thu 29 Oct, "Golden path live": HARD CHECKPOINT

**Gate:** a real Muse run goes from a Roman-Telugu request to a verified draft quote, end to end. AT-01, AT-03 and AT-04 pass.

### A. Agent (~3.5 hrs)
- [ ] LangGraph graph: interpret → discover → call → observe → clarify/finish, with checkpoints.
- [ ] Connect the MCP tools through `langchain-mcp-adapters`.
- [ ] Limits: ≤8 model turns, ≤12 tool calls, and a per-run token/cost cap (set via env).
- [ ] **Clarify node**: an ambiguous product or unit produces a question, never a guess.

### B. Safety, trace and verifier (~3 hrs)
- [ ] Backend safety guard: block any write intent outside draft-only, and log the attempt as `forbidden_attempt`.
- [ ] Trace recorder that writes every model and tool event to JSONL or SQLite, tagged with run_id, task_id, model_version, harness_version and timestamps. Keys are masked.
- [ ] Deterministic verifier:
  - compares the final DB state with the expected state
  - checks forbidden actions
  - checks the tool trace
  - **no LLM self-grading**
- [ ] Cost ledger built from the traces.

### C. Acceptance runs (~1.5 hrs)
- [ ] **AT-01:** Roman Telugu + English → correct draft quote.
- [ ] **AT-03:** ambiguous product → clarifying question.
- [ ] **AT-04:** "order confirm cheyyaku" → no committed order; any attempt is visible in the trace.
- [ ] Run each 3 times and note how much the results vary.
- [ ] Save one trace as the first **replay artifact**. It is our safety net for the demo.

### D. Event
- [ ] **7:30–8:30 PM IST**: #office-hours.

### End of Day 3: checkpoint decision
- [ ] **PASS:** continue to Day 4 as planned (40 tools, BigTool, voice path, first build-in-public post).
- [ ] **FAIL:** use Day 4 morning to fix it. Apply the PRD cut order: drop open weights, then paraphrase probes. **Never** cut the live quote path or the verifier.

---

## Look-ahead (details to be added on Day 3)
| Day | Date (IST) | Focus | Event (IST) |
|---|---|---|---|
| 4 | Fri Oct 30 | 40 tools, BigTool, arms A/B, voice path, first X post | Office hours 7:30 PM · Fireworks session 9:30 PM (optional) |
| 5 | Sat Oct 31 | 48-task benchmark, baseline runs, failure catalog | No office hours |
| 6 | Sun Nov 1 | Improvement loop: diagnose → patch → paraphrase probes → regression → approve/rollback | No office hours · US daylight saving ends |
| 7 | Mon Nov 2 | 3-view UI, held-out runs ×3, hosted demo, README, timing study, **feature freeze** | Office hours **8:30 PM** |
| 8 | Tue Nov 3 | Script, record and edit video, submission dry run | Office hours 8:30 PM · last full day for submission questions |
| 9 | Wed Nov 4 | Buffer, then **submit** | Final office hours **Thu Nov 5, 7:30 AM IST = hard deadline** |
