"""E-033: a fresh clone has every input the experiment scripts load and every file the experiments index cites."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def test_the_lesson_stores_the_experiment_scripts_load_are_in_the_repository():
    # scripts/exp009*_gate.py and session.EXP008 load EXP-008's lessons; exp011/011r/013 load EXP-009b's gated lessons
    assert sorted((ART / "learning").glob("exp008_*_rep0.sqlite")), "EXP-008 lesson store missing"
    assert sorted((ART / "learning").glob("exp009b_*_fresh.sqlite")), "EXP-009b lesson store missing"


def test_every_plan_and_result_file_in_the_experiments_index_exists():
    data = json.loads((ART / "experiments_index.json").read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data["experiments"]
    missing = [f"{e['id']}: {part['file']}" for e in rows for part in (e.get("plan") or {}, e.get("result") or {})
               if part.get("file") and not (ROOT / part["file"]).exists()]
    assert not missing, missing
