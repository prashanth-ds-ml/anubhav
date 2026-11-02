"""The measured results for the Proof page, read from the committed result files. Each says what it measured: these
numbers belong to that system, not to whatever runs today."""

import json

from ..data.config import ROOT

BENCH, LEARN = ROOT / "artifacts" / "benchmark", ROOT / "artifacts" / "learning"
BASELINE = ROOT / "archive" / "prototype_experiments" / "artifacts" / "baseline"
REGISTRY = ROOT / "artifacts" / "experiments_index.json"


def _latest(folder, pattern):
    files = [p for p in sorted(folder.glob(pattern)) if not p.name.endswith("_rows.json")]
    return (files[-1].name, json.loads(files[-1].read_text(encoding="utf-8"))) if files else (None, None)


def _arm(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    s = d["summary"]
    return {"arm": d["arm"], "model": d.get("model"), "runs": s["runs"], "mean_success": s["mean_success"], "mean_latency_s": s["mean_latency_s"],
            "mean_tool_calls": s["mean_tool_calls"], "cost_usd": s["cost_usd"], "file": path.name}


def open_weights():
    """EXP-004: Muse Spark Open (open weights, Baseten) against Muse Spark 1.3 on the same 48 tool-calling tasks, 2 repeats."""
    pairs = [("core", "arm-core_2*.json", "arm-core_baseten_*.json"), ("A", "arm-a_2*.json", "arm-a_baseten_*.json")]
    rows = []
    for arm, spark, open_ in pairs:
        s, o = sorted(BASELINE.glob(spark)), sorted(BASELINE.glob(open_))
        if s and o:
            rows.append({"arm": arm, "tools": 8 if arm == "core" else 40, "spark_1_3": _arm(s[-1]), "spark_open": _arm(o[-1])})
    return rows


def mining_demo():
    """EXP-008: lesson mining on the demo world, per company and repeat, pooled."""
    f, d = _latest(LEARN, "exp008_2*.json")
    if not d:
        return None
    reps = {}
    for key, v in d["A"].items():
        r = reps.setdefault(key.split("#")[-1], {"passed": 0, "true_passed": 0, "found": 0, "learnable": 0, "traps_admitted": 0})
        r["passed"] += v["passed"]
        r["true_passed"] += v["passed"] - len(v["false_lessons"])
        r["found"] += len(v["found"])
        r["learnable"] += len(v["learnable"])
        r["traps_admitted"] += len(v["traps_admitted"])
    tot = {k: sum(r[k] for r in reps.values()) for k in ("passed", "true_passed", "found", "learnable", "traps_admitted")}
    score = lambda r: {**r, "precision": round(r["true_passed"] / r["passed"], 3) if r["passed"] else None,
                       "recall": round(r["found"] / r["learnable"], 3) if r["learnable"] else None}
    return {"file": f, "repeats": [score(r) for _, r in sorted(reps.items())], "pooled": score(tot)}


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"experiments": []}


def results():
    out = []
    ow = open_weights()
    if ow:
        out.append({"id": "EXP-004", "file": ow[0]["spark_open"]["file"], "measured_on": "48 tool-calling tasks, 2 repeats (96 runs an arm), before the logistics world existed", "arms": ow})
    m = mining_demo()
    if m:
        out.append({"id": "EXP-008", "file": m["file"], "measured_on": "lesson mining by Muse Spark 1.3 on the demo world, against the generator's hidden rules, 2 repeats",
                    "repeats": m["repeats"], "pooled": m["pooled"]})
    f, d = _latest(BENCH, "exp011_2*.json")
    if d:
        out.append({"id": "EXP-011", "file": f, "measured_on": "single Planner, commit 61cc927, one run each", "world": d.get("world"), "summary": d["summary"]})
    f, d = _latest(BENCH, "exp011r_2*.json")
    if d:
        out.append({"id": "EXP-011R", "file": f, "measured_on": "single Planner on the shipped version, 3 repeats", "repeats": d["repeats"],
                    "pooled": d["pooled"], "replicated": d["replicated"], "summary": d.get("summary"), "world": d.get("world"),
                    "cost_usd": d.get("cost_usd"), "runs": len(d.get("rows", [])), "pack_leaks": sum(len(k.get("leaks", [])) for k in d.get("packs", []))})
    for eid, pattern in (("EXP-012", "exp012_2*.json"), ("EXP-012b", "exp012b_2*.json")):
        f, d = _latest(BENCH, pattern)
        if d:
            out.append({"id": eid, "file": f, "measured_on": "single Planner; tool candidates at the old threshold of 2 requests (now 3, D-045)",
                        "arms": d.get("arms"), "decision": d.get("decision")})
    f, d = _latest(BENCH, "exp013_2*.json")
    if d:
        out.append({"id": "EXP-013", "file": f, "measured_on": "single Planner vs the team, one repeat, 54 cases; learning-round patches approved by a fixed rule in the experiment's own store",
                    "decision": d["decision"], "learning_round": d["learning_round"], "cost_usd": d["cost_usd"]})
    for eid, pattern in (("EXP-009", "exp009_2*.json"), ("EXP-009b", "exp009b_2*.json")):
        f, d = _latest(LEARN, pattern)
        if d:
            out.append({"id": eid, "file": f, "measured_on": "lesson mining against the generator's hidden rules", "pooled": d["primary_fresh_world"]["pooled"]})
    return out


def curve():
    f, d = _latest(BENCH, "exp014_2*.json")
    if not d:
        return {"measured": False, "note": "EXP-014 has not run yet"}
    return {"measured": True, "file": f, "stages": d["stages"], "agents": d["agents"], "decision": d["decision"], "cost_usd": d["cost_usd"]}

