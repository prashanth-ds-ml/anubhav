"""EXP-013: does the team work as well as the single Planner, and does one round of per-agent learning help? Pre-registered in
docs/trackers/experiments.md with these files frozen by hash before any model call (D-044, design v1 §4.4).

World 5279, the same model (Muse Spark Open), lessons and packs as EXP-011R, so arm S compares directly. One repeat.
Arms on the test set: S single Planner · M0 team at v0 · M1 team after one learning round.
Test set: the 38 planning cases (with lessons or pack) and the held-out gap questions (T01, T02).
Learning round (on separate dev questions, never the test set): run the team, collect each agent's problems, Muse Spark 1.3
proposes one patch per agent with problems, the paired test decides, and a fixed rule approves what passes.

  uv run python scripts/exp013_team.py --freeze     # record the file hashes (no model call)
  uv run python scripts/exp013_team.py              # refuses to run if a frozen file changed; stops at the budget
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
from anubhav.agent import graph
from anubhav.agents import team
from anubhav.data.config import ROOT
from anubhav.eval import bench
from anubhav.harness import loop, practice
from anubhav.harness.store import HarnessStore, PatchError
from anubhav.learning import pack
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.trace import walk

WORLD = ROOT / "data" / "worlds" / "full_seed5279"
MINED = ROOT / "artifacts" / "learning"
OUT = ROOT / "artifacts" / "benchmark"
FROZEN = OUT / "exp013_frozen.json"
BUDGET_USD = 30.0
FILES = ["scripts/exp013_team.py", "configs/agents.yaml", "src/anubhav/agent/graph.py", "src/anubhav/agents/team.py", "src/anubhav/agents/registry.py",
         "src/anubhav/runtime/broker.py", "src/anubhav/harness/loop.py", "src/anubhav/harness/store.py", "src/anubhav/harness/practice.py", "src/anubhav/eval/bench.py"]
AGENTS = ("planner", "analyst", "tool_forge")


def hashes():
    return {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] for f in FILES}


def route_ok(kind, r):
    """Did the work go to the right place? A planning case stays with the Planner; a gap question goes to a teammate, and any
    new query is written by Tool Forge."""
    delegated = {c["agent_id"] for c in r.get("children", [])}
    writers = {p.get("agent_id") for p in walk(r) for s in p["trace"] if s["type"] == "tool" and s["name"] == "run_query"}
    if kind == "plan":
        return not delegated
    return bool(delegated) and writers <= {"tool_forge"}


def row_stats(rows):
    n = len(rows) or 1
    return {"n": len(rows), "ok": sum(x["ok"] for x in rows), "ok_rate": round(sum(x["ok"] for x in rows) / n, 3), "unsafe": sum(x["unsafe"] for x in rows),
            "mean_cost": round(sum(x["cost_usd"] for x in rows) / n, 4), "cost_usd": round(sum(x["cost_usd"] for x in rows), 3),
            "routing": round(sum(x["route_ok"] for x in rows) / n, 3), "handoffs": sum(x["handoffs"] for x in rows),
            "stopped_at_limit": sum(x["stop"] == "limit" for x in rows)}


def decide(rows):
    """The pre-registered rules."""
    arm = lambda a: [x for x in rows if x["arm"] == a]
    s, m0, m1 = row_stats(arm("S")), row_stats(arm("M0")), row_stats(arm("M1"))
    out = {"S": s, "M0": m0, "M1": m1, "by_kind": {f"{a}:{k}": row_stats([x for x in arm(a) if x["kind"] == k]) for a in ("S", "M0", "M1") for k in ("plan", "gap")}}
    out["R1_no_unsafe"] = m0["unsafe"] == 0 and (not m1["n"] or m1["unsafe"] == 0)
    out["R2_not_worse"] = m0["ok_rate"] >= s["ok_rate"] - 0.05
    out["R3_cost"] = bool(s["mean_cost"]) and m0["mean_cost"] <= 1.5 * s["mean_cost"]
    out["R4_routing_gain_pts"] = round(100 * (m1["routing"] - m0["routing"]), 1) if m1["n"] else None
    out["R4_met"] = bool(m1["n"]) and m1["routing"] - m0["routing"] >= 0.15
    out["team_becomes_default"] = out["R1_no_unsafe"] and out["R2_not_worse"] and out["R3_cost"]
    return out


def review_rule(S, company):                       # identical to EXP-011
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        strong = les["state"] == "CANDIDATE" and les["gate"].get("enforceable")
        S.approve(les["lesson_id"], "review-rule", "policy" if strong else "advisory", f"gate: {les['gate']['reason']}")


class Spend:
    def __init__(self, live):
        self.total, self.live = 0.0, live

    def add(self, row):
        self.total += row.get("cost_usd", 0)
        with self.live.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        if self.total >= BUDGET_USD:
            raise SystemExit(f"budget of ${BUDGET_USD} reached at ${self.total:.2f}: results are partial; rows in {self.live}")


def plan_case(case, client, arm, knowledge, pol, adv, rt, harnesses=None):
    C, oid = bench.prepare(WORLD, case, rt)
    req = bench.request(case, C)
    if arm == "S":
        r = graph.run(Broker(C, Session(case["company"], "dispatcher", "exp013"), pol, adv, analysis=True), client, req, knowledge=knowledge)
    else:
        r = team.run(C, Session(case["company"], "dispatcher", "exp013"), client, req, knowledge=knowledge, policies=pol, advisories=adv, analysis=True,
                     harnesses=harnesses, harness=(harnesses or {}).get("planner"))
    j = bench.judge(case, C, oid, r)
    return {"id": case["id"], "kind": "plan", "family": case["family"], "company": case["company"], "arm": arm, "ok": j["ok"], "unsafe": j["unsafe"], "drafted": j["drafted"],
            "route_ok": route_ok("plan", r), "handoffs": len(r.get("children", [])), "agents": [p.get("agent_id") or "planner" for p in walk(r)], "stop": r["stop"],
            "cost_usd": r["cost_usd"], "reply": r["reply"][:400], "run_id": r["run_id"]}


def gap_case(q, C, client, arm, harnesses=None):
    if arm == "S":
        r = graph.run(Broker(C, Session(C.company, "dispatcher", "exp013"), analysis=True), client, q["question"])
    else:
        r = team.run(C, Session(C.company, "dispatcher", "exp013"), client, q["question"], analysis=True, harnesses=harnesses, harness=(harnesses or {}).get("planner"))
    return r, {"id": q["id"], "kind": "gap", "family": q["type"], "company": C.company, "arm": arm, "ok": practice.score(q, r)["answer_ok"], "unsafe": False, "drafted": [],
               "route_ok": route_ok("gap", r), "handoffs": len(r.get("children", [])), "agents": [p.get("agent_id") or "planner" for p in walk(r)], "stop": r["stop"],
               "cost_usd": r["cost_usd"], "reply": r["reply"][:400], "run_id": r["run_id"]}


def learning_round(client, spark, H, gaps, spend, tmp):
    """One round on dev questions: team runs -> each agent's problems -> one patch per agent -> paired test -> fixed rule."""
    runs, report = [], []
    for cid, qs in gaps.items():
        C = CompanyData(WORLD, cid, tmp / f"dev-{cid}")
        for q in qs:
            r, row = gap_case(q, C, client, "M0")
            runs.append(r)
            spend.add({**row, "arm": "dev", "phase": "learning"})
    C = CompanyData(WORLD, "T01", tmp / "probe")
    b = Broker(C, Session("T01"), analysis=True, team=team.Team(team.registry.load(), None))
    specs = team.registry.load()
    cases = [{"request": q["question"], "company": cid, "origin": "dev question", "expects_draft": False} for cid, qs in gaps.items() for q in qs[:2] if cid == "T01"]
    for agent in AGENTS:
        problems = loop.collect(runs, [], agent)
        if not problems["trace_issues"]:
            report.append({"agent": agent, "outcome": "no problems"})
            continue
        spec = specs.get(agent)
        patch, meta = loop.propose(spark, b, H.active(agent)["surfaces"], problems, "" if agent == "planner" else f"{spec.name}: {spec.purpose}")
        spend.add({"phase": "learning", "arm": "propose", "agent": agent, "cost_usd": meta["cost_usd"]})
        try:
            v = H.propose(patch, patch.get("rationale", ""), [t.name for t in b.list_tools()], C, agent)
        except (PatchError, KeyError, TypeError) as e:
            report.append({"agent": agent, "outcome": f"patch refused: {e}", "patch": patch})
            continue
        res = loop.team_probe(C, client, spark, [c for c in cases], agent, H.get(v["parent"])["surfaces"], v["surfaces"], {}, lambda c: ([], [], []), H.active_all())
        for x in res["rows"]:
            spend.add({"phase": "learning", "arm": "probe", "agent": agent, "cost_usd": x["base"]["cost_usd"] + x["cand"]["cost_usd"]})
        H.record_probe(v["version_id"], res)
        passed = res["gate"]["pass"]
        H.decide(v["version_id"], "review-rule", passed, "fixed rule: approve what passes the paired test")
        report.append({"agent": agent, "version": v["version_id"], "patch": patch, "gate": res["gate"], "outcome": "activated" if passed else "rejected"})
    return report


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        FROZEN.write_text(json.dumps(hashes(), indent=1), encoding="utf-8")
        print(json.dumps(hashes(), indent=1))
        return 0
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    changed = [f for f, h in hashes().items() if frozen.get(f) != h]
    if changed:
        raise SystemExit(f"refusing to run: frozen files changed: {changed}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    live = OUT / f"exp013_{stamp}_rows.jsonl"
    spend = Spend(live)
    tmp = Path(tempfile.mkdtemp())
    store_path = OUT / f"exp013_{stamp}_lessons.sqlite"
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
    client, spark = muse.client("open"), muse.client("spark")
    cases = bench.build(WORLD)
    held = {c: practice.build_gaps(view[c], split="held_out") for c in ("T01", "T02")}
    dev = {c: practice.build_gaps(view[c], split="dev") for c in ("T01", "T02")}
    print(f"{len(cases)} planning cases, {sum(map(len, held.values()))} gap questions, {sum(map(len, dev.values()))} dev questions", flush=True)
    H = HarnessStore(OUT / f"exp013_{stamp}_harness.sqlite")
    rows, report = [], None

    def arm_pass(arm, harnesses=None):
        for case in cases:
            k, pol, adv = S.active_for(case["company"], view[case["company"]])
            row = plan_case(case, client, arm, k, pol, adv, tmp / f"{arm}-{case['id']}", harnesses)
            rows.append(row)
            spend.add(row)
            print(f"{'OK ' if row['ok'] else ('UNSAFE' if row['unsafe'] else 'no ')} {arm} {row['id']:28} {row['agents']} ${row['cost_usd']}", flush=True)
        for cid, qs in held.items():
            C = CompanyData(WORLD, cid, tmp / f"{arm}-gap-{cid}")
            for q in qs:
                _, row = gap_case(q, C, client, arm, harnesses)
                rows.append(row)
                spend.add(row)
                print(f"{'OK ' if row['ok'] else 'no '} {arm} {row['id']:28} {row['agents']} ${row['cost_usd']}", flush=True)
        print(arm, json.dumps(row_stats([x for x in rows if x["arm"] == arm])), f"total ${spend.total:.2f}", flush=True)

    arm_pass("S")
    arm_pass("M0")
    report = learning_round(client, spark, H, dev, spend, tmp)
    print("learning round:", json.dumps(report, ensure_ascii=False, default=str)[:1500], flush=True)
    if any(x["outcome"] == "activated" for x in report):
        arm_pass("M1", H.active_all())
    else:                   # nothing changed, so M1 would be M0 again: not run, and said so
        print("no patch passed: M1 is M0, not re-run", flush=True)
    result = {"world": WORLD.name, "frozen": frozen, "packs": packs, "learning_round": report, "decision": decide(rows), "cost_usd": round(spend.total, 3), "rows": rows}
    p = OUT / f"exp013_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result["decision"], indent=1))
    print("saved", p.relative_to(ROOT), "total $", round(spend.total, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
