"""EXP-019: EXP-016's learned-tools protocol, asked through the TEAM (pre-registered 2026-11-04 before any model call).

EXP-016 (Muse Spark 1.3, single Planner with run_query) made no learned tool, so none was used (0 of 16). The $0.98
diagnostic of 2026-11-03 found why: Spark 1.3 wrote a different query shape for each request, so no query served 3
different requests. Commit b9d2f03 gives each agent its own tools, enforced in code: in a team the Planner has no
run_query, the Analyst no SQL, and only Tool Forge writes queries, told to write ONE aggregated query with the town and
dates as inputs (and its skills: write-one-query, debug-sql). This asks: does Spark 1.3, through the team, now make
learned tools, use them, and need fewer calls?

Everything but the agent is EXP-016's: world 5279, T01 and T02, the same dev (learning) and held-out gap questions in
the same order, learn on dev in the query arm, candidates from code (3+ different requests), the same code checks and
the same fixed approval rule (approved when the checks pass), test arms Q (team, no learned tools) and T (team + the
approved learned tools). The same answer checker (practice.score, which reads the lead and every teammate) and the
same bars. Tool repair (forge.repair_tool) is NOT used: a candidate that fails its checks stays rejected.

Each question is one team request, the way the app runs it (service/runs.run_with, team=True): team.run with the
Planner as lead, delegation on, analysis on, the learned tools given to the broker. What the app adds per visitor is
left out, as in every frozen experiment: no lessons or knowledge, no harness, no per-agent knowledge, no business
profile, no history, unsupervised (supervised runs stop for a person; there is none here).

  baseten_api_key= uv run python scripts/exp019_team_tools.py --freeze     # write the frozen plan + hashes, no model call
  baseten_api_key= uv run python scripts/exp019_team_tools.py --smoke      # 1 team request (T01's first dev question)
  baseten_api_key= uv run python scripts/exp019_team_tools.py              # the run; stops inside the $6.00 total cap
"""

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp_freeze  # noqa: E402

from anubhav import muse, trace  # noqa: E402
from anubhav.agents import team  # noqa: E402
from anubhav.data.config import ROOT  # noqa: E402
from anubhav.harness import practice  # noqa: E402
from anubhav.learning import newtools as nt  # noqa: E402
from anubhav.learning.store import LessonStore  # noqa: E402
from anubhav.runtime.broker import Session  # noqa: E402
from anubhav.runtime.company import CompanyData  # noqa: E402
from anubhav.runtime.query import sandbox  # noqa: E402

TAG = "exp019"
SCRIPT = "scripts/exp019_team_tools.py"
MODEL_KEY = "spark"                 # Muse Spark 1.3 on the Meta API; never Baseten
WORLD = ROOT / "data" / "worlds" / "full_seed5279"
COMPANIES = ("T01", "T02")
CAP_USD = 6.00                      # total Meta spend for EXP-019, smoke included
RESERVE_USD = 0.45                  # the most one team request can cost: the team cap ($0.40) plus one model call
OUT = ROOT / "artifacts" / "benchmark"
EXTRA = ["src/anubhav/runtime/query.py", "src/anubhav/trace.py", "src/anubhav/learning/store.py",
         "src/anubhav/runtime/company.py", "src/anubhav/service/runs.py"]

PLAN = {
    "id": "EXP-019",
    "question": "With commit b9d2f03 (each agent its own tools, enforced in code; only Tool Forge writes SQL, told to write "
                "one aggregated query with town and dates as inputs; agent skills), does Muse Spark 1.3 asked through the "
                "team make learned tools, use them, and need fewer tool calls? EXP-016 (single Planner) made none (0 of 16 used).",
    "model": "Muse Spark 1.3 on the Meta API (model key 'spark', muse-spark-1.3), default sampling as EXP-016; no Baseten call "
             "(the script refuses to start if baseten_api_key is set)",
    "protocol": "EXP-016's (scripts/exp012b_new_tools.py) in everything but the agent: world full_seed5279, T01 then T02; "
                "practice.build_gaps dev (10 per company, learning) and held_out (8 per company, test) in the same order; "
                "learning in the query arm; newtools.candidates (3+ different requests), newtools.check, the same fixed "
                "approval rule (approved when the checks pass; a name still carrying a source value is skipped); "
                "practice.score as the answer checker. Tool repair is not used.",
    "agent": "every question is one team request: team.run(C, Session(cid,'dispatcher','exp019'), client, question, "
             "learned_tools=...) with the roster from configs/agents.yaml (Planner lead, delegation on, analysis on); "
             "no lessons, no knowledge, no harness, no per-agent knowledge, no profile, no history, unsupervised",
    "arms": {"Q": "team, no learned tools", "T": "team + the company's approved learned tools (given to the broker, so the "
             "Planner and Analyst can call them)"},
    "measures": "per question: answer_ok, total tool calls (lead + every teammate), lead calls, delegations, learned tool "
                "used, cost; per company: queries written (by agent), candidate groups and each group's number of "
                "different requests, candidates, checks passed, tools made",
    "bar": {
        "R2": "learned tools cheaper and not worse (EXP-016's): pooled over 16 held-out questions, T mean total tool calls "
              "<= 0.7 x Q mean total tool calls, and T right >= Q right - 1",
        "R2b": "learned tools used (EXP-016's): T calls a learned tool on at least half of its held-out questions (>= 8 of 16)",
        "S1_secondary": ">= 1 learned tool made (approved by the fixed rule) over T01 and T02",
    },
    "reported_not_judged": "per company results; candidate group sizes against the 2026-11-03 diagnostic (single Planner, "
                           "Spark 1.3: T01 14 groups, largest 2 requests, 0 candidates; T02 14 groups, largest 3, 1 "
                           "candidate passing); EXP-016's single-Planner Q and T next to these (3.25 and 3.38 calls, "
                           "15/16 and 16/16 right, $0.040 and $0.042 a question)",
    "repeats": 1,
    "budget": "hard cap $6.00 total Meta spend, smoke included: 1 smoke request (T01's first dev question, query arm, not "
              "part of the result) then the run, which stops before any request when spent + $0.45 would pass what is "
              "left of the cap",
    "partial": "if the cap stops the run, bars are computed only over held-out questions with both arms done, and the "
               "result is labelled partial",
    "caveats": "one run per question; the same questions as EXP-012b/EXP-016, so not unseen and a third attempt on them; "
               "team runs differ from EXP-016 in more than the tool routing (delegation overhead, skills, retry cap); "
               "the fixed rule stands in for a person's approval; code changed since EXP-016 (the diagnostic's detection "
               "fix in newtools.py and broker.py), so a change in tools made is not only the team's doing.",
}


def file_hashes():
    h = exp_freeze.hashes(SCRIPT)
    skills = sorted(p for p in (ROOT / "configs" / "skills").rglob("*") if p.is_file())
    for f in EXTRA + [p.relative_to(ROOT).as_posix() for p in skills]:
        h[f] = hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]
    return h


def plan_sha():
    return hashlib.sha256(json.dumps(PLAN, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def freeze():
    doc = dict(file_hashes()) | {"plan": PLAN, "plan_sha256": plan_sha(), "frozen_at": datetime.now().isoformat(timespec="seconds")}
    exp_freeze.path(TAG).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def check():
    p = exp_freeze.path(TAG)
    if not p.exists():
        sys.exit(f"refusing to run: {p.name} is missing; pre-register and freeze first")
    frozen = json.loads(p.read_text(encoding="utf-8"))
    now = file_hashes()
    changed = [f for f in set(now) | {k for k in frozen if k not in ("plan", "plan_sha256", "frozen_at")} if frozen.get(f) != now.get(f)]
    if changed:
        sys.exit(f"refusing to run: frozen files changed: {sorted(changed)}")
    if json.dumps(frozen.get("plan"), sort_keys=True, ensure_ascii=False) != json.dumps(PLAN, sort_keys=True, ensure_ascii=False):
        sys.exit("refusing to run: the plan differs from the frozen plan")


def no_baseten():
    if os.environ.get("baseten_api_key", "").strip() or os.environ.get("BASETEN_API_KEY", "").strip():
        sys.exit("refusing to run: baseten_api_key is set; run with `baseten_api_key= uv run python ...` (Meta API only)")


def ask(C, client, q, learned=()):
    r = team.run(C, Session(C.company, "dispatcher", "exp019"), client, q["question"], learned_tools=learned)
    trace.save(r, label=f"{TAG}:{MODEL_KEY}")
    s = practice.score(q, r)
    parts = list(trace.walk(r))
    names = {x["name"] for x in learned}
    row = {**{k: q[k] for k in ("id", "company", "type", "lang", "question")},
           **{k: s[k] for k in ("answer_ok", "right_tool", "tools", "cost_usd")},
           "tool_calls": sum(p.get("tool_calls", 0) for p in parts), "lead_calls": r["tool_calls"],
           "delegations": [p.get("agent_id") for p in parts[1:]],
           "run_query_by": [s_.get("agent_id") for p in parts for s_ in p["trace"] if s_.get("type") == "tool" and s_.get("name") == "run_query"],
           "used_learned": [t for t in s["tools"] if t in names],
           "stop": r["stop"], "reply": (r["reply"] or "")[:400], "run_id": r["run_id"]}
    return r, row


def stats(rows):
    n = len(rows) or 1
    return {"n": len(rows), "answer_ok": round(sum(x["answer_ok"] for x in rows) / n, 3), "right": sum(x["answer_ok"] for x in rows),
            "mean_tool_calls": round(sum(x["tool_calls"] for x in rows) / n, 2),
            "mean_lead_calls": round(sum(x["lead_calls"] for x in rows) / n, 2),
            "mean_cost": round(sum(x["cost_usd"] for x in rows) / n, 4), "cost_usd": round(sum(x["cost_usd"] for x in rows), 3),
            "learned_used": sum(bool(x["used_learned"]) for x in rows)}


def smoke_spent():
    return round(sum(json.loads(p.read_text(encoding="utf-8"))["cost_usd"] for p in OUT.glob(f"{TAG}_smoke_*.json")), 4)


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true", help="write exp019_frozen.json (hashes + plan) and exit; no model call")
    ap.add_argument("--smoke", action="store_true", help="one team request (T01's first dev question); counts toward the cap")
    a = ap.parse_args()
    no_baseten()
    if a.freeze:
        doc = freeze()
        print(json.dumps({k: v for k, v in doc.items() if k != "plan"}, indent=1))
        return
    check()
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    client, tmp = muse.client(MODEL_KEY), Path(tempfile.mkdtemp())
    if client.model != muse.DEFAULT_MODEL:
        sys.exit(f"refusing to run: model {client.model} is not {muse.DEFAULT_MODEL}")
    prior = smoke_spent()
    if a.smoke:
        if prior + RESERVE_USD > CAP_USD:
            sys.exit("refusing: the cap is used up")
        C = CompanyData(WORLD, "T01", tmp / "T01")
        q = practice.build_gaps(C, split="dev")[0]
        r, row = ask(C, client, q)
        tools_by = {p.get("agent_id"): sorted({s["name"] for s in p["trace"] if s.get("type") == "tool"}) for p in trace.walk(r)}
        out = {"tag": TAG, "smoke": True, "model": client.model, "cost_usd": r["cost_usd"], "row": row, "tools_by_agent": tools_by,
               "children_cost": round(sum(c["cost_usd"] for c in r.get("children", [])), 5)}
        (OUT / f"{TAG}_smoke_{stamp}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=1, ensure_ascii=False))
        print(f"smoke spent ${r['cost_usd']:.4f}; total so far ${prior + r['cost_usd']:.4f} of ${CAP_USD}")
        return
    budget = round(CAP_USD - prior, 4)
    live = OUT / f"{TAG}_{stamp}_rows.jsonl"
    rows, learned_all, groups_all, stopped = [], {}, {}, False
    spent = lambda: sum(x["cost_usd"] for x in rows)
    room = lambda: spent() + RESERVE_USD <= budget

    def keep(row):
        rows.append(row)
        with live.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"smoke spent ${prior}; this run may spend up to ${budget} (stops before a request when spent + ${RESERVE_USD} would pass it)", flush=True)
    for cid in COMPANIES:
        if stopped:
            break
        C = CompanyData(WORLD, cid, tmp / cid)
        sb, S = sandbox(C), LessonStore(OUT / f"{TAG}_{stamp}_{cid}_tools.sqlite")
        learn_runs = []
        for q in practice.build_gaps(C, split="dev"):
            if not room():
                stopped = True
                break
            r, row = ask(C, client, q)
            learn_runs.append(r)
            keep({**row, "phase": "learn", "arm": "Q"})
            print(f"learn {cid} {'ok ' if row['answer_ok'] else 'BAD'} {q['type']:26} {q['lang']} calls={row['tool_calls']} "
                  f"lead={row['lead_calls']} to={row['delegations']} sql_by={row['run_query_by']} ${row['cost_usd']:.4f} total=${spent():.3f}", flush=True)
        if stopped:
            print(f"{cid}: learning stopped by the cap; no tools judged for it", flush=True)
            break
        gs = nt.groups(learn_runs, cid, sb)
        cands = [g for g in gs if len(g["requests"]) >= nt.MIN_USES]
        info = {"queries_written": len(nt.uses_in(learn_runs, cid, sb)),
                "run_query_calls_by_agent": {}, "groups": len(gs),
                "group_requests": [len(g["requests"]) for g in gs], "group_uses": [len(g["uses"]) for g in gs],
                "largest_group": max((len(g["requests"]) for g in gs), default=0), "candidates": len(cands), "checks": []}
        for x in rows:
            if x["company"] == cid and x["phase"] == "learn":
                for ag in x["run_query_by"]:
                    info["run_query_calls_by_agent"][ag or "?"] = info["run_query_calls_by_agent"].get(ag or "?", 0) + 1
        for g in cands:
            c = nt.check(g, sb)
            entry = {"requests": len(g["requests"]), "pass": c["pass"], "template": g["template"][:300]}
            try:
                tid = nt.propose(S, cid, g, c, nt.free_name(S, cid, nt.suggest_name(g)), nt.describe(g))
            except ValueError as e:
                entry["skipped"] = str(e)[:200]
                info["checks"].append(entry)
                print(f"{cid}: candidate skipped ({e})", flush=True)
                continue
            if c["pass"]:
                nt.decide(S, tid, "fixed-rule", True)
            info["checks"].append(entry)
        learned = nt.tools(S, cid, "active")
        groups_all[cid] = info
        learned_all[cid] = [{"name": t["name"], "params": [p["name"] for p in t["params"]], "from_requests": len(t["source"])} for t in learned]
        print(f"{cid}: {info['groups']} groups, requests per group {info['group_requests']}, {info['candidates']} candidates, "
              f"{len(learned)} tools approved: {[t['name'] for t in learned]}", flush=True)
        for q in practice.build_gaps(C, split="held_out"):
            for arm, tools in (("Q", ()), ("T", learned)):
                if not room():
                    stopped = True
                    break
                r, row = ask(C, client, q, tools)
                keep({**row, "phase": "test", "arm": arm})
                print(f"test  {cid} {arm} {'ok ' if row['answer_ok'] else 'BAD'} {q['type']:26} {q['lang']} calls={row['tool_calls']} "
                      f"lead={row['lead_calls']} to={row['delegations']} learned={row['used_learned']} ${row['cost_usd']:.4f} total=${spent():.3f}", flush=True)
            if stopped:
                break
    test = [x for x in rows if x["phase"] == "test"]
    done = {x["id"] for x in test if x["arm"] == "T"} & {x["id"] for x in test if x["arm"] == "Q"}
    paired = [x for x in test if x["id"] in done]
    arms = {k: stats([x for x in paired if x["arm"] == k]) for k in "QT"}
    t_rows = [x for x in paired if x["arm"] == "T"]
    used = sum(bool(x["used_learned"]) for x in t_rows)
    made = sum(len(v) for v in learned_all.values())
    decision = {"R2_learned_tools_cheaper_not_worse": bool(t_rows) and arms["T"]["right"] >= arms["Q"]["right"] - 1
                and arms["T"]["mean_tool_calls"] <= 0.7 * arms["Q"]["mean_tool_calls"],
                "R2b_learned_tools_used": bool(t_rows) and used >= len(t_rows) / 2,
                "S1_at_least_one_tool_made": made >= 1,
                "learned_tool_used_in": f"{used}/{len(t_rows)}", "tools_made": made,
                "calls_ratio_T_over_Q": round(arms["T"]["mean_tool_calls"] / arms["Q"]["mean_tool_calls"], 3) if arms["Q"]["mean_tool_calls"] else None}
    result = {"tag": TAG, "plan_sha256": plan_sha(), "model": client.model, "world": WORLD.name, "complete": not stopped and len(done) == 16,
              "learned": learned_all, "groups": groups_all, "learn": stats([x for x in rows if x["phase"] == "learn"]),
              "arms": arms, "by_company": {f"{c}:{k}": stats([x for x in paired if x["company"] == c and x["arm"] == k]) for c in COMPANIES for k in "QT"},
              "decision": decision, "cost_usd": round(spent(), 4), "smoke_cost_usd": prior, "total_meta_usd": round(spent() + prior, 4),
              "rows": rows}
    if stopped:
        print(f"the ${CAP_USD} cap stopped the run: results are partial", flush=True)
    p = OUT / f"{TAG}_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("complete", "learned", "groups", "learn", "arms", "by_company", "decision", "cost_usd", "total_meta_usd")},
                     indent=1, ensure_ascii=False))
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
