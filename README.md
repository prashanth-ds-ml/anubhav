# Telugu-First Self-Improving Order Agent

> Built during the **Meta Global AI Developer Hackathon** (Oct 26 – Nov 4, 2026) · Indie track · *Push the Frontier*

**A Meta Muse-powered, Telugu-first agent that gets measurably better at discovering and using business tools through verified experience, without retraining the model.**

**Proof case:** the order desk of a Telugu-speaking wholesale distributor. Retailers' voice notes and messages mix Telugu script, Roman Telugu and English, and the agent turns them into **verified draft quotations**. When it fails, Muse diagnoses the failure and proposes a bounded fix to its own operating harness, never its weights. The fix is tested on unseen tasks, and a human approves it before it goes live.

*"Same frozen model. Smarter harness."*

**Where it can go next:**
- pharma distribution
- agri-input dealers
- dairy cooperatives
- spare-parts counters
- other Indian languages

Only the tool registry and the language guidance change. The improvement loop stays the same.

**Status:** 🚧 work in progress (Day 1). See [`docs/PRD_v1.1.md`](docs/PRD_v1.1.md).

## Meta models used
| Role | Model |
|---|---|
| Order agent (tool calling) | `muse-spark-1.3` |
| Voice-note transcription (Telugu) | `muse-voice-transcribe-1.0` |
| Failure diagnostician and patch proposer | `muse-spark-1.3` |

**Repo:** https://github.com/prashanth-ds-ml/meta-hackathon-telugu-agent

## Quick start (so far)
```bash
git clone https://github.com/prashanth-ds-ml/meta-hackathon-telugu-agent.git
cd meta-hackathon-telugu-agent
uv sync
echo "meta_api=<your Meta Model API key>" > .env
uv run python scripts/smoke/smoke_text.py           # T1–T5, T8 capability checks
uv run python scripts/smoke/smoke_negation_loop.py  # "order confirm cheyyaku" safety loop
uv run python scripts/smoke/smoke_voice.py voice/*  # Telugu voice-note transcription (files)
uv run python scripts/smoke/live_voice.py --seconds 20 --agent  # live mic → transcript → Muse tool calls
uv run pytest -q                                    # unit tests (mock mode, no credits)
```

## Repository layout
```
src/order_agent/      # Python package: db/ (SQLite simulator), pricing.py (reference quote engine), llm.py (Muse + mock adapter)
datasets/business/    # fictional distributor ERP as CSV (source of truth); hidden/ = shop slang the agent must learn
datasets/tasks/       # 48-task benchmark (32 dev / 16 held-out)
scripts/data/         # build_db.py: CSV -> data/business.db
scripts/smoke/        # Day-1 capability tests against the Meta Model API
tests/                # pytest (mock mode, no API credits)
artifacts/smoke/      # raw smoke-test results (evidence)
docs/                 # Obsidian vault: PRD, day plan, trackers, daily notes
```

## Built during the hackathon vs. third-party
Everything in this repository was written during the hackathon, starting Oct 27, 2026. Third-party libraries are used as dependencies only: OpenAI Python SDK (pointed at the Meta Model API), httpx, python-dotenv. Later additions will be LangGraph, langgraph-bigtool, MCP SDK and Streamlit. All business data (customers, brands, prices) is **fictional**.

## License
MIT
