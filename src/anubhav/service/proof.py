"""The measured results for the Proof page, read from the committed result files. Each says what it measured: these
numbers belong to that system, not to whatever runs today."""

import json

from ..data.config import ROOT

BENCH, LEARN = ROOT / "artifacts" / "benchmark", ROOT / "artifacts" / "learning"


def _latest(folder, pattern):
    files = [p for p in sorted(folder.glob(pattern)) if not p.name.endswith("_rows.json")]
    return (files[-1].name, json.loads(files[-1].read_text(encoding="utf-8"))) if files else (None, None)


def results():
    out = []
    f, d = _latest(BENCH, "exp011_2*.json")
    if d:
        out.append({"id": "EXP-011", "file": f, "measured_on": "single Planner, commit 61cc927, one run each", "world": d.get("world"), "summary": d["summary"]})
    f, d = _latest(BENCH, "exp011r_2*.json")
    if d:
        out.append({"id": "EXP-011R", "file": f, "measured_on": "single Planner on the shipped version, 3 repeats", "repeats": d["repeats"],
                    "pooled": d["pooled"], "replicated": d["replicated"]})
    for eid, pattern in (("EXP-012", "exp012_2*.json"), ("EXP-012b", "exp012b_2*.json")):
        f, d = _latest(BENCH, pattern)
        if d:
            out.append({"id": eid, "file": f, "measured_on": "single Planner; tool candidates at the old threshold of 2 requests (now 3, D-045)",
                        "arms": d.get("arms"), "decision": d.get("decision")})
    for eid, pattern in (("EXP-009", "exp009_2*.json"), ("EXP-009b", "exp009b_2*.json")):
        f, d = _latest(LEARN, pattern)
        if d:
            out.append({"id": eid, "file": f, "measured_on": "lesson mining against the generator's hidden rules", "pooled": d["primary_fresh_world"]["pooled"]})
    return out
