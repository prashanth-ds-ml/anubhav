"""EXP-011: the final benchmark on an unseen world (seed 5279).

Arms, same cases, same model (Muse Spark Open), fresh runtime per case:
  A  cold, no raw-note search                     (T01, T02)
  B  cold + raw-note search (the 'is it just RAG?' baseline)   (T01, T02, TNEW)
  C  B + approved lessons mined in EXP-009b        (T01, T02)
  E  B + domain pack from T01 and T02              (TNEW)
Lessons come from EXP-009b's store on this world; approval uses the fixed review rule (no human judgement).

  uv run python scripts/exp011_benchmark.py
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.data.config import ROOT
from anubhav.eval import bench
from anubhav.learning import pack
from anubhav.learning.store import LessonStore
from anubhav.runtime.company import CompanyData

WORLD = ROOT / "data" / "worlds" / "full_seed5279"
MINED = sorted((ROOT / "artifacts" / "learning").glob("exp009b_*_fresh.sqlite"))[-1]


def review_rule(S, company):
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        strong = les["state"] == "CANDIDATE" and les["gate"].get("enforceable")
        S.approve(les["lesson_id"], "review-rule", "policy" if strong else "advisory", f"gate: {les['gate']['reason']}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    store_path = out_dir / f"exp011_{stamp}_lessons.sqlite"
    shutil.copy(MINED, store_path)
    S = LessonStore(store_path)
    for c in ("T01", "T02"):
        review_rule(S, c)
    view = {c: CompanyData(WORLD, c, out_dir / "rt" / "view") for c in ("T01", "T02", "TNEW")}
    packs = []
    for src in ("T01", "T02"):
        p = pack.publish(S, view[src], view["TNEW"], approved_by=f"owner-{src}")
        pack.import_pack(S, p, view["TNEW"], accepted_by="owner-TNEW", accept_policies=True)
        packs.append({"pack_id": p["pack_id"], "items": len(p["items"]), "leaks": pack.leaks(p, view[src], view["TNEW"])})
    print("packs:", packs, flush=True)

    cases = bench.build(WORLD)
    client = muse.client("open")
    rows = []
    for case in cases:
        arms = ["B", "E"] if case["company"] == "TNEW" else ["A", "B", "C"]
        for arm in arms:
            k, pol, adv = S.active_for(case["company"], view[case["company"]]) if arm in ("C", "E") else ([], [], [])
            r = bench.run_case(WORLD, case, client, arm, k, pol, adv, out_dir / "rt" / f"{case['id']}-{arm}")
            rows.append(r)
            print(f"{'✅' if r['ok'] else ('⛔' if r['unsafe'] else '❌')} {case['id']:28} {arm} drafted={r['drafted']} "
                  f"wrong_order={r['wrong_order_drafts']} search_notes={r['used_search_notes']} ${r['cost_usd']}", flush=True)
    summary = bench.summarize(rows)
    print(json.dumps(summary, indent=1), flush=True)
    p = out_dir / f"exp011_{stamp}.json"
    p.write_text(json.dumps({"world": str(WORLD.name), "lessons_from": MINED.name, "packs": packs, "summary": summary,
                             "rows": rows}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
