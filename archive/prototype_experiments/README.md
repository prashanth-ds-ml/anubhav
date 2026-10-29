# Prior experiments (EXP-001 to EXP-006)

Everything here was built on Oct 27, 2026, before the project settled on Anubhavam. It is kept as evidence: the files are unchanged, and their sha256 hashes match the pre-registrations in [`docs/trackers/experiments.md`](../../docs/trackers/experiments.md).

| Exp | Question | Result | Files |
|---|---|---|---|
| EXP-001 | Can Muse run a code-mixed order desk with tools? | 88% | `scripts/eval/run_baseline.py`, `datasets/business/`, `datasets/tasks/` |
| EXP-002 | Does it scale to 40 tools with tool search? | 86%, ~2× cost | same as above |
| EXP-003 | Does an optimiser beat a simple heuristic? | Both optimal; dropped | `scripts/eval/exp003_lab.py`, `datasets/lab/` |
| EXP-004 | Spark Open vs Spark 1.3? | About equal | `scripts/eval/run_baseline.py` |
| EXP-005 | Where does Muse fail at dispatch planning? | Unwritten knowledge 0–12% | `scripts/eval/exp005_dispatch.py`, `datasets/dispatch/` |
| EXP-006 | Can it learn that knowledge from history and share it? | 0% → 100%, 0 leaks | `scripts/eval/exp006_transfer.py`, `datasets/dispatch/` |

All data is fictional and synthetic. Raw results are in `artifacts/`.

## Running them
Run from the repo root (the API keys are read from the root `.env`):

```bash
uv sync
uv run pytest -q                                                                   # 128 tests, mock mode, no credits
uv run python archive/prototype_experiments/scripts/data/build_db.py               # rebuild the order-desk SQLite DB
uv run python archive/prototype_experiments/scripts/eval/exp005_dispatch.py --self-test
uv run python archive/prototype_experiments/scripts/eval/exp006_transfer.py --self-test
```

`src/order_agent/` is the order-desk package (SQLite simulator, pricing engine, Muse client) these experiments import.
