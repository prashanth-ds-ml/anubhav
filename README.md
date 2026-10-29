# Anubhavam

> Built during the **Meta Global AI Developer Hackathon** (Oct 26 – Nov 4, 2026) · Indie track · *Push the Frontier*

**An agent that learns a business's unwritten rules from the business's own records.** It checks the evidence, asks a person to approve risky lessons, and shares safe regional knowledge with the next customer of the same type. It works in Telugu, English and Roman Telugu, on Meta Muse. *Anubhavam* (అనుభవం) means "experience".

*Same model. Verified experience. Better decisions.*

## The problem
A dispatcher near Warangal knows that a 32 ft truck can't get into one Jangaon godown. That rule isn't in any system; it lives in a driver's note from a failed trip. An AI agent connected to the business data passes every check and still sends the 32 ft truck.

In our prior experiments, Muse handled Telugu, Roman Telugu and tool calls at 88–100%, but scored **0–12% on unwritten local knowledge**. That gap is what Anubhavam closes.

## How it learns
1. **Records:** trips, staff corrections and outcomes are stored.
2. **Mine:** Muse proposes candidate lessons, such as "32 ft trucks can't use the north entrance of the Jangaon godown".
3. **Check:** code decides, not the model. Lessons need supporting evidence and no contradictions, and habits that look like rules are rejected.
4. **Review:** a person approves risky lessons. A lesson stays a warning until it is approved as a rule.
5. **Use:** approved lessons guide the next plan; a deterministic safety check enforces hard rules.
6. **Refresh:** contradicting outcomes challenge a lesson; lessons expire and can be rolled back.
7. **Share:** lessons are private by default. Approved regional lessons form a domain pack that helps a new customer from day 1.

The agent only ever creates **draft** plans. It never dispatches real goods.

## Status
🚧 **In progress.** The new build starts now. What exists today:
- **Design:** [PRD v3.1](docs/PRD_v3.1.md), [Data & Benchmark Blueprint](docs/Data_Benchmark_Blueprint_v1.0.md) and an [overview](docs/Anubhavam_overview.md). Scope: 3 history companies + 1 new test company.
- **Prior experiments** (small synthetic sets, 13–16 tasks): [archive/prototype_experiments](archive/prototype_experiments/). The most relevant is EXP-006: unwritten-rule tasks went from 0% to 100% after learning from 123 trips, and a second company using the domain pack went from 0% to 100% with 0 leaks. These are early signals, not final results.

## Meta models
| Role | Model |
|---|---|
| Agent (planning, tool calls) | Muse Spark / Muse Spark Open |
| Lesson miner | Muse Spark |
| Voice input (Telugu) | Muse Voice Transcribe |

## Repository layout
```
docs/                          # Obsidian vault: PRD, blueprint, overview, diagrams, trackers, daily notes
archive/prototype_experiments/ # EXP-001–006: code, data and raw results (unchanged, hashes verified)
src/anubhavam/                 # the new build (coming)
```

## Quick start
```bash
git clone https://github.com/prashanth-ds-ml/anubhav.git
cd anubhav
uv sync
echo "meta_api=<your Meta Model API key>" > .env
uv run pytest -q    # prior-experiment tests, mock mode, no credits
```

## Built during the hackathon vs. third-party
Everything in this repository was written during the hackathon, starting Oct 27, 2026. Third-party libraries are used as dependencies only (OpenAI Python SDK pointed at the Meta Model API, httpx, python-dotenv, and more as listed in `pyproject.toml`). All companies, people, operating rules and data are **fictional**.

## License
MIT
