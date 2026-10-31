"""A small live check of the team on the demo world (not the benchmark's unseen world), ~$0.30 on Baseten: does the real
model delegate, reach Tool Forge when nothing fits, and keep planning safely? Prints what happened; decides nothing.

  uv run python scripts/team_smoke.py
"""

import json
import sys
import tempfile
from pathlib import Path

from anubhav import muse, trace
from anubhav.agents import team
from anubhav.data.config import ROOT
from anubhav.runtime.broker import Session
from anubhav.runtime.company import CompanyData
from anubhav.ui.logs import tool_usage

WORLD = ROOT / "data" / "worlds" / "full_seed20261104"
REQUESTS = [("plan", "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku."),
            ("data", "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?"),
            ("gap", "Which of our sites had the most damaged cases in September, and on which weekday do most damages happen?")]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = muse.client("spark")
    C = CompanyData(WORLD, "T01", Path(tempfile.mkdtemp()) / "rt")
    total, runs = 0.0, []
    for tag, req in REQUESTS:
        r = team.run(C, Session("T01", "dispatcher", "smoke"), client, req)
        trace.save(r, label=f"smoke:team:{tag}")
        runs.append(r)
        total += r["cost_usd"]
        print(f"\n== {tag}: {req}")
        print("  agents:", ["planner"] + [c["agent_id"] for c in r["children"]], "stop:", r["stop"], "cost:", r["cost_usd"], "drafts:", r["drafts"], "reply_check:", r["reply_check"]["ok"])
        for part in [r, *r["children"]]:
            print(f"  {part.get('agent_id')}:", [s["name"] + ("" if s["ok"] else f"!{s['error']['code']}") for s in part["trace"] if s["type"] == "tool"])
        print("  reply:", r["reply"][:300].replace("\n", " "))
    print("\ntotal $", round(total, 4))
    print(json.dumps(tool_usage(runs)[:12], ensure_ascii=False))


if __name__ == "__main__":
    main()
