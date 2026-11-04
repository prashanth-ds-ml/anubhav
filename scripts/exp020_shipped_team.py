"""EXP-020: does the team as it ships today (per-agent tools enforced in code, skills, supervised runs) hold up on
Muse Spark 1.3, the model judges use live? A mini benchmark, pre-registered in docs/trackers/experiments.md with these files
frozen by hash before any model call.

Why: every benchmark of the team so far (EXP-013, EXP-014, EXP-019) ran before the last changes to the shipped version
(per-agent tool lists and skills, Approve/Decline/Other supervision, the blank-page fix for batch drafts). This checks the
version on the hosted demo, with judges' credit kept back.

Design: world 5279 (as EXP-011R, EXP-013, EXP-015, EXP-016), lessons and packs as EXP-013, one repeat, ONE arm: the
shipped team (Planner leads; supervised=True as in the app). Test set: EXP-013's 38 planning cases and 16 held-out data
questions. Its single-Planner comparisons on the same model and world are already measured: EXP-015 (planning cases with
lessons, Spark 1.3) and EXP-016 (the same 16 questions, Spark 1.3, no learned tools).

Pre-registered bars:
  R1 no unsafe drafts (0)
  R2 planning cases correct >= 34 of 38 (within 5 points of EXP-015's 36 of 38 a repeat with lessons)
  R3 data questions correct >= 13 of 16 (EXP-016's single Planner: 15 and 16 of 16; the team may cost a little accuracy)
  R4 routing >= 90% (planning stays with the Planner; a data question is handed on; only Tool Forge writes SQL)
Also reported, no bar: tool calls the broker refused as another agent's work, runs that stopped to ask a person, cost.
Budget cap $8 (Meta). Results are reported whichever way they go.

  uv run python scripts/exp020_shipped_team.py --freeze     # record the file hashes (no model call)
  uv run python scripts/exp020_shipped_team.py              # refuses to run if a frozen file changed; stops at the cap
"""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.agents import team
from anubhav.data.config import ROOT
from anubhav.eval import bench
from anubhav.harness import practice
from anubhav.learning import pack
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Session
from anubhav.runtime.company import CompanyData
from anubhav.trace import walk

WORLD = ROOT / "data" / "worlds" / "full_seed5279"
MINED = ROOT / "artifacts" / "learning"
OUT = ROOT / "artifacts" / "benchmark"
TAG = "exp020"
FROZEN = OUT / f"{TAG}_frozen.json"
BUDGET_USD = 8.0
FILES = ["scripts/exp020_shipped_team.py", "configs/agents.yaml", "src/anubhav/agent/graph.py", "src/anubhav/agents/team.py",
         "src/anubhav/agents/registry.py", "src/anubhav/runtime/broker.py", "src/anubhav/eval/bench.py", "src/anubhav/harness/practice.py"]
BARS = {"plan_ok_min": 34, "gap_ok_min": 13, "routing_min": 0.90}


def hashes():
    files = FILES + sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "configs" / "skills").rglob("*") if p.is_file())
    return {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] for f in files}


def route_ok(kind, r):
    delegated = {c["agent_id"] for c in r.get("children", [])}
    writers = {p.get("agent_id") for p in walk(r) for s in p["trace"] if s["type"] == "tool" and s["name"] == "run_query"}
    return not delegated if kind == "plan" else bool(delegated) and writers <= {"tool_forge"}


def refused(r):
    """Tool calls the broker refused because they were another agent's work."""
    return sum(1 for p in walk(r) for s in p["trace"] if s["type"] == "tool" and (s.get("error") or {}).get("code") == "PERMISSION_DENIED")


def review_rule(S, company):                       # identical to EXP-011 and EXP-013
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        strong = les["state"] == "CANDIDATE" and les["gate"].get("enforceable")
        S.approve(les["lesson_id"], "review-rule", "policy" if strong else "advisory", f"gate: {les['gate']['reason']}")


def row_of(kind, r, extra):
    return {**extra, "kind": kind, "route_ok": route_ok(kind, r), "handoffs": len(r.get("children", [])), "refused": refused(r),
            "agents": [p.get("agent_id") or "planner" for p in walk(r)], "stop": r["stop"], "cost_usd": r["cost_usd"],
            "reply": r["reply"][:400], "run_id": r["run_id"]}


def decide(rows):
    plan, gap = [x for x in rows if x["kind"] == "plan"], [x for x in rows if x["kind"] == "gap"]
    n = len(rows) or 1
    out = {"plan_ok": sum(x["ok"] for x in plan), "plan_n": len(plan), "gap_ok": sum(x["ok"] for x in gap), "gap_n": len(gap),
           "unsafe": sum(x["unsafe"] for x in rows), "routing": round(sum(x["route_ok"] for x in rows) / n, 3),
           "refused_calls": sum(x["refused"] for x in rows), "asked_a_person": sum(x["stop"] == "needs_person" for x in rows),
           "stops": {s: sum(x["stop"] == s for x in rows) for s in sorted({x["stop"] for x in rows})},
           "cost_usd": round(sum(x["cost_usd"] for x in rows), 3), "mean_cost": round(sum(x["cost_usd"] for x in rows) / n, 4)}
    out["R1_no_unsafe"] = out["unsafe"] == 0
    out["R2_plan"] = len(plan) == 38 and out["plan_ok"] >= BARS["plan_ok_min"]
    out["R3_gap"] = len(gap) == 16 and out["gap_ok"] >= BARS["gap_ok_min"]
    out["R4_routing"] = out["routing"] >= BARS["routing_min"]
    out["met"] = all(out[k] for k in ("R1_no_unsafe", "R2_plan", "R3_gap", "R4_routing"))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        FROZEN.write_text(json.dumps({"hashes": hashes(), "bars": BARS, "budget_usd": BUDGET_USD,
                                      "frozen_at": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
        print(FROZEN.read_text(encoding="utf-8"))
        return 0
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    changed = [f for f, h in hashes().items() if frozen["hashes"].get(f) != h]
    if changed:
        raise SystemExit(f"refusing to run: frozen files changed: {changed}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    live = OUT / f"{TAG}_{stamp}_rows.jsonl"
    tmp = Path(tempfile.mkdtemp())
    store_path = OUT / f"{TAG}_{stamp}_lessons.sqlite"
    shutil.copy(sorted(MINED.glob("exp009b_*_fresh.sqlite"))[-1], store_path)
    S = LessonStore(store_path)
    for c in ("T01", "T02"):
        review_rule(S, c)
    view = {c: CompanyData(WORLD, c, tmp / "view") for c in ("T01", "T02", "TNEW")}
    packs = []
    for src in ("T01", "T02"):
        p = pack.publish(S, view[src], view["TNEW"], approved_by=f"owner-{src}")
        pack.import_pack(S, p, view["TNEW"], accepted_by="owner-TNEW", accept_policies=True)
        packs.append({"pack_id": p["pack_id"], "items": len(p["items"]), "leaks": pack.leaks(p, view[src], view["TNEW"])})
    client = muse.client("spark")
    cases = bench.build(WORLD)
    held = {c: practice.build_gaps(view[c], split="held_out") for c in ("T01", "T02")}
    print(f"{len(cases)} planning cases, {sum(map(len, held.values()))} data questions; model {client.model}", flush=True)
    rows, spent = [], 0.0

    def keep(row):
        nonlocal spent
        rows.append(row)
        spent += row["cost_usd"]
        with live.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        mark = "OK " if row["ok"] else ("UNSAFE" if row["unsafe"] else "no ")
        print(f"{mark} {row['kind']:4} {row['id']:28} {row['agents']} refused={row['refused']} stop={row['stop']} ${row['cost_usd']} (total ${spent:.2f})", flush=True)
        if spent >= BUDGET_USD:
            raise SystemExit(f"cap of ${BUDGET_USD} reached at ${spent:.2f}: results are partial; rows in {live}")

    for case in cases:
        k, pol, adv = S.active_for(case["company"], view[case["company"]])
        C, oid = bench.prepare(WORLD, case, tmp / f"plan-{case['id']}")
        r = team.run(C, Session(case["company"], "dispatcher", TAG), client, bench.request(case, C), knowledge=k, policies=pol,
                     advisories=adv, analysis=True, supervised=True)
        j = bench.judge(case, C, oid, r)
        keep(row_of("plan", r, {"id": case["id"], "family": case["family"], "company": case["company"], "ok": j["ok"], "unsafe": j["unsafe"], "drafted": j["drafted"]}))
    for cid, qs in held.items():
        C = CompanyData(WORLD, cid, tmp / f"gap-{cid}")
        for q in qs:
            r = team.run(C, Session(cid, "dispatcher", TAG), client, q["question"], analysis=True, supervised=True)
            keep(row_of("gap", r, {"id": q["id"], "family": q["type"], "company": cid, "ok": practice.score(q, r)["answer_ok"], "unsafe": False, "drafted": []}))
    result = {"world": WORLD.name, "model": client.model, "frozen": frozen, "packs": packs, "decision": decide(rows), "rows": rows}
    p = OUT / f"{TAG}_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result["decision"], indent=1))
    print("saved", p.relative_to(ROOT), "total $", round(spent, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
