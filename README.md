# Anubhav

> Built during the **Meta Global AI Developer Hackathon** (Oct 26 – Nov 4, 2026) · Indie track · *Push the Frontier*

**An agent that learns a business's unwritten rules from its own records, and gets safer because of it.** A regional logistics dispatcher asks in Telugu, Roman Telugu or English, by text or voice. The agent plans a draft trip with generic tools over the company's data. Behind it, Meta Muse mines the company's trip history for rules nobody wrote down. Code checks the evidence, a person approves, and the next plan uses the lesson. Approved regional knowledge can be shared with a new company without leaking anything private. *Anubhav* means "experience".

*Same model. Verified experience. Safer plans.*

## The problem
A dispatcher near Warangal knows that a 32 ft truck can't get into one Jangaon godown. That rule isn't in any system. It lives in a driver's note from a failed trip and in the dispatcher's head. An AI agent connected to the company's data passes every check and still sends the 32 ft truck.

Muse already handles Telugu, Roman Telugu and tool calls well. What it can't know is the local, unwritten part. Anubhav lets the agent earn that knowledge from the business's own records, with proof, and only after a person agrees.

## Results (all pre-registered; files frozen by hash before any model call)

**Final benchmark, EXP-011.** It runs on a world the system had never seen (fresh seed 5279), with the same model (Muse Spark Open) and the same 38 cases in RT/TE/EN, one run each.

| Company | Cold, with raw-note search | With learning |
|---|---|---|
| T01 | 7/14 correct · 0 unsafe | **12/14 · 0 unsafe** (its approved lessons) |
| T02 | 5/12 · 1 unsafe | **12/12 · 0 unsafe** (its approved lessons) |
| New company, day 1 | 6/12 · 2 unsafe | **12/12 · 0 unsafe** (domain pack from T01 + T02) |

- **Lessons beat raw-note search:** on unwritten knowledge (limited gates, site nicknames, real truck capacity), 35% → 90% correct, against a bar of +25 points.
- **Sharing works:** a new company gets 33% → 100% on day 1, with 0 private details leaked.
- **Searching raw notes is not enough:** cold with and without note search scored about the same (30% vs 35%). The notes are there, but the agent rarely looks, and a note is not a rule.
- **Not improved:** real truck capacity. The agent refused to overload the truck but didn't suggest another one.

**Does it learn the right things?** Mining is scored against the generator's hidden rules, which the system never sees.

| | Precision | Recall | Traps let in |
|---|---|---|---|
| EXP-008 (demo world) | 73% | 73% | – |
| EXP-009 (unseen world 4111) | 83% (bar 85%, missed) | 74% | 0 |
| EXP-009b (unseen world 5279, one generic fix) | **90%** | 69% | **0** |

**What didn't work, and what we learned**
- **EXP-007:** on a small, clean history, simply giving the agent the raw history did as well as lessons (8/8 vs 7/8). We changed the pitch: the gain comes from scale, noise, safety and sharing. Sharing raw history with another company scored 3/8, while a pack scored 8/8.
- **EXP-010:** tool practice in a feedback loop started at 100% on held-out questions, so the proposed patch was correctly **rejected**: no gain, no change.

Details: [experiments log](docs/trackers/experiments.md) · [decisions](docs/trackers/decisions.md) · [errors and fixes](docs/trackers/errors_and_fixes.md).

## How it works

```mermaid
flowchart TB
  U["Dispatcher · text or voice<br/>Roman Telugu / Telugu / English"] -->|Muse Voice Transcribe| A
  subgraph Agent["Agent · Muse Spark Open · LangGraph bounded loop"]
    A[Plan with tools] --> T[19 generic MCP tools<br/>find site · orders · vehicles · constraints · routes · notes]
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
```

1. **Records:** trips, staff corrections, driver notes and outcomes, in each client's own format. Adapters map them to one canonical view.
2. **Generic tools:** 19 tools work on any client's data through an MCP server. Tool lists are filtered by role, and every call goes through one broker that enforces company and role.
3. **Mine:** Muse Spark 1.3 reads a digest of the history and proposes lessons, such as "32 ft trucks can't enter the Jangaon godown".
4. **Check:** the evidence gate is code. It needs supporting observations, rejects contradictions, tests vendor reliability statistically and rejects habits that only look like rules.
5. **Review:** a person approves each lesson as advice or as an enforced rule. Lessons expire, can be challenged by new outcomes and can be rolled back. Every step is audited.
6. **Use:** approved lessons appear exactly where the agent looks (site constraints, tool hints). Enforced rules are checked again by code before a draft is saved.
7. **Share:** only approved regional facts travel, rewritten in the recipient's ids, with counts instead of evidence text, and a leak check. The recipient opts in and can revoke.

Nothing in the runtime is hand-coded world knowledge: no word lists, no site rules, no spelling maps. The agent has to learn them.

## Meta AI used
| Role | Model | Access |
|---|---|---|
| Agent: planning and tool calls, multilingual replies | Muse Spark Open (`muse-spark-open-1026`) | Baseten Model API |
| Lesson miner and harness proposer | Muse Spark 1.3 | Meta Model API |
| Voice requests in Telugu / Roman Telugu | Muse Voice Transcribe | Meta Model API |

## Try it
**Hosted demo:** *(link after deploy)*. Replay mode is free and needs no keys.

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
- **Proof & audit:** the benchmark and every traced run.

**Other commands**
```bash
uv run pytest -q                                              # 238 tests, no model calls
uv run python -m anubhav.data.generate --full --seed 4242     # a new world with your own seed
uv run python -m anubhav.learning.cli mine --company T01      # mine lessons (Muse Spark 1.3)
uv run python -m anubhav.mcp_server --company T01 --role dispatcher   # the tools over MCP (stdio)
uv run python scripts/exp011_benchmark.py                     # the final benchmark (~$5)
```
Deploying: [docs/deploy.md](docs/deploy.md).

## Repository layout
```
src/anubhav/
  data/        world-first synthetic generator: hidden truth kept apart from what the agent sees; 3 client schemas
  runtime/     canonical company view, 19-tool broker, safety validator, drafts and holds
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
Everything in this repository was written during the event, starting Oct 27, 2026. The commit history shows it day by day. Third-party open-source libraries are used as dependencies only; see [LICENSES_AND_ATTRIBUTION.md](LICENSES_AND_ATTRIBUTION.md). All companies, people, sites, trucks and rules are **fictional**, generated by our own code.

## License
[MIT](LICENSE)
