# Anubhav

> Built during the **Meta Global AI Developer Hackathon** (Oct 26 – Nov 4, 2026) · Indie track · *Push the Frontier*

**An agent that learns a business's unwritten rules from its own records, and gets safer because of it.** A regional logistics dispatcher asks in Telugu, Roman Telugu or English, by text or voice. The agent plans a draft trip with generic tools over the company's data. Behind it, Meta Muse mines the company's trip history for rules nobody wrote down. Code checks the evidence, a person approves, and the next plan uses the lesson. Approved regional knowledge can be shared with a new company without leaking anything private. *Anubhav* means "experience".

*Same model. Verified experience. Safer plans.*

## The problem
A dispatcher near Warangal knows that a 32 ft truck can't get into one Jangaon godown. That rule isn't in any system. It lives in a driver's note from a failed trip and in the dispatcher's head. An AI agent connected to the company's data passes every check and still sends the 32 ft truck.

This is the normal case, not an edge case. India has about 12.5 million trucks run by about 3.5 million operators, and "around 75% of truck operators in India own fewer than five trucks" ([Redseer, Dec 2024](https://redseer.com/articles/unlocking-growth-in-indias-fragmented-trucking-sector/)). Small operators run on phone calls, notes and memory, not software. Logistics still costs India about 7.97% of GDP (2023–24, DPIIT–NCAER *Assessment of Logistics Cost in India*, as [reported in Sep 2025](https://aslindia.net/newsletters/indias-logistics-costs-fall-to-797-of-gdp-in-fy-202324-dpiit)).

Muse already handles Telugu, Roman Telugu and tool calls well. What it can't know is the local, unwritten part. Anubhav lets the agent earn that knowledge from the business's own records, with proof, and only after a person agrees.

## Results (pre-registered; files frozen by hash before any model call; read the [limitations](#limitations))

**Final benchmark, EXP-011R: the shipped version, 3 repeats.** A world the system had never seen (fresh seed 5279), the same model (Muse Spark Open), 38 cases in RT/TE/EN, each run 3 times (306 runs), on the version you can try. Totals over the 3 repeats:

| Company | Cold, with raw-note search | With learning |
|---|---|---|
| T01 | 21/42 correct · 2 unsafe | **36/42 · 0 unsafe** (its approved lessons) |
| T02 | 26/36 · 1 unsafe | **36/36 · 0 unsafe** (its approved lessons) |
| New company, day 1 | 18/36 · 6 unsafe | **36/36 · 0 unsafe** (domain pack from T01 + T02) |

- **Lessons beat raw-note search:** on unwritten knowledge (limited gates, site nicknames, real truck capacity), 48% → 90% correct pooled (+40, +45, +40 points in the three repeats; 20 cases each), against a pre-registered bar of +25. **Replicated in 3 of 3 repeats.**
- **Sharing works:** a new company gets 33% → 100% on its regional cases on day 1 in every repeat (9 cases each), and our leak check found 0 private details in the packs. **Replicated in 3 of 3 repeats.**
- **The first measurement (EXP-011, commit `61cc927`, one run each) agreed:** 35% → 90% and 33% → 100%.
- **Searching raw notes is not enough:** in EXP-011 cold with and without note search scored about the same (30% vs 35%). The notes are there, but the agent rarely looks, and a note is not a rule.
- **Not improved:** real truck capacity (T01): 0/6 with lessons in EXP-011R (2/6 without). The agent refuses to overload the truck but does not complete a safe plan; refusals that name a free vehicle that fits did not change that.

**New tools (EXP-012 and EXP-012b, unseen world 5279, 16 held-out questions no built tool was designed for).**
- With the read-only query tool the agent answered 13/16 vs 11/16 with built-in tools only: +12.5 points, short of the pre-registered +25 (EXP-012).
- In EXP-012 it never called the tools it had learned (0/16), because each was named after the one request it came from. With general names (EXP-012b) it used them in **14/16** questions, answered 15/16 (vs 14/16 without them), with 20% fewer tool calls and 24% lower cost. The pre-registered bar was 30% fewer calls: **not met**.

**Does it learn the right things?** Mining is scored against the generator's hidden rules, which the system never sees.

| | Precision | Recall | Traps let in |
|---|---|---|---|
| EXP-008 (demo world) | 73% | 73% | – |
| EXP-009 (unseen world 4111) | 83% (bar 85%, missed) | 74% | 0 |
| EXP-009b (unseen world 5279, one generic fix) | **90%** | 69% | **0** |

**What didn't work, and what we learned**
- **EXP-007:** on a small, clean history, simply giving the agent the raw history did as well as lessons (8/8 vs 7/8). We changed the pitch: the gain comes from scale, noise, safety and sharing. Sharing raw history with another company scored 3/8, while a pack scored 8/8.
- **EXP-010:** tool practice in a feedback loop started at 100% on held-out questions, so the proposed patch was correctly **rejected**: no gain, no change.

**The team, EXP-013 (one repeat, 54 cases: 38 planning cases and 16 data questions).** An orchestrator (Planner) with sub-agents (Analyst, Tool Forge, Lesson Miner), against one planner:

| | Correct | Unsafe drafts | Mean cost a case | Routing |
|---|---|---|---|---|
| Single Planner | 48/54 | 0 | $0.054 | n/a |
| Team | 47/54 | 0 | $0.073 | 91% |
| Team after one learning round | 46/54 | 0 | $0.069 | 98% |

- **Met:** no unsafe drafts, within 5 points of one planner (−1.9), within 1.5× the cost (1.36×). By the rule fixed beforehand, the team is the API's default.
- **The team is not more accurate or cheaper than one planner.** Planning cases are the same (36/38 in every arm). On data questions the arms got 12, 11 and 10 of 16. What it adds is visible hand-offs, tool creation and per-agent learning, not better answers.
- **Learning round, not met:** routing +7.4 points against a bar of +15 (M0 was already at 91%, so +15 was out of reach). Two changes passed their paired tests and cost per case fell 5%, but answers did not improve.
- **The team's demo bundle isn't recorded yet:** hosted replays are single-Planner runs.

### Limitations
- **Synthetic data.** Every company, record and rule is generated by our own code. That is within the rules (the only data rule bans data we have no rights to), and it is how we can score lessons against hidden truth. An interview with a logistics professional shaped the world, but no real company's data has been used, and no real dispatcher has checked the lessons yet.
- **Our own cases.** The benchmark cases and the hidden rules they test come from the same generator. The system never sees the hidden rules, but we wrote the generator.
- **EXP-013 is one repeat on world 5279, already used by earlier experiments.** Team prompts were adjusted on smoke runs on another world first, and the routing label is our own definition. A one-case gap between arms means little.
- **Small samples.** 20 cases behind the lessons result and 9 behind the pack result, run 3 times each in EXP-011R; the repeats agree closely, but the case set is small and from one world.
- **The first EXP-011 run was interrupted and resumed.** 65 of its 102 runs are kept from their log lines (outcome, unsafe, cost), not full traces. There was also one pre-run fix to the leak check, logged before any model call. Both are in the [experiments log](docs/trackers/experiments.md).
- **Lessons were mined before the gate changed.** EXP-011R re-ran the shipped agent, broker and validator, but used the lessons mined and gated in EXP-009b; the gate's generic-vehicle-word change ([D-038](docs/trackers/decisions.md)) was not re-measured.
- **Mining misses about 3 in 10 hidden rules** (recall 69–74%), and every lesson still needs a person.
- **The tool-use loop has not yet improved anything.** In EXP-010 its one patch was correctly rejected (no held-out gain).
- **The leak check is our own token check** against the source company's ids, names and vendors, not a formal privacy guarantee.

Details: [experiments log](docs/trackers/experiments.md) · [decisions](docs/trackers/decisions.md) · [errors and fixes](docs/trackers/errors_and_fixes.md).

## How it works

```mermaid
flowchart TB
  U["Dispatcher · text or voice<br/>Roman Telugu / Telugu / English"] -->|Muse Voice Transcribe| A
  subgraph Agent["Agent · Muse Spark Open · LangGraph bounded loop"]
    A[Plan with tools] --> T[27 generic MCP tools in 7 groups<br/>orders & sites · fleet & drivers · planning · trips & documents<br/>history & performance · knowledge]
    T --> D[Draft only: never dispatches]
    D --> V{{Deterministic safety check<br/>enforces approved rules}}
  end
  T --> DB[(Company data<br/>any schema → canonical adapter)]
  DB --> M["Miner · Muse Spark 1.3<br/>proposes lessons from history"]
  M --> G{{Evidence gate · code, not the model<br/>support, contradictions, Fisher test, habits ≠ rules}}
  G --> R[Person reviews: advice or enforced rule]
  R -->|approved lessons| A
  R --> P[Domain pack: regional facts only,<br/>recipient's ids, counts-only evidence, leak check, opt-in, revocable]
  P -->|day-1 knowledge| N[New company]
  F[Tester feedback + traces] --> H[Harness loop: tool hints and guidelines,<br/>paired test gate, versions, rollback] --> A
  A -->|no tool fits| Q[Read-only SQL query<br/>sandbox: SELECT only, own records]
  Q -->|reused for other requests| NT{{Tool checks · code<br/>same answers, held-out inputs}} --> R2[Person approves] -->|new tool| A
  NR[Nightly review of its own runs] --> H
  NR --> M
  NR --> NT
```

1. **Records:** trips, staff corrections, driver notes and outcomes, in each client's own format. Adapters map them to one canonical view.
2. **Generic tools:** 27 tools in 7 groups (orders & sites, fleet & drivers, planning, trips & documents, history & performance, knowledge, system) work on any client's data through an MCP server. They come from an audit of what planners actually ask. `plan_board` shows a whole day in one call, `check_load` tests a plan without committing, and `list_lessons` lets the agent explain what it has learned. Tool lists are filtered by role, and every call goes through one broker that enforces company and role.
3. **Mine:** Muse Spark 1.3 reads a digest of the history and proposes lessons, such as "32 ft trucks can't enter the Jangaon godown".
4. **Check:** the evidence gate is code. It needs supporting observations, rejects contradictions, tests vendor reliability statistically and rejects habits that only look like rules.
5. **Review:** a person approves each lesson as advice or as an enforced rule. Lessons expire, can be challenged by new outcomes and can be rolled back. Every step is audited.
6. **Use:** approved lessons appear exactly where the agent looks (site constraints, tool hints). Enforced rules are checked again by code before a draft is saved.
7. **Share:** only approved regional facts travel, rewritten in the recipient's ids, with counts instead of evidence text, and a leak check. The recipient opts in and can revoke.
8. **Make new tools:** when no tool fits, the agent writes one read-only SQL query over its own company's records (SELECT only, in a sandbox with time and row limits). A query it needed for other requests too becomes a candidate tool: code turns its values into parameters, checks that it gives the same answers and works on inputs it never saw, and a person approves it. Then the agent calls it in one step.
9. **Review its own runs:** a nightly review reads the agent's runs and feedback, and code sends each problem to its fix: tool use to the harness loop, reused queries to new tools, facts people stated to the miner and the evidence gate. Nothing becomes active without a person.
10. **Know the business:** a business profile counted from the records (sites, fleet, volumes, goods, languages), plus what the owner adds, is given to the agent as information.

Before the planner reads a reply, code checks it: every draft, vehicle and order id in it must come from that run, and it must never claim a dispatch. A refusal for a load that doesn't fit names free vehicles that would.

Nothing in the runtime is hand-coded world knowledge: no word lists, no site rules, no spelling maps. The agent has to learn them. A company's written thresholds (e-way bill value, segregation, cold chain) live in `configs/operating_rules.yaml`.

## Meta AI used
| Role | Model | Access |
|---|---|---|
| Agent: planning and tool calls, multilingual replies | Muse Spark Open (`muse-spark-open-1026`) | Baseten Model API |
| Lesson miner and harness proposer | Muse Spark 1.3 | Meta Model API |
| Voice requests in Telugu / Roman Telugu | Muse Voice Transcribe | Meta Model API |

**Open weights end to end:** every agent run, the live demo and the whole EXP-011 benchmark run on **Muse Spark Open**, the open-weights model, served by Baseten. Muse Spark 1.3 (Meta Model API) only proposes lessons and patches, offline, and code checks everything it proposes; Muse Voice Transcribe turns speech into text.

## Try it
**Hosted demo:** **[anubhav-metahackathon.streamlit.app](https://anubhav-metahackathon.streamlit.app/)**. Replay mode, no keys, free; each visitor gets their own drafts and lessons. The first open after a quiet spell can take about a minute while it wakes up.

**Locally:**
```bash
git clone https://github.com/prashanth-ds-ml/anubhav.git
cd anubhav
uv sync
uv run streamlit run streamlit_app.py     # builds the demo world from its seed on first start
```
Replay works with no keys. For live runs and voice, add a `.env`:
```
meta_api=<Meta Model API key>
baseten_api_key=<Baseten key>
```

Things to try in the app:
- **Workbench:** pick a suggestion and compare *Use approved lessons* off vs on. Open **Show as a graph** to see which tools the agent used.
- **What it learned:** each lesson, its evidence, and how it was learned day by day.
- **Share:** publish a pack to the new company and see what arrives.
- **Business profile:** what the agent knows about the company, counted from its records, plus what the owner adds.
- **Logs:** every run as plan → act → observe → code checks, and every lesson, patch, new tool, nightly review and piece of feedback on one timeline. Press "Run the nightly review".
- **New tools:** on the Workbench pick "New tool" (5 calls), then approve the reused query on this page and ask again (1 call).
- **Proof & audit:** the benchmark and every traced run.

**Other commands**
```bash
uv run pytest -q                                              # 520 tests (392 Anubhav + 128 archived prototype), no model calls
uv run uvicorn anubhav.api.app:app --port 7860                # the API for the web app; docs at /docs
uv run python scripts/exp013_team.py                          # the team vs one planner (~$14)
uv run python -m anubhav.data.generate --full --seed 4242     # a new world with your own seed
uv run python -m anubhav.learning.cli mine --company T01      # mine lessons (Muse Spark 1.3)
uv run python -m anubhav.mcp_server --company T01 --role dispatcher   # the tools over MCP (stdio)
uv run python scripts/exp011_benchmark.py                     # the final benchmark (~$5)
uv run python scripts/exp011r_benchmark.py                    # EXP-011 x3 on the current version (~$19)
uv run python scripts/exp012_new_tools.py                     # query tools and learned tools (~$3)
uv run python -m anubhav.review --company T01                 # the nightly review (code-only; --live adds one Muse call)
```
Deploying: [docs/deploy.md](docs/deploy.md).

## Repository layout
```
src/anubhav/
  data/        world-first synthetic generator: hidden truth kept apart from what the agent sees; 3 client schemas
  runtime/     canonical company view, 27-tool broker (7 categories), safety validator, drafts and holds
  mcp_server.py
  agent/       LangGraph agent loop
  learning/    digest → miner → evidence gate → lesson store → domain packs; truth scoring (evaluation only)
  harness/     how-to-work loop: feedback, trace signals, tool practice, patch gate, versions
  eval/        benchmark case builder and judge
  ui/          Streamlit helpers and graphs
app_pages/, streamlit_app.py   the demo app
scripts/       pre-registered experiments (EXP-008 … EXP-011), demo export
artifacts/     experiment results (JSON, logs)
demo/          small bundle for the hosted replay
configs/       world and client-schema configs
docs/          PRD, data spec, blueprint, trackers (Obsidian vault)
archive/       first prototypes and experiments EXP-001–006 (Oct 27–28)
tests/         data, runtime, learning, harness, safety (adversarial), eval
```

## Built during the hackathon
Everything in this repository was written during the event, starting Oct 27, 2026. The commit history shows it day by day. Third-party open-source libraries are used as dependencies only; see [LICENSES_AND_ATTRIBUTION.md](LICENSES_AND_ATTRIBUTION.md).

**Ideas we built on (reimplemented; no code copied):**
- The tool-use loop follows the Propose–Probe–Compose idea of **Harness²** (Google Research, [arXiv 2610.14224](https://arxiv.org/abs/2610.14224)), in a bounded form: small text patches, a paired old-vs-new test and human approval, with no executable code in patches.
- Meta's **legal-agent-workshop** (`meta-models/legal-agent-workshop`) suggested the client timeout and retries, a clean stop when a model call fails, and checking the reply's claims in code. All companies, people, sites, trucks and rules are **fictional**, generated by our own code.

## License
[MIT](LICENSE)
