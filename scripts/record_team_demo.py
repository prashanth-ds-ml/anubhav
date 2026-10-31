"""Real team runs for the demo bundle (~$0.50 on Baseten), on the demo world: planning with and without lessons, a data question,
and the Lesson Miner. Labelled demo:team:*, then `uv run python scripts/export_demo.py` puts them in the hosted bundle.
Prints the Lesson Miner's precision and recall against the hidden rules; proposals go to a temporary store.

  uv run python scripts/record_team_demo.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

from anubhav import muse, trace
from anubhav.agents import team
from anubhav.learning import evaluate
from anubhav.learning.store import LessonStore
from anubhav.runtime.broker import Session
from anubhav.runtime.company import CompanyData
from anubhav.service.session import EXP008, SUGGESTIONS, WORLD
from anubhav.trace import walk


def show(tag, r):
    print(f"\n== {tag}: agents {[p.get('agent_id') for p in walk(r)]} stop {r['stop']} ${r['cost_usd']} drafts {r['drafts']} reply_check {r['reply_check']['ok']}")
    for p in walk(r):
        print(f"  {p.get('agent_id')}:", [s["name"] + ("" if s["ok"] else f"!{s['error']['code']}") for s in p["trace"] if s["type"] == "tool"])
    print("  reply:", r["reply"][:260].replace("\n", " "))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp())
    client = muse.client("open")
    shutil.copy(EXP008[-1], tmp / "lessons.sqlite")
    S = LessonStore(tmp / "lessons.sqlite")
    total = 0.0

    def go(tag, request, lessons):
        nonlocal total
        C = CompanyData(WORLD, "T01", tmp / f"rt-{tag}")
        k, pol, adv = S.active_for("T01", C) if lessons else ([], [], [])
        r = team.run(C, Session("T01", "dispatcher", "demo"), client, request, knowledge=k, policies=pol, advisories=adv, lessons=S.for_agent("T01", C) if lessons else [], analysis=True)
        r["learned_tools"] = []
        trace.save(r, label=f"demo:team:{tag}")
        show(tag, r)
        total += r["cost_usd"]

    go("cold", SUGGESTIONS["Roman Telugu"], False)
    go("lessons", SUGGESTIONS["Roman Telugu"], True)
    go("nickname", SUGGESTIONS["Nickname"], True)
    go("new-tool", SUGGESTIONS["New tool"], False)
    go("data", "Which of our sites had the most damaged cases in September?", False)

    C = CompanyData(WORLD, "T01", tmp / "rt-miner")
    fresh = LessonStore(tmp / "miner.sqlite")
    r = team.run(C, Session("T01", "dispatcher", "demo"), client, team.MINE_BRIEF, lead_agent="lesson_miner", analysis=True, lesson_store=fresh)
    r["learned_tools"] = []
    trace.save(r, label="demo:team:miner")
    show("miner", r)
    total += r["cost_usd"]
    s = evaluate.score(evaluate.Truth(WORLD), "T01", fresh.list("T01"))
    print("\nminer:", {k: s[k] for k in ("proposed", "passed", "precision", "recall", "false_lessons", "traps_admitted")})
    print("total $", round(total, 4))


if __name__ == "__main__":
    main()
