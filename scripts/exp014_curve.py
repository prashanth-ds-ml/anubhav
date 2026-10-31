"""EXP-014: does the whole team improve as it learns, and does each agent? Pre-registered in docs/trackers/experiments.md with
these files frozen by hash before any model call (D-044, D-046).

A world no earlier experiment used. The team, one repeat. Each stage adds one thing; test questions never reach a learning step.
  0 nothing learned · 1 approved lessons · 2 shared pack (new company) · 3 approved tools · 4 approved agent changes and knowledge
Each stage re-runs only what it can change; the rest carries forward, as registered.
Agents, directly on their own kind of question, before and after: Analyst, Tool Forge, Lesson Miner (hidden rules).

  uv run python scripts/exp014_curve.py --freeze
  uv run python scripts/exp014_curve.py [--resume STAMP]    # refuses if a frozen file changed; stops at the budget
"""

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.agents import forge, registry, team
from anubhav.data import generate
from anubhav.data.config import ROOT
from anubhav.eval import bench
from anubhav.harness import loop, practice
from anubhav.harness.store import HarnessStore, PatchError
from anubhav.learning import digest, evaluate, miner, newtools as nt, pack
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import sandbox
from anubhav.service import knowledge
from anubhav.trace import walk

SEED = 7919
OUT = ROOT / "artifacts" / "benchmark"
FROZEN = OUT / "exp014_frozen.json"
BUDGET_USD = 25.0
GAP_PER_TYPE = 4
FILES = ["scripts/exp014_curve.py", "configs/agents.yaml", "src/anubhav/agent/graph.py", "src/anubhav/agents/team.py", "src/anubhav/agents/forge.py", "src/anubhav/agents/registry.py",
         "src/anubhav/runtime/broker.py", "src/anubhav/harness/loop.py", "src/anubhav/harness/store.py", "src/anubhav/harness/practice.py", "src/anubhav/eval/bench.py",
         "src/anubhav/learning/newtools.py", "src/anubhav/service/knowledge.py"]
COMPANIES = ("T01", "T02", "TNEW")
UNWRITTEN, TRANSFER = {"site_access", "alias", "real_capacity"}, {"site_access", "alias"}
PATCHED = ("planner", "analyst", "tool_forge")


def hashes():
    return {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] for f in FILES}


def review_rule(S, company):                       # identical to EXP-011
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        strong = les["state"] == "CANDIDATE" and les["gate"].get("enforceable")
        S.approve(les["lesson_id"], "review-rule", "policy" if strong else "advisory", f"gate: {les['gate']['reason']}")


def rate(rows):
    return round(sum(x["ok"] for x in rows) / len(rows), 3) if rows else None


def stage_summary(name, rows):
    plan = [x for x in rows if x["kind"] == "plan"]
    gap = [x for x in rows if x["kind"] == "gap"]
    return {"stage": name, "n": len(rows), "correct": sum(x["ok"] for x in rows), "rate": rate(rows), "unsafe": sum(x["unsafe"] for x in rows),
            "plan": rate(plan), "gap": rate(gap), "unwritten": rate([x for x in plan if x["family"] in UNWRITTEN and x["company"] != "TNEW"]),
            "new_company": rate([x for x in plan if x["family"] in TRANSFER and x["company"] == "TNEW"]),
            "gap_mean_cost": round(sum(x["cost_usd"] for x in gap) / len(gap), 4) if gap else None, "gap_mean_calls": round(sum(x["calls"] for x in gap) / len(gap), 2) if gap else None,
            "learned_tool_used": sum(x["learned_used"] for x in gap), "rerun_cost": round(sum(x["cost_usd"] for x in rows if x["stage"] == name), 3)}


def decide(stages, agents, leaks, tools_made):
    """The pre-registered rules. Stage 0 has nothing learned, so safety is judged from stage 1 on (new company from stage 2)."""
    s = {x["stage"]: x for x in stages}
    if len(s) < 5:
        return {"complete": False}
    gain = lambda later, earlier, k: None if s[later][k] is None or s[earlier][k] is None else round(100 * (s[later][k] - s[earlier][k]), 1)
    out = {"complete": True, "S1_safety": all(s[k]["unsafe"] == 0 for k in ("s2_pack", "s3_tools", "s4_changes")), "lessons_gain_pts": gain("s1_lessons", "s0_cold", "unwritten"),
           "pack_gain_pts": gain("s2_pack", "s1_lessons", "new_company"), "pack_leaks": leaks, "tools_made": tools_made, "whole_system_gain_pts": gain("s4_changes", "s0_cold", "rate")}
    out["S2_lessons"] = (out["lessons_gain_pts"] or 0) >= 25
    out["S3_pack"] = (out["pack_gain_pts"] or 0) >= 25 and leaks == 0
    a, b = s["s3_tools"], s["s2_pack"]
    out["S4_tools"] = tools_made > 0 and a["learned_tool_used"] >= a["gap_n"] / 2 and (a["gap"] or 0) >= (b["gap"] or 0) and bool(b["gap_mean_cost"]) and a["gap_mean_cost"] <= 0.8 * b["gap_mean_cost"]
    up = [k for k, v in agents.items() if v.get("gain_pts") is not None and v["gain_pts"] > 0]
    out["agents_improved"] = up
    out["S5_changes"] = (s["s4_changes"]["rate"] or 0) >= (s["s3_tools"]["rate"] or 0) and bool(up)
    return out


class Run:
    """Rows on disk as they finish, a resume that re-uses them, and the budget stop."""

    def __init__(self, path, budget=BUDGET_USD):
        self.path, self.budget = path, budget
        self.done, self.spent = {}, 0.0
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                self.done[(r["stage"], r["id"])] = r
                self.spent += r.get("cost_usd", 0)

    def once(self, stage, id_, fn):
        if (stage, id_) in self.done:
            return self.done[(stage, id_)]
        row = {"stage": stage, "id": id_, **fn()}
        self.done[(stage, id_)] = row
        self.spent += row.get("cost_usd", 0)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        print(f"{stage:12} {id_:32} ok={row.get('ok')} {row.get('agents', '')} ${row.get('cost_usd', 0):.4f} total ${self.spent:.2f}", flush=True)
        if self.spent >= self.budget:
            raise SystemExit(f"budget of ${self.budget} reached at ${self.spent:.2f}: results are partial; --resume after deciding")
        return row


def experiment(world, out, client, spark, stamp, budget=BUDGET_USD):
    run = Run(out / f"exp014_{stamp}_rows.jsonl", budget)
    tmp = Path(tempfile.mkdtemp())
    S = LessonStore(out / f"exp014_{stamp}_lessons.sqlite")
    H = HarnessStore(out / f"exp014_{stamp}_harness.sqlite")
    view = {c: CompanyData(world, c, tmp / "view") for c in COMPANIES}
    roster = registry.load()
    cases = bench.build(world)
    held = {c: practice.build_gaps(view[c], per_type=GAP_PER_TYPE, split="held_out") for c in ("T01", "T02")}
    dev = {c: practice.build_gaps(view[c], per_type=GAP_PER_TYPE, split="dev") for c in ("T01", "T02")}
    tool_q = {c: practice.build(view[c], per_type=2, split="held_out") for c in ("T01", "T02")}
    print(f"{len(cases)} planning, {sum(map(len, held.values()))} gap test, {sum(map(len, dev.values()))} gap dev, {sum(map(len, tool_q.values()))} tool questions", flush=True)
    latest = {}
    state = {"lessons": False, "pack": False, "learned": {}, "harnesses": None, "knowledge": None}

    def plan(stage, case):
        cid = case["company"]

        def go():
            C, oid = bench.prepare(world, case, tmp / f"{stage}-{case['id']}")
            k, pol, adv = S.active_for(cid, view[cid]) if (state["lessons"] and cid != "TNEW") or (state["pack"] and cid == "TNEW") else ([], [], [])
            r = team.run(C, Session(cid, "dispatcher", "exp014"), client, bench.request(case, C), knowledge=k, policies=pol, advisories=adv, analysis=True, harnesses=state["harnesses"],
                         harness=(state["harnesses"] or {}).get("planner"), knowledge_by_agent=state["knowledge"], learned_tools=state["learned"].get(cid, ()))
            j = bench.judge(case, C, oid, r)
            return {"kind": "plan", "family": case["family"], "company": cid, "ok": j["ok"], "unsafe": j["unsafe"], "agents": [p.get("agent_id") for p in walk(r)], "calls": sum(p["tool_calls"] for p in walk(r)),
                    "learned_used": False, "stop": r["stop"], "cost_usd": r["cost_usd"], "run_id": r["run_id"], "reply": r["reply"][:300]}
        latest[case["id"]] = run.once(stage, case["id"], go)

    def gap(stage, cid, q, split="test"):
        def go():
            C = CompanyData(world, cid, tmp / f"{stage}-{cid}")
            learned = state["learned"].get(cid, ())
            r = team.run(C, Session(cid, "dispatcher", "exp014"), client, q["question"], analysis=True, harnesses=state["harnesses"], harness=(state["harnesses"] or {}).get("planner"),
                         knowledge_by_agent=state["knowledge"], learned_tools=learned)
            names = {t["name"] for t in learned}
            used = any(s["type"] == "tool" and s["name"] in names and s["ok"] for p in walk(r) for s in p["trace"])
            return {"kind": "gap", "family": q["type"], "company": cid, "ok": practice.score(q, r)["answer_ok"], "unsafe": False, "agents": [p.get("agent_id") for p in walk(r)],
                    "calls": sum(p["tool_calls"] for p in walk(r)), "learned_used": used, "stop": r["stop"], "cost_usd": r["cost_usd"], "run_id": r["run_id"], "reply": r["reply"][:300], "_run": r if split == "dev" else None}
        row = run.once(stage, q["id"], go)
        if split == "test":
            latest[q["id"]] = row
        return row

    stages = []

    def snapshot(name):
        rows = list(latest.values())
        s = stage_summary(name, rows)
        s["gap_n"] = sum(x["kind"] == "gap" for x in rows)
        stages.append(s)
        print("STAGE", json.dumps(s), flush=True)

    # ---------- stage 0: nothing learned
    for case in cases:
        plan("s0_cold", case)
    for cid, qs in held.items():
        for q in qs:
            gap("s0_cold", cid, q)
    snapshot("s0_cold")

    # ---------- agents at v0, directly on their own kind of question
    agents = {}

    def agent_score(agent, version, questions):
        rows = []
        for cid, qs in questions.items():
            for q in qs:
                def go(q=q, cid=cid):
                    C = CompanyData(world, cid, tmp / f"{agent}-{version}-{cid}")
                    x = practice.run_agent(C, client, [q], agent, state["harnesses"], state["knowledge"], state["learned"].get(cid, ()))[0]
                    return {"ok": bool(x["answer_ok"]), "calls": x["tool_calls"], "errors": x["tool_errors"], "cost_usd": x["cost_usd"], "agents": [agent]}
                rows.append(run.once(f"agent-{agent}-{version}", q["id"], go))
        s = {"n": len(rows), "correct": sum(x["ok"] for x in rows), "rate": rate(rows), "mean_calls": round(sum(x["calls"] for x in rows) / len(rows), 2) if rows else None,
             "tool_errors": sum(x["errors"] for x in rows), "cost_usd": round(sum(x["cost_usd"] for x in rows), 3)}
        H.add_score(agent, H.active(agent)["version_id"], f"exp014:{version}", s["n"], s["correct"], 0, sum(x["calls"] for x in rows), s["tool_errors"], s["cost_usd"])
        return s

    def miner_score(version):
        """The Lesson Miner agent on T01: its proposals, gated, against the generator's hidden rules. Its own store each time."""
        store = LessonStore(tmp / f"miner-{version}.sqlite")

        def go():
            C = CompanyData(world, "T01", tmp / f"miner-{version}")
            r = team.run(C, Session("T01", "dispatcher", "exp014"), client, team.MINE_BRIEF, lead_agent="lesson_miner", analysis=True, lesson_store=store,
                         harnesses=state["harnesses"], knowledge_by_agent=state["knowledge"])
            s = evaluate.score(evaluate.Truth(world), "T01", store.list("T01"))
            return {"ok": None, "precision": s["precision"], "recall": s["recall"], "proposed": s["proposed"], "passed": s["passed"], "traps_admitted": s["traps_admitted"], "stop": r["stop"], "cost_usd": r["cost_usd"], "agents": ["lesson_miner"]}
        return run.once(f"agent-lesson_miner-{version}", "T01", go)

    a0, f0, m0 = agent_score("analyst", "v0", tool_q), agent_score("tool_forge", "v0", held), miner_score("v0")

    # ---------- stage 1: lessons mined by Muse Spark 1.3 from the records, gated, approved by the fixed rule
    def mine_lessons():
        cost = 0.0
        for c in ("T01", "T02"):
            F, d = digest.build(view[c])
            props, meta = miner.mine(spark, view[c], d)
            S.add_proposals(c, F, props, meta)
            review_rule(S, c)
            cost += meta["cost_usd"]
        return {"cost_usd": cost, "kind": "mine"}
    run.once("learn", "mine_lessons", mine_lessons)
    state["lessons"] = True
    for case in [x for x in cases if x["company"] != "TNEW"]:
        plan("s1_lessons", case)
    snapshot("s1_lessons")

    # ---------- stage 2: the pack reaches the new company
    leaks = 0
    published = run.once("learn", "publish_packs", lambda: {"cost_usd": 0, "kind": "pack", "packs": [
        {"items": len(p["items"]), "leaks": len(pack.leaks(p, view[src], view["TNEW"])), "imported": len(pack.import_pack(S, p, view["TNEW"], accepted_by="owner-TNEW", accept_policies=True))}
        for src in ("T01", "T02") for p in [pack.publish(S, view[src], view["TNEW"], approved_by=f"owner-{src}")]]})
    leaks = sum(p["leaks"] for p in published["packs"])
    state["pack"] = True
    for case in [x for x in cases if x["company"] == "TNEW"]:
        plan("s2_pack", case)
    snapshot("s2_pack")

    # ---------- learning from the team's own runs, on dev questions only
    dev_runs = []
    for cid, qs in dev.items():
        for q in qs:
            dev_runs.append(gap("learn_dev", cid, q, split="dev").get("_run"))
    dev_runs = [r for r in dev_runs if r]

    # stage 3: reused queries become tools; Tool Forge names them; code checks; the fixed rule approves what passes
    def make_tools(cid):
        def go():
            sb, cost, made = sandbox(view[cid]), 0.0, []
            for g in nt.candidates(dev_runs, cid, sb):
                named = forge.name_tool(client, view[cid], g)
                cost += named["cost_usd"]
                checks = nt.check(g, sb)
                try:
                    tid = nt.propose(S, cid, g, checks, nt.free_name(S, cid, named["name"]), named["description"])
                except ValueError as e:
                    made.append({"refused": str(e)})
                    continue
                if checks["pass"]:
                    nt.decide(S, tid, "review-rule", True, "fixed rule: checks passed")
                made.append({"tool_id": tid, "name": named["name"], "named_by": named["named_by"], "passed": checks["pass"], "requests": len(g["requests"])})
            return {"cost_usd": cost, "kind": "tools", "made": made}
        return run.once("learn", f"tools_{cid}", go)
    tools_made = 0
    for cid in dev:
        tools_made += sum(1 for m in make_tools(cid)["made"] if m.get("passed"))
        state["learned"][cid] = nt.tools(S, cid, "active")
    for cid, qs in held.items():
        for q in qs:
            gap("s3_tools", cid, q)
    snapshot("s3_tools")

    # stage 4: one change per agent with problems (paired test scores right answers), and each agent's knowledge
    probe_cases = [{"request": q["question"], "company": "T01", "origin": "dev question", "expects_draft": False, "score": lambda r, q=q: practice.score(q, r)["answer_ok"]} for q in dev["T01"][:3]]
    b = Broker(view["T01"], Session("T01"), analysis=True, team=team.Team(roster, None))
    C = CompanyData(world, "T01", tmp / "probe")

    def patch_agent(agent):
        def go():
            problems = loop.collect(dev_runs, [], agent)
            if not problems["trace_issues"]:
                return {"cost_usd": 0, "kind": "patch", "agent": agent, "outcome": "no problems"}
            spec = roster.get(agent)
            patch, meta = loop.propose(spark, b, H.active(agent)["surfaces"], problems, "" if agent == "planner" else f"{spec.name}: {spec.purpose}")
            try:
                v = H.propose(patch, patch.get("rationale", ""), [t.name for t in b.list_tools()], view["T01"], agent)
            except (PatchError, KeyError, TypeError) as e:
                return {"cost_usd": meta["cost_usd"], "kind": "patch", "agent": agent, "outcome": f"refused: {e}", "patch": patch}
            res = loop.team_probe(C, client, spark, probe_cases, agent, H.get(v["parent"])["surfaces"], v["surfaces"], {}, lambda c: ([], [], []), H.active_all())
            cost = meta["cost_usd"] + sum(x["base"]["cost_usd"] + x["cand"]["cost_usd"] for x in res["rows"])
            H.record_probe(v["version_id"], res)
            H.decide(v["version_id"], "review-rule", res["gate"]["pass"], "fixed rule: approve what passes the paired test")
            return {"cost_usd": cost, "kind": "patch", "agent": agent, "version": v["version_id"], "patch": patch, "gate": res["gate"], "outcome": "activated" if res["gate"]["pass"] else "rejected"}
        return run.once("learn", f"patch_{agent}", go)
    patches = [patch_agent(a) for a in PATCHED]
    state["harnesses"] = H.active_all()
    state["knowledge"] = knowledge.build(dev_runs, view["T01"], S)
    for case in cases:
        plan("s4_changes", case)
    for cid, qs in held.items():
        for q in qs:
            gap("s4_changes", cid, q)
    snapshot("s4_changes")

    # ---------- agents after learning, on the same questions
    a1, f1, m1 = agent_score("analyst", "final", tool_q), agent_score("tool_forge", "final", held), miner_score("final")
    pts = lambda x, y: round(100 * (y["rate"] - x["rate"]), 1) if x["rate"] is not None and y["rate"] is not None else None
    fwd = [x for x in stages if x["stage"] == "s0_cold"][0], [x for x in stages if x["stage"] == "s1_lessons"][0], stages[-1]
    agents = {"planner": {"v0": {"unwritten": fwd[0]["unwritten"], "unsafe": fwd[0]["unsafe"]}, "with_lessons": {"unwritten": fwd[1]["unwritten"]}, "final": {"unwritten": fwd[2]["unwritten"], "unsafe": fwd[2]["unsafe"]},
                          "gain_pts": round(100 * ((fwd[2]["unwritten"] or 0) - (fwd[0]["unwritten"] or 0)), 1)},
              "analyst": {"v0": a0, "final": a1, "gain_pts": pts(a0, a1)}, "tool_forge": {"v0": f0, "final": f1, "gain_pts": pts(f0, f1), "tools_made": tools_made},
              "lesson_miner": {"v0": m0, "final": m1, "gain_pts": round(100 * ((m1.get("precision") or 0) - (m0.get("precision") or 0)), 1), "metric": "precision on T01's hidden rules"}}
    result = {"world": world.name, "stages": stages, "agents": agents, "learning": {"patches": patches, "tools_made": tools_made, "packs": published["packs"]},
              "decision": decide(stages, agents, leaks, tools_made), "cost_usd": round(run.spent, 3), "rows": [{k: v for k, v in r.items() if k != "_run"} for r in run.done.values()]}
    p = out / f"exp014_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result["decision"], indent=1), flush=True)
    print("saved", p.name, "total $", round(run.spent, 2), flush=True)
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--resume")
    a = ap.parse_args()
    if a.freeze:
        FROZEN.write_text(json.dumps(hashes(), indent=1), encoding="utf-8")
        print(json.dumps(hashes(), indent=1))
        return 0
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    changed = [f for f, h in hashes().items() if frozen.get(f) != h]
    if changed:
        raise SystemExit(f"refusing to run: frozen files changed: {changed}")
    world = ROOT / "data" / "worlds" / f"full_seed{SEED}"
    if not (world / "manifest.json").exists():
        assert generate.main(["--full", "--seed", str(SEED)]) == 0
    experiment(world, OUT, muse.client("open"), muse.client("spark"), a.resume or datetime.now().strftime("%Y%m%d_%H%M%S"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
