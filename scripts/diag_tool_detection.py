"""Diagnostic, not a benchmark (owner, Nov 3): why did Muse Spark 1.3 make no learned tools in EXP-014 and EXP-016?

Re-asks EXP-016's 20 learning questions (world 5279, T01 and T02, the dev gap questions, query tools on) on Muse Spark 1.3
via the Meta API, saves every run's full trace (data/traces, local), and then runs tool detection twice on the same
runs: the old detection (newtools.py as committed in dece5cf) and the new one (case-insensitive and LIKE inputs, month
inputs, id lists refused). It reports, for each, the queries written, the queries with inputs, the groups, the candidates
(3+ different requests) and how many pass the code checks. No tool is approved and no answer is scored here.

  uv run python scripts/diag_tool_detection.py --budget 2
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from anubhav import muse, trace
from anubhav.agent import graph
from anubhav.data.config import ROOT
from anubhav.harness import practice
from anubhav.learning import newtools as nt_new
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import sandbox
from anubhav.trace import walk

WORLD = ROOT / "data" / "worlds" / "full_seed5279"
OLD_COMMIT = "dece5cf"


def old_detection():
    """newtools.py as it was before the Nov 3 fixes, loaded from git as its own module."""
    src = subprocess.run(["git", "show", f"{OLD_COMMIT}:src/anubhav/learning/newtools.py"], capture_output=True, text=True,
                         encoding="utf-8", cwd=ROOT, check=True).stdout
    src = re.sub(r"from \.\.(\w+)", r"from anubhav.\1", src)
    path = Path(tempfile.mkdtemp()) / "newtools_old.py"
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("newtools_old", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def queries(runs):
    """Every successful read-only query in these runs, as written."""
    out = []
    for top in runs:
        for r in walk(top):
            for s in r.get("trace", []):
                if s.get("type") == "tool" and s.get("name") == "run_query" and s.get("ok"):
                    a = s["arguments"]
                    a = json.loads(a) if isinstance(a, str) else (a or {})
                    out.append({"request": top.get("request", ""), "sql": a.get("sql", ""), "rows": (s.get("result") or {}).get("row_count")})
    return out


def styles(sql):
    low = sql.lower()
    return {"like": " like " in low, "lower_or_upper": "lower(" in low or "upper(" in low, "in_list": bool(re.search(r"\bin\s*\(\s*'", low)),
            "month_text": bool(re.search(r"'\d{4}-\d{2}'", sql)), "full_date": bool(re.search(r"'\d{4}-\d{2}-\d{2}'", sql))}


def detect(nt, runs, cid, sb):
    uses = nt.uses_in(runs, cid, sb)
    groups = nt.groups(runs, cid, sb)
    cands = nt.candidates(runs, cid, sb)
    checks = [nt.check(g, sb) for g in cands]
    return {"queries_with_inputs": len(uses), "groups": len(groups), "biggest_group_requests": max((len(g["requests"]) for g in groups), default=0),
            "candidates": len(cands), "candidates_passing_checks": sum(c["pass"] for c in checks),
            "candidate_templates": [g["template"] for g in cands], "check_reasons": [c["reasons"] for c in checks]}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("open", "spark"), default="spark")
    ap.add_argument("--budget", type=float, default=2.0)
    a = ap.parse_args()
    client, tmp, spent = muse.client(a.model), Path(tempfile.mkdtemp()), 0.0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nt_old = old_detection()
    report = {"model": client.model, "world": WORLD.name, "note": "diagnostic, not a benchmark", "companies": {}}
    for cid in ("T01", "T02"):
        C = CompanyData(WORLD, cid, tmp / cid)
        sb, runs = sandbox(C), []
        for q in practice.build_gaps(C, split="dev"):
            if spent >= a.budget:
                print(f"budget of ${a.budget} reached at ${spent:.2f}", flush=True)
                break
            b = Broker(C, Session(cid, "dispatcher", "diag"), analysis=True)
            r = graph.run(b, client, q["question"])
            trace.save(r, label=f"diag-tools:{a.model}")
            spent += r.get("cost_usd") or 0
            runs.append(r)
            print(f"{cid} {q['type']:26} {q['lang']} calls={r['tool_calls']} ${r.get('cost_usd', 0):.4f} total ${spent:.2f}", flush=True)
        qs = queries(runs)
        report["companies"][cid] = {
            "runs": len(runs), "queries_written": len(qs), "requests": len({x["request"] for x in qs}),
            "styles": dict(sum((Counter({k: 1 for k, v in styles(x["sql"]).items() if v}) for x in qs), Counter())),
            "old": detect(nt_old, runs, cid, sb), "new": detect(nt_new, runs, cid, sb),
            "queries": [{"request": x["request"][:120], "sql": x["sql"], "rows": x["rows"]} for x in qs]}
    report["cost_usd"] = round(spent, 4)
    out = ROOT / "artifacts" / "benchmark" / f"diag_tools_{a.model}_{stamp}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for cid, c in report["companies"].items():
        print(cid, json.dumps({k: c[k] for k in ("runs", "queries_written", "requests", "styles")}),
              "\n  old:", json.dumps({k: v for k, v in c["old"].items() if k not in ("candidate_templates", "check_reasons")}),
              "\n  new:", json.dumps({k: v for k, v in c["new"].items() if k not in ("candidate_templates", "check_reasons")}), flush=True)
    print("saved", out.relative_to(ROOT), "cost $", report["cost_usd"])


if __name__ == "__main__":
    main()
