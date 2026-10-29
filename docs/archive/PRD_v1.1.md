# PRD v1.1: Telugu-First Self-Improving Business Agent

**Meta Muse · LangGraph · BigTool · MCP · Verified Harness Improvement**

| | |
|---|---|
| Version | 1.1 (supersedes `Telugu_First_Self_Evolving_Agent_PRD_v1.docx`) |
| Date | 27 Oct 2026 |
| Owner | Solo indie developer |
| Track / theme | Indie Developer track · **Push the Frontier** (changed in v1.1.1; see §0.1) |
| Deadline | **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 7:30 AM IST**. Internal target: submit Nov 4 IST |
| Capacity | 8 build days × 8–10 hrs (~70 hrs, video included) + 1 buffer day |
| Status | Build-ready |

---

## 0. Changes from v1.0

| # | Change | Reason |
|---|---|---|
| 1 | ~~Theme is now **Build for Your World** only~~ **Superseded by §0.1: Push the Frontier** | One theme, one story. |
| 2 | Renamed from "Self-*Evolving*" to "Self-*Improving*" | A human approves every patch to metadata and guidance, so "self-evolving" overclaims and invites judge skepticism. |
| 3 | **Voice-note input** moved from non-goal to P0, *gated on the day-1 Telugu transcription test* | Adds a second Meta model (Muse Voice Transcribe), matches how orders actually arrive, and gives the video its opening hook. |
| 4 | **Muse is now the named failure diagnostician and patch proposer**, separate from its agent role | v1.0 left the proposer unspecified. A second Muse role directly targets the rubric's "Use of Meta AI Tooling" (25%). |
| 5 | New **self-verification by paraphrase**: Muse writes new Telugu and Roman-Telugu paraphrases to test whether its own patch generalizes. The verifier scores them deterministically. | Our candidate for the rubric's "surprised even us". |
| 6 | **Hosted live demo** added (P0) | The judges use "code and live product" and ask whether the demo "holds up live". |
| 7 | **Open-weights arm** (Muse Spark Open via Baseten or Modal) added as P1, conditional on partner credits | Makes the project eligible for the $10K Best Build on Open Weights bonus. |
| 8 | Cut order changed: drop the ablation and dashboard polish **before** dropping tools | Cutting tools first would make the BigTool retrieval comparison meaningless. |
| 9 | BigTool's expected win reframed as **tokens, cost and latency**. Accuracy is reported honestly either way. | Muse may handle 40 tool schemas directly, so a no-accuracy-gain result is pre-registered as acceptable. |
| 10 | Benchmark set at **48 tasks (32 dev / 16 held-out)**, each held-out task run 3 times with the spread reported | A single run on a small held-out set can produce noise that looks like uplift. |
| 11 | Arm D (ablation) and the non-Meta comparison dropped | Not visible in the video, and not worth the time. |
| 12 | Impact rests on cited public statistics, a measured manual-vs-agent time comparison, safety counters, and the developer's own Telugu voice notes. **No real customer data and no invented testimonials.** | No wholesaler access, and pursuing consent is not worth the time. |
| 13 | Added a credit budget, a bonus-prize plan, a submission compliance checklist and a revised video storyboard | Gaps in v1.0. |

### 0.1 Changes in v1.1.1 (27 Oct 2026, after Day-1 smoke tests)

| # | Change | Reason |
|---|---|---|
| 14 | **Headline set** (see §1). The product is the *capability*: an agent that gets measurably better at discovering and using tools through verified experience. | Owner decision. Puts the BigTool and Harness² ideas at the centre. |
| 15 | Theme switched to **Push the Frontier** | "Give a machine a new capability… in software" matches a self-improving tool-using agent. The Telugu business is the real-world proof case. |
| 16 | **Proof-case domain: FMCG/kirana wholesale distributor** (Andhra Pradesh, fictional data) | Clearest demo for a solo developer; already built; no perception risk. Other domains are named as future adoption targets (§1.1). |
| 17 | **Retrieval recall@k becomes a headline metric**, alongside task success | "Finding" tools is in the headline, so the arm B → C recall uplift must be measured and shown. |
| 18 | Model frozen to `muse-spark-1.3` (standard mode) | Day-1 smoke tests passed; the full benchmark costs < $10. |

---

## 1. Executive summary

> **Headline:** A Meta Muse-powered, Telugu-first agent that gets measurably better at discovering and using business tools through verified experience, without retraining the model.
>
> **Subline:** Proven on the order desk of a Telugu-speaking wholesale distributor, where voice-note orders become verified draft quotes. Every self-correction is tested on unseen tasks and approved by a human.
>
> **Video tagline:** *"Same frozen model. Smarter harness."*

**Theme: Push the Frontier.** The new machine capability is safe, verifiable self-improvement of tool discovery and tool use, in a low-resource language, with no weight updates. Inspirations: [langgraph-bigtool](https://github.com/langchain-ai/langgraph-bigtool) for scalable tool retrieval, and [Harness²](https://github.com/google-research/harness2) for improving the harness rather than the model (methodology only).

### 1.1 Proof case and adoption path
- **Proof case (built and demoed):** a wholesale FMCG/kirana distributor in Andhra Pradesh. Retailers' orders arrive as Telugu, Roman-Telugu or mixed voice notes and messages, and the agent turns them into verified draft quotes.
- **Adoption targets (narrative only, not built):**
  - pharma distribution to chemist shops (batch, expiry, licence checks)
  - agri-input dealers
  - dairy cooperatives (fat/SNF-based payouts)
  - auto spare-parts counters (huge, confusable part catalogs)
  - other Indian languages

  In each case, only the tool registry and the language guidance change. The improvement loop is the same.

### 1.2 Proof-case scenario
A Telugu-speaking wholesale order-desk operator receives informal orders as voice notes and chat messages that mix Telugu script, Roman Telugu and English product terms. Today these are converted to quotes by hand, from memory and spreadsheets. English-only ERP software doesn't understand them.

We build an agent that turns such a request into a **verified, editable draft quotation**:
1. Muse Voice Transcribe converts the voice note to text.
2. Muse Spark interprets the request and calls business tools through MCP.
3. BigTool retrieves the relevant tools from a 40-tool registry.
4. Pricing is computed deterministically and checked by an independent verifier.
5. Draft-only boundaries are enforced throughout: the agent never confirms orders, dispatches goods or sends messages.

When the agent fails, a separate **improvement loop** handles it:
1. Muse diagnoses the failure trace.
2. It proposes a bounded patch to the *harness* (tool metadata, language aliases, workflow guidance), never to its own weights.
3. It writes new paraphrases to test whether the patch generalizes.
4. The candidate runs on reset sandbox data against regression and held-out sets.
5. A human approves or rejects it. Every version is immutable and can be rolled back.

**Central claim we test honestly:** the *same frozen Muse model* completes multilingual business tasks more reliably after verified improvements to its operating harness, without fine-tuning.

**One-line pitch:** *"The model never changed. The harness got smarter, and a human signed off on every change."*

---

## 2. Source alignment

| Source | Requirement | How we meet it |
|---|---|---|
| Guide §1: Problem statements | Build toward one theme; must use Meta models | Push the Frontier ("give a machine a new capability… in software"). Muse Spark (agent and diagnostician) + Muse Voice Transcribe; Muse Spark Open optional |
| Guide §4: Rules | Public repo, max 4 per team (solo OK), new work only, original contributions clearly identified, no unlicensed code, data or assets | Repo starts Oct 27 with daily commits. README separates "built during hackathon" from "libraries used". All data fictional. |
| Guide §4: Anti-projects | Avoid basic RAG, medical advice, education chatbots, etc. | Multi-step agentic business workflow with tool execution and verification; not RAG |
| Guide §7: Submission | Due Nov 4 9 PM ET; public repo; accessible 3-min video; all contributors listed | Day-8 dry run in an incognito browser |
| Guide §8: Judging | Stage 1 pass/fail (theme + Meta use). Stage 2: Impact 30 / Meta tooling 25 / Tech 20 / Demo 25. Stage 3: top 5 per track, video watched live. | See §3, rubric strategy |
| Landing page: Indie track | Judged on "creativity, technical ambition, and whether it works" | The live path, verified results and the self-verification feature |
| Guide §5: Credits | $150 Meta Model API (received) | Budget in §12 |
| Guide §6: Partners | Baseten / Modal $100 each, selective (pending). Baseten model id: `meta-models/muse-spark-open-1026` | Open-weights arm is conditional (FR-13) |
| Schedule | Oct 28 12 PM ET (9:30 PM IST): "Agents 102: Best Practices for Verifiable Agents"; office hours 10–11 AM ET on weekdays | Attend; feed learnings into the verifier design |
| Discord clarification (user-reported, not in the official docs) | AI coding assistants and non-Meta models are allowed; Meta must play a real runtime role | Treat as unverified; our design complies either way |

---

## 3. Rubric strategy

About 70% of the scoring outcome depends on the **video**: with thousands of entries, Stage 3 judges watch it live. Every major feature must earn a visible moment in it.

| Criterion | What judges ask | Our answer, visible on screen |
|---|---|---|
| **Impact 30%** | Who benefits? How much does it matter? Could people use it? | The operator persona; cited scale (≈81M Telugu speakers, Census 2011; MSME figures to be verified and cited); **measured** manual vs. agent time per quote; zero unsafe actions; a hosted link anyone can try; the method generalizes to other low-resource languages and domains |
| **Meta tooling 25%** | Beyond basic integration? Surprising capabilities? | Three distinct Muse roles: agent, transcriber, diagnostician and patch proposer. Code-mixed Telugu tool calling with negation. Muse checking its own patch with new paraphrases. Optional open-weights run. |
| **Tech 20%** | Sound, thought-through engineering? | MCP tool contracts with tests, deterministic verifier, immutable harness versions, sandbox probes, rollback, repeated held-out runs |
| **Demo 25%** | Working? Impressive? Holds up live? Cool to watch? | Voice-note hook, live end-to-end run, a real failure fixed on screen, a before/after chart, subtitles throughout, hosted demo link |

**Bonus targets:**
- **Best Agentic Use-Case ($5K):** comes with the core build.
- **Best Open Weights ($10K):** only if partner credits arrive.
- **Most Viral ($20K) and Community Vote ($10K):** build-in-public posts on X from day 3, plus a Telugu clip with English subtitles.

---

## 4. Goals and non-goals

### 4.1 Goals
1. End-to-end verified draft quotation from a voice or text request in English, Telugu script, Roman Telugu or a mix, with Muse as the reasoning and tool-calling engine.
2. Tool discovery and execution over a 40-tool registry with semantically similar capabilities.
3. Exact traces and independently verified business outcomes for every run.
4. At least one genuine, reproducible harness improvement, validated on held-out tasks with a human approval gate.
5. A 3-minute video and a hosted demo that a judge can try.

### 4.2 Non-goals
- No production WhatsApp integration, and no WhatsApp branding in the UI.
- No payments, invoices or dispatch.
- No real customer data.
- No autonomous code rewriting and no unsupervised promotion of patches.
- No weight training.
- No ERP integration.
- No image or handwritten-slip input.
- No ablation arm (D) and no non-Meta model comparison.
- No guaranteed cross-domain generalization.

---

## 5. Persona and workflows

| Persona | Job to be done | Success signal |
|---|---|---|
| **Primary: wholesale order-desk operator** (Telugu-speaking, works over chat and voice) | Turn informal retailer requests into accurate draft quotes that respect stock, discounts and customer rules | Correct draft, fewer manual lookups, no unapproved commitments |
| **Secondary: developer / evaluator** | See why the agent failed, then test and approve a targeted harness fix | Reproducible before/after results with no unacceptable regressions |

### 5.1 Golden path
Input (voice note or text):

> "Ravi Traders ki 12 cartons quote cheyyi. Stock 8 unte migatha 4 next delivery ki note cheyyi. Customer discount eligible aithe apply cheyyi. Order confirm cheyyaku."

*(Roughly: "Quote 12 cartons for Ravi Traders. If only 8 are in stock, note the remaining 4 for the next delivery. Apply the customer discount if eligible. Don't confirm the order.")*

1. If the input is a voice note, transcribe it with Muse Voice Transcribe and show the transcript.
2. Resolve the customer, the exact SKU and the carton pack size. If the product is ambiguous, ask for clarification instead of guessing.
3. BigTool retrieves the customer-terms, inventory, pricing and discount tools.
4. Compute the quote deterministically from catalog units, flag the shortfall, and add a follow-up note.
5. Create an editable **draft** quote. Never confirm, dispatch or send anything.
6. Show sourced line items, the trace, assumptions, open clarifications and the verifier's verdict.

### 5.2 Alternate flows
| Situation | Expected behavior |
|---|---|
| Ambiguous product or unit | Ask an explicit clarifying question; never silently pick a SKU |
| Insufficient stock | Show the shortage and allowed substitutes; never reserve stock |
| Customer not eligible for discount | Show the verified undiscounted quote with an explanation |
| Needed tool missing from retrieval | Retrieve again (1–2 expansions), otherwise fail safely; log the retrieval miss |
| Timeout or malformed tool data | Bounded retry if the call is idempotent; otherwise show an actionable error |
| Negation ("vaddu" = "don't want/no", "cheyyaku" = "don't do it") | Honor it; the backend independently blocks unsafe write intents |
| Poor or unintelligible transcript | Show the transcript, flag low confidence, ask the operator to confirm before acting |

---

## 6. Functional requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---|---|
| FR-01 | English, Telugu script, Roman Telugu and mixed text inputs | P0 | Demonstrated examples in all four styles |
| FR-02 | Muse-powered LangGraph agent with bounded tool calls | P0 | Correct decision trace; configurable step and budget caps |
| FR-03 | MCP tool server over a deterministic SQLite business simulator | P0 | 12 core tool contracts pass tests |
| FR-04 | Draft quotation with an approval boundary | P0 | Accurate totals; no confirm or dispatch capability on the MVP path |
| FR-05 | Every run traceable and replayable | P0 | Prompt and config versions, tool choices, arguments and final state recorded |
| FR-06 | Independent task and policy verifier | P0 | Checks the tool trace and final DB state; no LLM self-rating |
| FR-07 | Human-approved harness improvement workflow | P0 | Propose → probe → regress → approve/reject → activate → rollback |
| FR-08 | BigTool retrieval behind a switch | P0 | Direct and retrieved modes run on identical requests |
| FR-09 | 40-tool registry, every tool real and tested | P0 (fallback: 25) | Each tool passes a schema check and a golden test |
| FR-10 | Three-view UI: Workbench, Improvement Lab, Benchmarks | P0 | All three views work, both on the hosted demo and locally |
| **FR-11** | **Voice-note input via Muse Voice Transcribe** | P0, gated on day-1 test | Telugu and code-mixed voice notes transcribe well enough to drive the golden path |
| **FR-12** | **Muse diagnostician and patch proposer** (separate role and prompt) | P0 | Produces a root-cause class and a scoped patch to one surface |
| **FR-13** | **Self-verification by paraphrase**: Muse writes N new paraphrases of the failed task, and the deterministic verifier scores them | P1 | Generated probes are stored, shown in the Improvement Lab, and kept separate from the locked held-out set |
| **FR-14** | **Hosted demo** with a live mode (spend-capped) and a replay mode | P0 | A public link works from an incognito browser |
| **FR-15** | **Open-weights arm** (Muse Spark Open via Baseten or Modal) | P1, conditional on credits | Same benchmark runs through a model-adapter switch |
| FR-16 | Measured manual-vs-agent timing study (self-timed, labeled as such) | P0 | 5 quotes timed each way, and the numbers shown |

---

## 7. Business domain and the 40-tool registry

8 groups × 5 tools = 40. The 12 core tools are marked with \*. A tool counts as implemented only when it does real validated work against the simulator and passes its contract test. All tools are generated from one shared contract template.

| Group | Tools |
|---|---|
| Customers | `find_customer`\* · `get_customer_profile`\* · `get_customer_terms` · `get_customer_order_history` · `check_customer_status` |
| Catalog | `search_products`\* · `get_sku_details`\* · `resolve_product_alias` · `get_pack_conversion`\* · `find_product_substitutes` |
| Inventory | `check_stock`\* · `get_warehouse_stock` · `get_available_to_promise` · `get_restock_eta` · `get_stock_shortfall` |
| Pricing | `get_standard_price`\* · `get_customer_price`\* · `get_bulk_price` · `get_discount_eligibility`\* · `get_tax_rules` |
| Quotations | `create_draft_quote`\* · `get_draft_quote`\* · `revise_draft_quote` · `compare_quote_options` · `validate_quote`\* |
| Orders | `find_order` · `get_order_status` · `get_order_lines` · `create_draft_order` · `validate_order_draft` |
| Fulfillment | `get_delivery_slots` · `estimate_delivery_date` · `get_supplier_eta` · `check_allocatable_stock` · `get_fulfillment_policy` |
| Policies & analytics | `get_business_policy` · `get_credit_policy` · `get_returns_policy` · `get_customer_outstanding` · `summarize_quote` |

**Tool contract.** Each tool definition includes:
- tool_id, purpose, domain
- read/write class
- JSON schema
- examples and counterexamples in English, Telugu and Roman Telugu
- preconditions and authorization class
- idempotency and error schema
- fixture and contract test

**Rules for all tools:**
- The LLM never computes monetary totals.
- Writes are draft-only, reversible and sandboxed.

---

## 8. Architecture

```
Voice note ─► Muse Voice Transcribe ─┐
Text ───────────────────────────────►├─► LangGraph agent (Muse Spark)
                                     │      interpret → discover → call → observe → clarify/finish
                                     │            │
                                     │      BigTool retriever (top-k over registry metadata)
                                     │            │
                                     │      MCP tool server (FastMCP) ─► SQLite business simulator
                                     │
Trace recorder (every model/tool event) ─► Deterministic verifier (expected vs. actual state)
                                     │
Improvement controller: Muse diagnostician → scoped patch → Muse paraphrase probes
   → sandbox probe on reset snapshots → regression + held-out gate → human approve → versioned activate/rollback
                                     │
Streamlit UI: Workbench · Improvement Lab · Benchmarks   (hosted: Hugging Face Space, live + replay)
```

### 8.1 Components
| Component | Responsibilities |
|---|---|
| Model adapter | Muse API calls (and an optional Muse Spark Open endpoint), structured tool calls, retry limits, token and cost accounting, model-version recording, **mock mode** for tests and UI work |
| Transcriber | Muse Voice Transcribe call, transcript and confidence capture, fallback to manual confirmation |
| LangGraph agent | Bounded graph with checkpoints |
| BigTool adapter | `langgraph-bigtool` retrieval; configurable top-k; records candidate IDs and scores |
| MCP server | FastMCP with typed schemas and deterministic, fixture-backed implementations; connected via `langchain-mcp-adapters` |
| Business simulator | SQLite: catalog, customers, inventory, pricing, quotes; snapshot and reset per scenario |
| Trace and verifier | Event-level provenance; expected-vs-actual checks on state and forbidden actions |
| Harness manager | Immutable versions, candidate diffs, sandbox evaluation, approval, activation, rollback |
| Diagnostician / proposer | Muse role: classify the root cause, emit a scoped patch, generate paraphrase probes |
| UI | Workbench, Improvement Lab, Benchmarks |

### 8.2 Execution limits
Per run, all configurable from the environment:
- ≤ 8 model turns
- ≤ 12 tool calls
- 1–2 retrieval expansions
- a per-run token and cost ceiling

Safety rules:
- The backend enforces authorization, not the model or the retriever.
- Tool outputs and customer text are treated as untrusted.
- API keys are masked in traces.
- The hosted live mode has a global spend cap and a rate limit.

---

## 9. Harness improvement design

### 9.1 What may be patched
- **Allowed surfaces:**
  1. Tool registry metadata: descriptions, retrieval tags, examples, disambiguation hints.
  2. Language guidance: Roman-Telugu and Telugu aliases, negation and quantity rules.
  3. Workflow guidance: preconditions, dependency hints, clarification rules.
- **Disallowed:**
  - permission logic
  - expected test outputs
  - production data
  - arbitrary code
  - model weights
  - self-approval

### 9.2 Candidate lifecycle
1. **Observe and classify** the failure: retrieval miss, wrong tool, wrong arguments, multilingual misreading, sequencing, data issue, or policy attempt.
2. **Propose:** Muse produces a patch against *one* versioned surface.
3. **Self-verify (FR-13):** Muse writes N new paraphrases of the failed request. These are generated probes and are never added to the locked held-out set.
4. **Probe:** run baseline and candidate on identical reset DB snapshots over:
   - the targeted cases
   - the paraphrase probes
   - previously passing regression cases
   - the locked held-out gate (expected answers are never shown to the proposer)
5. **Review:** a human sees the diff, the task-by-task results, the cost and latency changes, and any regressions, then approves or rejects.
6. **Activate** one immutable version, with one-click rollback.

### 9.3 Promotion policy (fixed before final evaluation)
- The targeted failure must be fixed.
- Zero critical safety failures.
- No newly failing high-priority regressions.
- No meaningful drop in held-out success.
- Cost and latency changes are shown.
- If the result is inconclusive, reject.
- Human approval is required even when every test passes.

---

## 10. Data

| Entity | Key fields |
|---|---|
| Customer | id, name, aliases, active, tier, terms, credit_status |
| Product | sku, name, brand, aliases (EN / Telugu / Roman Telugu), category, base_unit, units_per_case |
| Inventory | sku, warehouse_id, on_hand, reserved, available |
| PriceRule | sku, tier, min_quantity, unit_price, discount_rule, effective_dates |
| Quote / QuoteLine | draft status, harness_version, source_request; line totals, discount, shortage_note |
| ExecutionTrace | run_id, task_id, model_version, harness_id, transcript, retrievals, tool_calls, outcome |
| Correction | id, failure_id, surface, patch, proposed_by, paraphrase_probes, approval, tests, promoted_version |
| EvalCase | id, language, input_mode (text/voice), prompt, fixture_id, expected_state, forbidden_actions, split |

**Seed data:**
- 40 SKUs and 15 customers, all with **fictional** names, brands and prices. No real logos or trademarks.
- Voice notes are recorded by the developer only.
- Telugu phrasing is written from the developer's own knowledge of how such orders read.

---

## 11. Evaluation

| Arm | Configuration | Question |
|---|---|---|
| A | Muse + all 40 tools exposed directly (if the API allows that many schemas) | Does direct exposure work at this size? |
| B | Muse + BigTool, baseline harness | Does retrieval reduce tokens, cost and latency? What is its accuracy effect? |
| C | Muse + BigTool + approved improved harness | Do verified harness fixes improve **unseen** tasks? |
| OW (P1) | Muse Spark Open + BigTool, B vs. C | Does the improvement carry over to open weights? |

**Benchmark: 48 tasks.**
- By language: 8 English, 12 Telugu script, 16 Roman Telugu, 12 mixed.
- About 8 voice-input variants.
- Split: 32 dev, **16 locked held-out**.
- Coverage: SKU disambiguation, units and packs, negation, discounts, stock shortages, dependencies, missing tools, transient errors.

**Metrics:**
- **Primary:** end-to-end verified task success.
- **Retrieval:** recall@k and precision.
- **Tool calls:** validity (correct tool, arguments and authorization).
- **Safety:** forbidden actions attempted and executed (executed must be 0).
- **Regressions** introduced by each patch.
- **Efficiency:** tokens, cost, latency, turns and tool calls per success.
- **Manual-vs-agent time per quote** (self-timed, labeled).

**Rigor:**
- Frozen model IDs and settings, temperature 0 where supported.
- Identical fixture resets.
- Held-out tasks run **3 times**; report the mean and the spread.
- Log failed and inconclusive runs.
- Never fabricate uplift. A null result is reported as a null result.

---

## 12. Budget (Meta Model API, $150)

To be filled on day 1 once Muse pricing is confirmed.

| Item | Estimate |
|---|---|
| Development and debugging runs | TBD (target ≤ 25%) |
| Benchmark: 48 tasks × arms A/B/C, plus 16 held-out × 3 repeats × 2 arms | TBD (target ≤ 40%) |
| Improvement loop (diagnosis, paraphrases, probes) | TBD (target ≤ 15%) |
| Hosted live mode (hard-capped) | TBD (target ≤ 10%) |
| Reserve | ≥ 10% |

**Controls:**
- Mock mode for all unit and UI work.
- Per-run caps.
- A spend-limit notification on the Meta billing page.
- A cost ledger written from traces.

---

## 13. UX and demo

| View | Must show |
|---|---|
| **Agent Workbench** | Chat-style input (text, or upload/record a voice note) → transcript → interpreted entities → retrieved tools → live tool sequence → draft quote → verifier verdict |
| **Improvement Lab** | Failure trace → root-cause class → Muse's patch diff → paraphrase probes → probe and regression results → Approve/Reject → version history with rollback |
| **Benchmarks** | Arms A/B/C (+OW) by language; success, retrieval, safety, regressions, cost and latency; spread over repeats; drill-down into any task's trace |

### 13.1 Video storyboard (≤ 3:00)
| Time | Beat |
|---|---|
| 0:00–0:15 | **Hook:** a Telugu voice-note order plays with subtitles. "Millions of orders sound like this. No business software understands them." |
| 0:15–0:50 | **Live run:** voice → transcript → tools fire → verified draft quote. The shortfall is flagged and "cheyyaku" ("don't do it") is honored. |
| 0:50–1:25 | **Real failure:** a harder request fails, and the trace shows exactly why. |
| 1:25–2:05 | **Fix:** Muse diagnoses, patches, writes its own paraphrase tests; the sandbox and regression checks pass; a human approves. |
| 2:05–2:35 | **Proof:** before vs. after on held-out tasks with spread, cost and latency. "Same frozen model. Smarter harness." |
| 2:35–3:00 | **Impact:** measured time saved, zero unsafe actions, applicability to other low-resource languages, the Meta stack used, hosted link. |

Any replayed segment is labeled as replay. At least one path in the video is live. Subtitles run throughout. Latency is cut, not faked.

---

## 14. Non-functional requirements
- **Reproducibility:** one setup command, seeded fixtures, local deterministic verifier, pinned dependencies, CLI benchmark runner, stored replay artifacts.
- **Security:** API keys only in the environment; `.env` is gitignored; no unrestricted code execution; authorization enforced in the backend; spend caps on the hosted demo.
- **Reliability:** idempotent draft writes, bounded retries, clear errors, DB reset per test.
- **Observability:** every model and tool call tagged with run_id, task_id, model and harness version, and timestamps.
- **Performance:** golden path under 45 s when provider latency allows; actual latency is shown.
- **Accessibility:** Telugu Unicode rendering, readable tables, clear status indicators.

---

## 15. Release plan (IST; 8–10 hrs/day)

| Day | Date | Deliverable | Go / no-go gate |
|---|---|---|---|
| 1 | Oct 27 | Muse smoke test: tool calls, Roman Telugu, **voice test**, pricing, schema-count limit. Repo, fictional SQLite seed, model adapter with mock mode. Budget filled in. | A Roman Telugu prompt returns a valid tool call; voice decision made |
| 2 | Oct 28 | MCP server, 12 core tools, contract tests, deterministic pricing. Attend Agents 102 (9:30 PM IST). | Golden quote correct without the LLM |
| 3 | Oct 29 | LangGraph agent, trace recorder, verifier, safety guard | **Hard checkpoint:** golden path runs live end to end |
| 4 | Oct 30 | Expand to 40 tools, add BigTool, voice input path. Start build-in-public posts. | Arms A and B run on the same scenario |
| 5 | Oct 31 | 48-task benchmark, baseline runs, failure classifier | Baseline logged; real failures catalogued |
| 6 | Nov 1 | Improvement loop: diagnose → patch → paraphrase probes → regression → approve/rollback | One real candidate probed and decided |
| 7 | Nov 2 | 3-view UI, final held-out runs ×3, hosted demo, README, timing study. **Feature freeze at night.** | Fresh install and hosted link both work |
| 8 | Nov 3 | Video script, recording, editing; submission dry run | Video ≤ 3:00; all links work in incognito |
| 9 | Nov 4 | Buffer, then **submit** (hard deadline Nov 5, 7:30 AM IST) | Submitted |

**Cut order if behind** (first cut first):
1. Open-weights arm
2. Paraphrase probes (FR-13)
3. Dashboard polish
4. Tools from 40 → 25
5. Arm A
6. Voice input

**Never cut:** the live quote path, honest traces, the independent verifier, at least one improvement decision, video day.

---

## 16. Acceptance tests
- **AT-01:** A Roman Telugu + English request with a clear SKU and customer produces a correct draft quote with deterministic totals.
- **AT-02:** A Telugu-script request exercises at least two distinct MCP tools correctly.
- **AT-03:** An ambiguous product name triggers a clarifying question instead of a guessed quote.
- **AT-04:** "order confirm cheyyaku" (don't confirm the order) never results in a committed order, and any forbidden intent attempt is visible in the trace.
- **AT-05:** A retrieval miss is recorded with the needed tools versus the returned tools.
- **AT-06:** A correction is stored as a versioned diff and cannot promote itself.
- **AT-07:** A sandbox probe compares baseline and candidate on identical fixture snapshots.
- **AT-08:** Regression results can reject a candidate, and an approved version can be rolled back.
- **AT-09:** Baseline and improved runs use the same frozen Muse model and settings.
- **AT-10:** A fresh install with no secrets committed runs the local tests and replays the stored evaluation evidence.
- **AT-11:** A Telugu voice note drives the golden path end to end, with the transcript shown (if FR-11 is enabled).
- **AT-12:** Paraphrase probes are generated, scored by the verifier, and never leak into the held-out set (if FR-13 is enabled).
- **AT-13:** The hosted demo link works in an incognito browser and its spend cap is enforced.

---

## 17. Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Muse tool-calling or Telugu behavior differs from expectations | High | Day-1 smoke test first; adapter abstraction; mock mode |
| Telugu transcription quality is poor | Medium | Gated on the day-1 test; fall back to typed Roman Telugu and show low-confidence warnings |
| BigTool shows no accuracy gain | Medium | Pre-registered efficiency framing; honest reporting |
| No meaningful improvement on held-out tasks | High | Show honest diagnosis plus a transparent rejection; the agent still works |
| Benchmark leakage or overfitting | High | Locked held-out set, paraphrases kept separate, DB resets, proposer never sees expected answers |
| 40 tools dilute quality | Medium | Template-generated, contract-gated; fallback to 25 |
| Credits run out | Medium | Budget ledger, caps, mock mode, reserve |
| Hosted demo abused or overspends | Medium | Global spend cap, rate limit, replay mode as default |
| Demo can't be reproduced | High | Seeded data, stored replay artifacts, day-7 freeze |
| Rules or originality challenge | High | Daily commits from Oct 27; README provenance section; fictional assets only |
| Solo-developer fatigue | Medium | Day-3 checkpoint, fixed cut order, buffer day |

---

## 18. Success criteria and decisions

**P0 success:**
- One live, reproducible multilingual quotation path.
- 12 or more reliable tools, plus BigTool retrieval working.
- Trace and deterministic verifier working.
- At least one real harness candidate probed, with a human decision.
- Correctly labeled before/after results.
- Hosted demo up.
- Complete submission.

**P1 stretch:**
- Full set of 40 tools.
- Voice input.
- Paraphrase self-verification.
- Several distinct improvements.
- Open-weights arm.

**Decision log (v1.1):**
- Push the Frontier; headline as in §1. (v1.1 said Build for Your World; superseded.)
- Proof case: FMCG/kirana wholesale distributor; other domains are future adoption targets.
- Single domain.
- Draft-only transactions.
- Muse handles three runtime roles: agent, transcriber, diagnostician.
- BigTool for retrieval.
- Harness²-inspired bounded correction (methodology only, not a dependency).
- Synthetic data, solo developer, public repo.
- Docs kept in Markdown.

**Revisit only for measured blockers.**

---

## 19. References
- Hackathon docs (in `Hackathon_info/`):
  - Participant guide (11 pp.)
  - Event page (6 pp.)
  - Meta API credit form
  - Baseten and Modal credit forms
- https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details
- https://github.com/langchain-ai/langgraph-bigtool
- https://github.com/google-research/harness2 (methodological inspiration only)
- Previous version: `docs/Telugu_First_Self_Evolving_Agent_PRD_v1.docx`
