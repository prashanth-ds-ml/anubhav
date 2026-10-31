---
tags: [tracker, decisions]
---
# Decisions log

ADR-style: newest at the bottom. Never delete an entry; mark it superseded instead. Template: `templates/decision`.

| ID | Date | Decision | Status |
|---|---|---|---|
| D-001 | 2026-10-27 | Theme is **Build for Your World** only | superseded by D-018 |
| D-002 | 2026-10-27 | Rename "Self-Evolving" to **Self-Improving** | accepted |
| D-003 | 2026-10-27 | Voice-note input is P0, **gated on the Day-1 Telugu transcription test (T6)** | accepted (T6 passed 2026-10-27) |
| D-004 | 2026-10-27 | Muse plays 3 roles: agent, transcriber, diagnostician/proposer | accepted |
| D-005 | 2026-10-27 | No real user data and no testimonials; impact comes from cited stats and measured timing | accepted |
| D-006 | 2026-10-27 | Cut order: open weights → paraphrase probes → polish → tools 40→25 → arm A → voice | accepted |
| D-007 | 2026-10-27 | BigTool's expected win is tokens, cost and latency; accuracy is reported honestly | accepted |
| D-008 | 2026-10-27 | 48 tasks (32 dev / 16 held-out); held-out tasks run ×3 | accepted |
| D-009 | 2026-10-27 | Drop arm D (ablation) and non-Meta comparison | accepted |
| D-010 | 2026-10-27 | Docs are Markdown; `docs/` is the Obsidian vault | accepted |
| D-011 | 2026-10-27 | No Claude co-author or collaborator on pushes to `prashanth-ds-ml` | accepted |
| D-012 | 2026-10-27 | `Hackathon_info/` PDFs are never committed (they contain personal email and form pages) | accepted |
| D-013 | 2026-10-27 | Capacity is 8–10 hrs/day; Nov 4 IST is the buffer day | accepted |
| D-014 | 2026-10-27 | Runtime model: **`muse-spark-1.3` standard mode**, frozen for all evals. Not contributor mode | accepted |
| D-015 | 2026-10-27 | Commits use the personal email `prashanth01071995@gmail.com` (repo-local git config) | accepted |
| D-016 | 2026-10-27 | Python 3.12 with `uv`; OpenAI SDK pointed at `https://api.meta.ai/v1` | accepted |
| D-017 | 2026-10-27 | **Headline:** "A Meta Muse-powered, Telugu-first agent that gets measurably better at discovering and using business tools through verified experience, without retraining the model." | accepted |
| D-018 | 2026-10-27 | Theme: **Push the Frontier** (supersedes D-001) | accepted |
| D-019 | 2026-10-27 | Proof-case domain: **FMCG/kirana wholesale distributor** (AP, fictional data). Pharma, agri-input, dairy, spare parts and other languages are future adoption targets only | accepted |
| D-020 | 2026-10-27 | Retrieval recall@k (B → C) is a headline metric alongside task success | accepted |
| D-021 | 2026-10-27 | Repo and project name: **`meta-hackathon-telugu-agent`** (GitHub repo and Python project). Local folder stays `C:\Users\prash\projects\meta_hackathon`; it does not affect the remote, package or submission. Import package stays `order_agent` | superseded by D-025 |
| D-022 | 2026-10-27 | Business data lives in CSVs (source of truth) loaded into SQLite; shop slang is kept in `datasets/business/hidden/`, never in the DB; 48-task benchmark v1 with expected answers computed by `pricing.py` | accepted |
| D-023 | 2026-10-27 | Baseline first: run the baseline on Day 2–3, before building the improvement loop. Arms become A (all tools), B (Muse built-in `tool_search`), C (B + our approved harness patches) | accepted |
| D-024 | 2026-10-28 | Direction: **Anubhav**, an agent that learns a business's unwritten rules from its own records (evidence gate + reviewer), with private lessons and a regional domain pack for new customers. Based on EXP-005/006 | accepted |
| D-025 | 2026-10-29 | Repo renamed to **`anubhav`** (GitHub repo and Python project). Local folder stays `meta_hackathon` | accepted |
| D-026 | 2026-10-29 | Prior experiments EXP-001–006 and the `order_agent` package moved to `archive/prototype_experiments/`, layout unchanged so frozen hashes and scripts still work; new code goes in `src/anubhav/` | accepted |
| D-027 | 2026-10-29 | Design baseline: [[PRD_v3.1]] + [[Data_Benchmark_Blueprint_v1.0]], scaled to **3 history companies + 1 new test company** (instead of 5 + 1); everything else kept, built in layers with a demo-safe checkpoint on Nov 1 | accepted |
| D-028 | 2026-10-29 | **Ground rule:** every commit and push is by `prashanth-ds-ml <prashanth01071995@gmail.com>` only; no co-authors, no Claude attribution, no other GitHub account. Repo-local credential helper pins pushes to prashanth-ds-ml | accepted |
| D-029 | 2026-10-29 | Data defaults ([[Data_Spec_v1]]): 90 days (Aug 1 → Oct 29, 2026), ~2,500–3,000 orders (T01 ≈ 9/day, T02 ≈ 8/day, T03 ≈ 14/day), real towns and PIN codes with fictional businesses, notes ~50% Roman Telugu / 30% Telugu / 20% English or mixed; medium regional 3PL; delivery-window-driven planning; fleet ~30% own / 50% attached / 20% spot; public datasets used for structure only | accepted |
| D-030 | 2026-10-29 | **Generic tools over a canonical model.** The same 16 tools serve every client; each client's schema is mapped by an adapter file (`configs/adapters/*.yaml`). Onboarding = a mapping file, not code. Lessons are expressed in canonical terms, which is what lets them transfer. No raw SQL tool | accepted |
| D-031 | 2026-10-29 | Project name changed from Anubhavam to **Anubhav** everywhere (package `anubhav`, docs, configs) | accepted |
| D-032 | 2026-10-29 | MCP server per authenticated session (MCP SDK 2.x `MCPServer`): `tools/list` shows only what the role may use; company and role never come from tool arguments | accepted |
| D-033 | 2026-10-29 | Rule-related staff fixes stay local to the order (never written to the site master), matching the interview: constraints live in planners' heads | accepted |
| D-034 | 2026-10-29 | **No hard-coded knowledge.** Nothing the agent, miner, gate or tools use may contain facts, word lists or spellings written from knowledge of the generated world; use statistics computed from each company's own data, or let the agent learn it. Truth lives only in `learning/evaluate.py` (evaluation) and the generator | accepted |
| D-035 | 2026-10-29 | **Loop A built with tester feedback.** The owner tests as a native speaker; feedback (👍/👎 + category + note) is tagged `source: tester`. Language/behaviour feedback → bounded harness patches (response guidelines, per-tool hints, glossary), shared by every client, tested old-vs-new before activation. Plan feedback is evidence only, never a rule. Tester feedback is excluded from experiments; final benchmarks use a fresh seed | accepted |
| D-036 | 2026-10-29 | The agent learns to use the tools we provide: signals from its own traces (tool errors, repeats, limit hits) plus feedback drive Loop A. The paired-test gate is code (no lost drafts, no new tool errors, cost ≤ +30%, problem improved); a Muse judge of 'feedback addressed' is diagnostic; a person activates | accepted |
| D-037 | 2026-10-30 | **Tools follow the planner's questions, grouped in 7 categories.** An audit of ~35 user questions found gaps where the data existed but no tool did. Added: plan_board, check_load, create_dispatch_drafts, list_dispatch_drafts, list_drivers, trip_documents, performance, list_lessons; list_vehicles(available_on), trip_history(vehicle_id); the validator now blocks a truck on its workshop day. All generic (canonical model, any client). The model still does the planning; the tools let it see a whole day. Not built: live tracking and stop sequencing (no data). | accepted |
| D-038 | 2026-10-30 | **Judge-proof hosted demo (audit step 1).** Hosted with `ANUBHAV_PUBLIC=1`: each visitor gets their own drafts and lessons (starting from the EXP-008 lessons); shared harness decisions are local-only. Every live Muse call goes through one guard (key, 8 runs per session, 60 per day for the app). The Muse client has a 90 s timeout and 3 retries; a failed model call ends the run with `stop="error"` and keeps its drafts. D-034 applied to leftovers: the system prompt no longer says `"repu" = tomorrow` or "Telangana, 3PL"; validator thresholds live in `configs/operating_rules.yaml`; road speed comes from the world config; the gate learns generic vehicle words from each company's messages. These change the agent and gate after EXP-009/011 ran: those results stand for the commits they were frozen at, and are not re-claimed for this version | accepted |
| D-039 | 2026-10-30 | **Demo = one company, three ways of learning from its own runs, all visible.** Session 1 fails three ways (a business fact, a tool-use problem, a question no tool answers). A nightly review reads the agent's runs and feedback and code sends each problem to its fix: Loop B (lesson → evidence gate → reviewer), Loop A (patch → paired test → approval) or new-tool creation (D-040). Session 2 shows all three fixed. A Logs page shows runs, lessons, patches, tools and reviews on one timeline. Hospital and call-centre demos are **not built**: 2–3 days each, "medical" is an anti-project, and the new-business story is already proven (EXP-011 pack, D-030 adapters); they get one future-work slide. React frontend and a government-docs RAG were also declined (time; "basic RAG" is an anti-project). Plan: [[implementation_plan]] | accepted (owner, Oct 30) |
| D-040 | 2026-10-30 | **New tools are written as read-only SQL, never Python.** When no tool fits, the agent may call `run_query`: one SELECT over an in-memory copy of its own company's records (query_only, SELECT-only authorizer, time/row/length caps, untrusted text marked). A query template reused in ≥ 2 requests becomes a candidate tool; it must return the same rows as the originals, run on held-out values from the company's data, and be approved by a person. Approved tools are company-private (never in packs) and can be retired. Harness patches still may not contain executable code (FR-14): generated tools are a separate, gated store. `run_query` is off in frozen experiment configs | accepted (owner, Oct 30) |
| D-041 | 2026-10-30 | **Onboarding: the agent learns what the business is, from its data first, then asks.** Code builds a draft business profile from the company's own records (towns and sites, clients, fleet mix, volumes, goods classes, planner languages, busy days); Muse picks 5–7 questions only about what the records can't show (priorities, must-not-be-late customers, unwritten rules, approvals, peaks, words). Each stated rule is checked against the records: supported → a lesson candidate through the same gate and approval; contradicted → asked back with the count. The profile is saved per company with versions; a short "About this business" block (owner's description, capped, data not instructions) replaces "a regional transport company" in the prompt; stated priorities seed tool candidates. Off in frozen experiment configs. Workstream H in [[implementation_plan]] | accepted (owner, Oct 30); **scope cut Oct 30 by D-042** |
| D-042 | 2026-10-30 | **After the deep audit (score ~5.8 now, ~7.4 if the plan and video land): onboarding is slimmed and deploy moves first.** H = the business profile computed by code from the company's records, editable by the owner, shown in the agent's prompt (no Muse questions or answer checks; those are cut). Deploy (no keys, replay) right away (done Oct 30) by the owner from steps I prepare, to find hosting problems early. Audit actions adopted: README honesty pass (test count 287 incl. archive, Limitations with n per claim and the D-038 version gap, Harness² and workshop credit, Open Weights pitch), C slimmed (manual "make this a tool" first), the video gets Nov 3 + the Nov 4 buffer, a staged failure is labelled as staged | accepted (owner, Oct 30) |
| D-043 | 2026-10-30 | **Push toward 9/10 (owner).** Added to the plan: workstream I (impact and tooling evidence: README honesty pass, each Muse model's role shown on screen, Best Open Weights pitch, 1–2 cited freight statistics, a review kit for the interviewed dispatcher to check 10–15 learned lessons and time "plan tomorrow", a spreadsheet-import path for "who uses this on Monday") and workstream J (EXP-011R: EXP-011 re-run 3 times on the current version, pre-registered, ~$15, to give the spread and close the D-038 version gap; EXP-012 for new tools, ~$3). Target: weighted ~8–8.5, not 9 everywhere (all data is synthetic). Spreadsheet import is cut first if a day slips | accepted (owner, Oct 30) |
| D-044 | 2026-10-31 | **Multi-agent redesign and React app: designed in another assistant's session, merged here.** [[Anubhav_MultiAgent_Design_v1]] (status FINAL there, decisions #1–16, delivery plan §4.9 marked confirmed by the owner): Planner as orchestrator delegating to Analyst, Tool Forge and Lesson Miner through one `delegate` tool (depth ≤ 2, shared budget); per-agent instructions, knowledge and learning loops; learned routing; React + FastAPI in one Hugging Face Docker Space; a new pre-registered benchmark (~$30, one repeat). The single Planner stays the baseline and fallback, and Streamlit stays the hosted link until React is verified. Conflicts: the Oct 30 plan had Nov 3–4 for the video and submission only; EXP-011R numbers apply to the single Planner only. **Owner, Oct 31: go; the owner and Claude build it in parallel; the other session's plan was the owner's own (a second view), so the entry stays solo.** | accepted (owner, Oct 31); Sprint 0 and Sprint 1 Python done Oct 31 |
| D-045 | 2026-10-31 | **What "makes a tool" means (owner).** Read-only tools only. A query written for **3+ different requests** becomes a candidate (the same query pattern, any agent's query; the same request again doesn't count; a person may still promote one early and it must pass the same checks). When nothing fits, `find_capability` reports `tool_missing` and Tool Forge writes the first query. Code builds and tests the tool; a person approves. No new code, no outside connections, no generating MCP servers: approved tools appear on the one existing server. EXP-012/012b were measured at the old threshold of 2 and stay labelled so. Harness² emphasis in the demo: decide later. Fallback if time runs short: Lesson Miner slips, Tool Forge stays | accepted (owner, Oct 31) |

---

### D-001: Theme is Build for Your World only
- **Context:** PRD v1 hedged between "Push the Frontier" and "Build for Your World".
- **Decision:** Submit under Build for Your World.
- **Alternatives:** Push the Frontier, whose examples are robotics, energy, materials and physical systems; a weak fit.
- **Consequences:** One clear story. The self-improving harness becomes the technical *how*, not the theme.
- **Rubric impact:** Impact (fits the problem statement), Stage 1 pass.

> **D-001 superseded on 2026-10-27 by D-018.** The owner's headline makes the capability the product, which fits Push the Frontier.

### D-003: Voice gated on the T6 test
- **Context:** Voice adds a second Meta model and the video hook, but Telugu support in Muse Voice Transcribe is unverified.
- **Decision:** Run T6 on Day 1. Voice goes IN only if the transcripts can drive the golden path.
- **Consequences:** If it goes OUT, the ~3 hrs go to polishing the improvement loop.
- **Rubric impact:** Meta tooling, Demo.

### D-005: No real user data
- **Context:** No access to wholesalers; getting consent would take too much of 8 days.
- **Decision:** Fictional data; the developer records their own voice notes; public stats are cited and verified; a self-timed manual-vs-agent study is labeled as self-timed.
- **Consequences:** The Impact story rests on scale plus measured numbers. Never invent quotes.

### D-006: Cut order
- **Context:** Cutting tools first (as in v1) would make the BigTool comparison meaningless.
- **Decision:** See the table. Never cut the live quote path, traces, the verifier, at least one improvement decision, or video day.

### D-017 / D-018: Headline and theme
- **Context:** The owner set the headline around the agent's capability: getting better at discovering and using tools through verified experience, without retraining. The concepts behind it are langgraph-bigtool (tool retrieval at scale) and Harness² (improve the harness, not the model).
- **Decision:** Submit under Push the Frontier. The Telugu business is the proof case, not the product.
- **Consequences:**
  - BigTool retrieval and the improvement loop are the core.
  - Recall@k becomes a headline metric (D-020).
  - The headline needs a subline that names the human beneficiary, to cover Impact (30%).
  - "Measurably" requires a real, honestly reported held-out uplift (R-04).
- **Rubric impact:** Meta tooling, Tech, Impact (through the adoption path).

### D-019: Proof-case domain stays FMCG/kirana distributor
- **Context:** Pharma distribution was considered: richer tools and higher stakes, but some anti-project perception risk and a rebuild. The owner prioritised the best demo they can build solo.
- **Decision:** Keep the already-built FMCG/kirana distributor. List pharma, agri-input, dairy, spare parts and other languages as adoption targets on the final video slide and in the README.
- **Consequences:** No rebuild cost, and zero perception risk. The impact story is breadth across domains.

### D-014: Muse Spark 1.3, standard mode
- **Context:** Smoke tests passed on 1.3. Contributor mode is ~12× cheaper but lets Meta train on our prompts, and is limited to 150 RPM.
- **Decision:** Use `muse-spark-1.3` standard for everything that's measured. The estimated benchmark cost is under $10, so cost isn't a constraint.
- **Alternatives:** Contributor mode (cheaper, but adds a data-use question and a lower rate limit); 1.2 (recommended for audio input, but we transcribe separately).
- **Consequences:** One frozen model ID for the "same frozen model" claim (AT-09). Voice goes through Muse Voice Transcribe, not Spark audio input.
- **Rubric impact:** Tech (clean experiment), Meta tooling (latest model).

---

### D-022: CSV source of truth, hidden shop knowledge, benchmark v1
- **Context:** If Muse already handles Telugu and tool calling well, an easy benchmark shows no room to improve, and the headline claim collapses.
- **Decision:** Expand the fictional business (84 SKUs with near-duplicates, 17 customers with look-alike names, units, schemes, credit limits, 98 historical orders) as CSVs loaded into SQLite. Keep shop slang ("GG oil", "pedda dabba", "Ravi anna") in `hidden/`, never in the DB. Write 48 tasks whose expected flags and totals come from the pricing engine.
- **Alternatives:** Making tasks artificially hard (judges would notice); keeping the 40-SKU seed (too easy for retrieval).
- **Consequences:** Headroom comes from realistic business knowledge a frozen model can't have, not from tricks. `tests/test_benchmark.py` keeps every task consistent with the data.
- **Rubric impact:** Tech (verifiable benchmark), Impact (realistic shop conventions), Demo (a slang failure fixed on screen).

### D-023: Baseline first; Muse tool search as arm B
- **Context:** Muse may already be strong; Muse also has built-in `tool_search` / `defer_loading`.
- **Decision:** Run an early baseline (Day 2–3) to measure the real failure rate before building the loop. Arm B uses Muse's own tool search; arm C adds our human-approved harness patches (Harness² method) on top.
- **Alternatives:** Our own BigTool retrieval as arm B (more code, and weaker on Meta tooling if Muse's search is better).
- **Consequences:** If the baseline is above ~90%, shift the claim to efficiency and reliability over repeats and add harder realistic tool sets. First check whether tool descriptions can be updated between requests so learned aliases reach the search.
- **Rubric impact:** Meta tooling (built-in Muse features), Tech (honest baseline).

