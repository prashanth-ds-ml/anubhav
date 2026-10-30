"""EXP-012: does the agent fill tool gaps with queries, and do the tools it learns make it cheaper without losing
accuracy? (pre-registered 2026-11-02 before any Muse call)

World 5279 (unseen), T01 and T02, Muse Spark Open, the gap questions of practice.build_gaps (no built tool answers
them; answers computed from the records; never shown to the agent).
  1. Learn: the dev gap questions with the query tools on (arm Q). Their runs go through newtools.candidates and
     newtools.check; every candidate whose checks pass is approved by a fixed rule (the stand-in for the person,
     as EXP-011's review rule).
  2. Test, held-out gap questions (other towns, other month), fresh runtime each:
       N  built-in tools only (no query tools)      Q  + describe_tables / run_query      T  Q + the approved learned tools
  uv run python scripts/exp012_new_tools.py         # ~96 runs, ~$4 Baseten
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.agent import graph
from anubhav.data.config import ROOT
from anubhav.harness import practice
from anubhav.learning import newtools as nt
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import sandbox

WORLD = ROOT / "data" / "worlds" / "full_seed5279"


def ask(C, client, q, analysis, learned=()):
    b = Broker(C, Session(C.company, "dispatcher", "exp012"), analysis=analysis, learned_tools=learned)
    r = graph.run(b, client, q["question"])
    s = practice.score(q, r)
    return r, {**{k: q[k] for k in ("id", "company", "type", "lang", "question")}, **{k: s[k] for k in ("answer_ok", "right_tool", "tools", "cost_usd")},
               "tool_calls": r["tool_calls"], "stop": r["stop"], "reply": r["reply"][:400], "run_id": r["run_id"]}


def stats(rows):
    n = len(rows) or 1
    return {"n": len(rows), "answer_ok": round(sum(x["answer_ok"] for x in rows) / n, 3), "right": sum(x["answer_ok"] for x in rows),
            "mean_tool_calls": round(sum(x["tool_calls"] for x in rows) / n, 2), "mean_cost": round(sum(x["cost_usd"] for x in rows) / n, 4),
            "cost_usd": round(sum(x["cost_usd"] for x in rows), 3)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "artifacts" / "benchmark"
    out.mkdir(parents=True, exist_ok=True)
    live = out / f"exp012_{stamp}_rows.jsonl"
    client, tmp = muse.client("open"), Path(tempfile.mkdtemp())
    rows, learned_all = [], {}
    for cid in ("T01", "T02"):
        C = CompanyData(WORLD, cid, tmp / cid)
        sb, S = sandbox(C), LessonStore(out / f"exp012_{stamp}_{cid}_tools.sqlite")
        learn_runs = []
        for q in practice.build_gaps(C, split="dev"):
            r, row = ask(C, client, q, True)
            learn_runs.append(r)
            rows.append({**row, "phase": "learn", "arm": "Q"})
            print(f"learn {cid} {'✅' if row['answer_ok'] else '❌'} {q['type']:26} {q['lang']} calls={row['tool_calls']} ${row['cost_usd']}", flush=True)
        for g in nt.candidates(learn_runs, cid, sb):
            c = nt.check(g, sb)
            tid = nt.propose(S, cid, g, c, f"{nt.suggest_name(g)}_{g['key'][:4]}", (g["uses"][0]["purpose"] or g["uses"][0]["request"])[:200])
            if c["pass"]:
                nt.decide(S, tid, "fixed-rule", True)
        learned = nt.tools(S, cid, "active")
        learned_all[cid] = [{"name": t["name"], "params": [p["name"] for p in t["params"]], "from_requests": len(t["source"])} for t in learned]
        print(f"{cid}: {len(learned)} tools approved by the fixed rule: {[t['name'] for t in learned]}", flush=True)
        for q in practice.build_gaps(C, split="held_out"):
            for arm, analysis, tools in (("N", False, ()), ("Q", True, ()), ("T", True, learned)):
                r, row = ask(C, client, q, analysis, tools)
                row |= {"phase": "test", "arm": arm, "used_learned": [t for t in row["tools"] if t in {x["name"] for x in learned}]}
                rows.append(row)
                with live.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"test  {cid} {arm} {'✅' if row['answer_ok'] else '❌'} {q['type']:26} {q['lang']} calls={row['tool_calls']} ${row['cost_usd']}", flush=True)
    test = [x for x in rows if x["phase"] == "test"]
    arms = {a: stats([x for x in test if x["arm"] == a]) for a in "NQT"}
    rule = {"R1_query_fills_gap": 100 * (arms["Q"]["answer_ok"] - arms["N"]["answer_ok"]) >= 25,
            "R2_learned_tools_cheaper_not_worse": arms["T"]["right"] >= arms["Q"]["right"] - 1
            and arms["T"]["mean_tool_calls"] <= 0.7 * arms["Q"]["mean_tool_calls"]}
    result = {"world": WORLD.name, "learned": learned_all, "learn": stats([x for x in rows if x["phase"] == "learn"]),
              "arms": arms, "by_company": {f"{c}:{a}": stats([x for x in test if x["company"] == c and x["arm"] == a]) for c in ("T01", "T02") for a in "NQT"},
              "decision": rule, "cost_usd": round(sum(x["cost_usd"] for x in rows), 3), "rows": rows}
    p = out / f"exp012_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("learned", "learn", "arms", "decision", "cost_usd")}, indent=1, ensure_ascii=False))
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
