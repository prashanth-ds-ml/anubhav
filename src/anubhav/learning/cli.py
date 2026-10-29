"""Learning loop from the command line.

  uv run python -m anubhav.learning.cli mine --company T01 [--model spark]
  uv run python -m anubhav.learning.cli list --company T01
  uv run python -m anubhav.learning.cli approve L-T01-003 --effect policy --verified "two refused trips; operator confirmed" --reviewer prashanth
  uv run python -m anubhav.learning.cli reject|retire|rollback L-T01-004 --reviewer prashanth --why "..."
  uv run python -m anubhav.learning.cli recheck --company T01
  uv run python -m anubhav.learning.cli publish --source T01 --to TNEW --approver prashanth [--accept-policies]
  uv run python -m anubhav.learning.cli report --company T01
"""

import argparse
import json
import sys
from pathlib import Path

from .. import muse
from ..mcp_server import DEFAULT_WORLD
from ..runtime.company import CompanyData
from . import digest, miner, pack, report
from .store import LessonStore


def store_for(world):
    return LessonStore(Path(world) / "learning" / "learning.sqlite")


def data(world, company):
    return CompanyData(Path(world), company, Path(world) / "runtime" / "learning")


def show(rows):
    for r in rows:
        print(f"{r['lesson_id']:12} {r['state']:16} {r['kind']:18} {json.dumps(r['params'], ensure_ascii=False)[:70]:70} | {r['gate']['reason'][:90]}")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mine", "list", "approve", "reject", "retire", "rollback", "recheck", "publish", "report"])
    ap.add_argument("lesson", nargs="?")
    ap.add_argument("--company")
    ap.add_argument("--world", default=str(DEFAULT_WORLD))
    ap.add_argument("--model", choices=["spark", "open"], default="spark")
    ap.add_argument("--effect", choices=["advisory", "policy"], default="advisory")
    ap.add_argument("--verified", default="")
    ap.add_argument("--reviewer", default="reviewer")
    ap.add_argument("--why", default="")
    ap.add_argument("--source")
    ap.add_argument("--to")
    ap.add_argument("--approver")
    ap.add_argument("--accept-policies", action="store_true")
    a = ap.parse_args(argv)
    S = store_for(a.world)
    if a.cmd == "mine":
        C = data(a.world, a.company)
        F, d = digest.build(C)
        props, meta = miner.mine(muse.client(a.model), C, d)
        ids = S.add_proposals(a.company, F, props, meta)
        print(f"{len(props)} proposals from {meta['model']} (${meta['cost_usd']:.4f}, {meta['latency_s']}s)")
        show([S.get(i) for i in ids])
    elif a.cmd == "list":
        show(S.list(a.company))
    elif a.cmd == "approve":
        show([S.approve(a.lesson, a.reviewer, a.effect, a.verified)])
    elif a.cmd == "reject":
        show([S.reject(a.lesson, a.reviewer, a.why)])
    elif a.cmd == "retire":
        show([S.retire(a.lesson, a.reviewer, a.why)])
    elif a.cmd == "rollback":
        show([S.rollback(a.lesson, a.reviewer)])
    elif a.cmd == "recheck":
        C = data(a.world, a.company)
        show(S.recheck(a.company, digest.Facts(C)))
    elif a.cmd == "publish":
        src, dst = data(a.world, a.source), data(a.world, a.to)
        p = pack.publish(S, src, dst, a.approver)
        ids = pack.import_pack(S, p, dst, a.approver, a.accept_policies)
        print(f"{p['pack_id']}: {len(p['items'])} lessons shared, {len(p['skipped'])} skipped; leaks: {pack.leaks(p, src, dst)}")
        show([S.get(i) for i in ids])
    elif a.cmd == "report":
        print(report.weekly(S, a.company, data(a.world, a.company)))


if __name__ == "__main__":
    main()
