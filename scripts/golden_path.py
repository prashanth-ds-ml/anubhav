"""Live golden path: real Muse + the MCP tools on the generated world, in four language styles plus one ambiguous
request. Each run starts from a clean runtime (no drafts) and its full trace is saved.

  uv run python scripts/golden_path.py --model open        # Muse Spark Open (Baseten)
  uv run python scripts/golden_path.py --model spark       # Muse Spark 1.3 (Meta API)
"""

import argparse
import sys
from pathlib import Path

from anubhav import muse, trace
from anubhav.agent import graph
from anubhav.mcp_server import DEFAULT_WORLD
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData

REQUESTS = [
    ("rt", "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku."),
    ("te", "రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు."),
    ("en", "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch."),
    ("mix", "Jangaon Lakshmi order ki suitable vehicle choose chesi draft create cheyyi, confirm cheyyaku."),
    ("ambiguous", "Warangal load ki bandi pettu."),
]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["open", "spark"], default="open")
    ap.add_argument("--company", default="T01")
    ap.add_argument("--world", default=str(DEFAULT_WORLD))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    client = muse.client(a.model)
    total = 0.0
    for tag, req in REQUESTS:
        if a.only and tag not in a.only:
            continue
        C = CompanyData(Path(a.world), a.company, Path(a.world) / "runtime" / "golden")
        C.runtime.reset()
        b = Broker(C, Session(a.company, "dispatcher", "golden-path"))
        r = graph.run(b, client, req)
        trace.save(r, label=f"golden_path:{tag}")
        total += r["cost_usd"]
        tools = [s["name"] + ("" if s["ok"] else f"!{s['error']['code']}") for s in r["trace"] if s["type"] == "tool"]
        drafts = [b.call("get_dispatch_draft", {"draft_id": d})["result"] for d in r["drafts"]]
        print(f"\n[{tag}] {req}\n  tools: {tools}\n  drafts: {[(d['vehicle_id'], d['orders'], d['verdict']['load']['kg']) for d in drafts]}"
              f"\n  stop={r['stop']} turns={r['turns']} calls={r['tool_calls']} ${r['cost_usd']} {r['latency_s']}s run={r['run_id']}"
              f"\n  reply: {r['reply'][:400]}")
    print(f"\nTotal cost: ${total:.4f}")


if __name__ == "__main__":
    main()
