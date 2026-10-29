"""Trace store: every agent run is appended as one JSON line (full trace) and indexed in SQLite (one row),
so any run can be inspected, replayed and costed. Secrets never enter a trace (no keys are ever in messages)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .data.config import ROOT

TRACE_DIR = ROOT / "data" / "traces"


def save(run: dict, directory: Path = TRACE_DIR, label: str = "live") -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    run = {**run, "saved_at": datetime.now().isoformat(timespec="seconds"), "label": label}
    path = directory / f"{datetime.now():%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False, default=str) + "\n")
    con = sqlite3.connect(directory / "index.sqlite")
    con.execute("create table if not exists runs (run_id text primary key, saved_at text, label text, company text, "
                "role text, model text, request text, stop text, turns int, tool_calls int, drafts text, cost_usd real, "
                "latency_s real, file text)")
    con.execute("insert or replace into runs values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run["run_id"], run["saved_at"], label, run["company"], run["role"], run["model"], run["request"],
                 run["stop"], run["turns"], run["tool_calls"], json.dumps(run["drafts"]), run["cost_usd"],
                 run["latency_s"], path.name))
    con.commit()
    con.close()
    return path


def load(run_id: str, directory: Path = TRACE_DIR) -> dict | None:
    for p in sorted(Path(directory).glob("*.jsonl"), reverse=True):
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["run_id"] == run_id:
                return r
    return None


def replay(run_id: str, directory: Path = TRACE_DIR) -> list[str]:
    """A readable step-by-step view of a saved run (labelled as a replay)."""
    r = load(run_id, directory)
    if not r:
        return [f"no run {run_id}"]
    lines = [f"REPLAY of {r['run_id']} ({r['label']}, {r['model']}, {r['company']}): {r['request']}"]
    for s in r["trace"]:
        if s["type"] == "tool":
            lines.append(f"  tool {s['name']}({s['arguments']}) -> {'ok' if s['ok'] else s['error']['code']}")
        elif s["type"] == "model" and s.get("content"):
            lines.append(f"  model: {s['content'][:200]}")
    lines.append(f"  reply: {r['reply'][:300]} · drafts {r['drafts']} · ${r['cost_usd']} · {r['stop']}")
    return lines
