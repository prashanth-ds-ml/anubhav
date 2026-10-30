"""EXP-012b: EXP-012 with one change: learned tools get general names and descriptions (pre-registered 2026-10-30
before any Muse call, after EXP-012 failed both rules).

EXP-012 approved 10 tools but the agent never called one on held-out questions (0/16): each tool was named after
the request it came from ("..._narsampet_september"). Now code names a tool by what it returns and takes
(newtools.suggest_name, e.g. weekday_stops_by_town), describes its inputs (newtools.describe), and refuses a name
that contains a value it was built from. Everything else is EXP-012's protocol: world 5279, T01 and T02, the same
gap questions, learn on dev with the query tools, the same checks, the same fixed approval rule.
Test arms (held-out): Q (+ query tools) and T (Q + learned tools). Arm N is not re-run (EXP-012 reported it).
  uv run python scripts/exp012b_new_tools.py        # ~52 runs, ~$3 Baseten
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
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", default="T01,T02")
    ap.add_argument("--keep", help="rows.jsonl of an interrupted run whose test rows are kept (amendment, logged)")
    ap.add_argument("--keep-tools", help="tools sqlite of the kept company, for the learned-tool list")
    a = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "artifacts" / "benchmark"
    out.mkdir(parents=True, exist_ok=True)
    live = out / f"exp012b_{stamp}_rows.jsonl"
    client, tmp = muse.client("open"), Path(tempfile.mkdtemp())
    rows, learned_all = [], {}
    if a.keep:
        kept = [json.loads(x) for x in Path(a.keep).read_text(encoding="utf-8").splitlines() if x.strip()]
        rows += [dict(x, phase="test", kept_from=Path(a.keep).name) for x in kept]
        kc = sorted({x["company"] for x in kept})
        if a.keep_tools:
            for c in kc:
                learned_all[c] = [{"name": t["name"], "params": [p["name"] for p in t["params"]], "from_requests": len(t["source"])}
                                  for t in nt.tools(LessonStore(a.keep_tools), c, "active")]
        print(f"kept {len(kept)} test rows of {kc} from {a.keep}", flush=True)
    for cid in a.companies.split(","):
        C = CompanyData(WORLD, cid, tmp / cid)
        sb, S = sandbox(C), LessonStore(out / f"exp012b_{stamp}_{cid}_tools.sqlite")
        learn_runs = []
        for q in practice.build_gaps(C, split="dev"):
            r, row = ask(C, client, q, True)
            learn_runs.append(r)
            rows.append({**row, "phase": "learn", "arm": "Q"})
            print(f"learn {cid} {'✅' if row['answer_ok'] else '❌'} {q['type']:26} {q['lang']} calls={row['tool_calls']} ${row['cost_usd']}", flush=True)
        for g in nt.candidates(learn_runs, cid, sb):
            c = nt.check(g, sb)
            try:      # amendment (logged): a name that still carries a source value is not a general tool: skip it
                tid = nt.propose(S, cid, g, c, nt.free_name(S, cid, nt.suggest_name(g)), nt.describe(g))
            except ValueError as e:
                print(f"{cid}: candidate skipped ({e})", flush=True)
                continue
            if c["pass"]:
                nt.decide(S, tid, "fixed-rule", True)
        learned = nt.tools(S, cid, "active")
        learned_all[cid] = [{"name": t["name"], "params": [p["name"] for p in t["params"]], "from_requests": len(t["source"])} for t in learned]
        print(f"{cid}: {len(learned)} tools approved by the fixed rule: {[t['name'] for t in learned]}", flush=True)
        for q in practice.build_gaps(C, split="held_out"):
            for arm, analysis, tools in (("Q", True, ()), ("T", True, learned)):
                r, row = ask(C, client, q, analysis, tools)
                row |= {"phase": "test", "arm": arm, "used_learned": [t for t in row["tools"] if t in {x["name"] for x in learned}]}
                rows.append(row)
                with live.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"test  {cid} {arm} {'✅' if row['answer_ok'] else '❌'} {q['type']:26} {q['lang']} calls={row['tool_calls']} ${row['cost_usd']}", flush=True)
    test = [x for x in rows if x["phase"] == "test"]
    arms = {a: stats([x for x in test if x["arm"] == a]) for a in "QT"}
    t_rows = [x for x in test if x["arm"] == "T"]
    rule = {"R2_learned_tools_cheaper_not_worse": arms["T"]["right"] >= arms["Q"]["right"] - 1
            and arms["T"]["mean_tool_calls"] <= 0.7 * arms["Q"]["mean_tool_calls"],
            "R2b_learned_tools_used": sum(bool(x["used_learned"]) for x in t_rows) >= len(t_rows) / 2,
            "learned_tool_used_in": f"{sum(bool(x['used_learned']) for x in t_rows)}/{len(t_rows)}"}
    result = {"world": WORLD.name, "learned": learned_all, "learn": stats([x for x in rows if x["phase"] == "learn"]),
              "arms": arms, "by_company": {f"{c}:{a}": stats([x for x in test if x["company"] == c and x["arm"] == a]) for c in ("T01", "T02") for a in "QT"},
              "decision": rule, "cost_usd": round(sum(x["cost_usd"] for x in rows), 3), "rows": rows}
    p = out / f"exp012b_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("learned", "learn", "arms", "decision", "cost_usd")}, indent=1, ensure_ascii=False))
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
