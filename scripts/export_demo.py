"""Export the small demo bundle the hosted app needs (git-tracked, no secrets): saved real runs for free replay,
the EXP-008 lessons, and the tool-practice results.

  uv run python scripts/export_demo.py
"""

import json
import sqlite3
from pathlib import Path

from anubhav.data.config import ROOT
from anubhav.ui.core import SUGGESTIONS

OUT = ROOT / "demo"


def main():
    OUT.mkdir(exist_ok=True)
    wanted = set(SUGGESTIONS.values())
    runs, seen = [], set()
    for p in sorted((ROOT / "data" / "traces").glob("*.jsonl"), reverse=True):
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            key = (r["company"], r["request"].strip(), bool(r.get("knowledge")))
            if r["request"].strip() in wanted and r["company"] in ("T01", "TNEW") and key not in seen:
                seen.add(key)
                runs.append(r)
    (OUT / "replay_runs.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in runs) + "\n", encoding="utf-8")
    store = sorted((ROOT / "artifacts" / "learning").glob("exp008_*_rep0.sqlite"))[-1]
    con = sqlite3.connect(store)
    con.row_factory = sqlite3.Row
    lessons = {t: [dict(r) for r in con.execute(f"select * from {t}")] for t in ("lessons", "lesson_events")}
    con.close()
    (OUT / "exp008_lessons.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=1), encoding="utf-8")
    hs = ROOT / "data" / "harness" / "harness.sqlite"
    con = sqlite3.connect(hs)
    con.row_factory = sqlite3.Row
    practice = [dict(r) for r in con.execute("select * from practice where round like 'EXP010%'")]
    con.close()
    (OUT / "practice.json").write_text(json.dumps(practice, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(runs)} replay runs, {len(lessons['lessons'])} lessons, {len(practice)} practice rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
