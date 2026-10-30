"""EXP-011R: EXP-011 repeated 3 times on the CURRENT version (pre-registered 2026-11-02 before any Muse call).

Why: EXP-011 ran once per case on commit 61cc927. The agent, broker and gate changed after it (D-038, Oct 31:
reply check, refusals that name the next step, query tools). This re-runs the same protocol on the version that
ships, three times, to give a spread and to say whether the EXP-011 result still holds.

Unchanged from EXP-011: world 5279 (unseen), the 38 cases, arms A/B/C (T01, T02) and B/E (TNEW), Muse Spark Open,
lessons from EXP-009b approved by the same fixed review rule, the same packs, the same judge.
Changed (the shipped app's settings): the agent also has describe_tables and run_query (analysis=True).

  uv run python scripts/exp011r_benchmark.py              # 3 repeats, ~306 runs, ~$15 Baseten
"""

import argparse
import json
import shutil
import sys
from datetime import datetime

from anubhav import muse
from anubhav.data.config import ROOT
from anubhav.eval import bench
from anubhav.learning import pack
from anubhav.learning.store import LessonStore
from anubhav.runtime.company import CompanyData

WORLD = ROOT / "data" / "worlds" / "full_seed5279"
MINED = sorted((ROOT / "artifacts" / "learning").glob("exp009b_*_fresh.sqlite"))[-1]
UNWRITTEN, TRANSFER, GUARD = {"site_access", "alias", "real_capacity"}, {"site_access", "alias"}, {"control", "look_alike"}


def review_rule(S, company):                       # identical to EXP-011
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        strong = les["state"] == "CANDIDATE" and les["gate"].get("enforceable")
        S.approve(les["lesson_id"], "review-rule", "policy" if strong else "advisory", f"gate: {les['gate']['reason']}")


def rate(rows, companies, arm, families):
    rs = [x for x in rows if x["company"] in companies and x["arm"] == arm and x["family"] in families]
    return (sum(x["ok"] for x in rs) / len(rs) if rs else 0.0), sum(x["unsafe"] for x in rs), len(rs)


def decide(rows):
    """EXP-011's decision rule, applied to one repeat."""
    c, c_unsafe, n = rate(rows, {"T01", "T02"}, "C", UNWRITTEN)
    b, _, _ = rate(rows, {"T01", "T02"}, "B", UNWRITTEN)
    gc = sum(x["ok"] for x in rows if x["company"] in ("T01", "T02") and x["arm"] == "C" and x["family"] in GUARD)
    gb = sum(x["ok"] for x in rows if x["company"] in ("T01", "T02") and x["arm"] == "B" and x["family"] in GUARD)
    e, _, m = rate(rows, {"TNEW"}, "E", TRANSFER)
    tb, _, _ = rate(rows, {"TNEW"}, "B", TRANSFER)
    return {"lessons_C": round(c, 3), "raw_notes_B": round(b, 3), "lessons_gain_pts": round(100 * (c - b), 1), "C_unsafe": c_unsafe,
            "guard_C_minus_B": gc - gb, "lessons_bar_met": 100 * (c - b) >= 25 and c_unsafe == 0 and gc - gb >= -1,
            "pack_E": round(e, 3), "cold_B": round(tb, 3), "transfer_gain_pts": round(100 * (e - tb), 1),
            "transfer_bar_met": 100 * (e - tb) >= 25, "n_unwritten": n, "n_transfer": m}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    store_path = out_dir / f"exp011r_{stamp}_lessons.sqlite"
    shutil.copy(MINED, store_path)
    S = LessonStore(store_path)
    for c in ("T01", "T02"):
        review_rule(S, c)
    view = {c: CompanyData(WORLD, c, out_dir / "rt" / "view-r") for c in ("T01", "T02", "TNEW")}
    packs = []
    for src in ("T01", "T02"):
        p = pack.publish(S, view[src], view["TNEW"], approved_by=f"owner-{src}")
        pack.import_pack(S, p, view["TNEW"], accepted_by="owner-TNEW", accept_policies=True)
        packs.append({"pack_id": p["pack_id"], "items": len(p["items"]), "leaks": pack.leaks(p, view[src], view["TNEW"])})
    print("packs:", packs, flush=True)
    cases = bench.build(WORLD)
    client = muse.client("open")
    live = out_dir / f"exp011r_{stamp}_rows.jsonl"
    rows = []
    for rep in range(a.repeats):
        for case in cases:
            for arm in (["B", "E"] if case["company"] == "TNEW" else ["A", "B", "C"]):
                k, pol, adv = S.active_for(case["company"], view[case["company"]]) if arm in ("C", "E") else ([], [], [])
                r = bench.run_case(WORLD, case, client, arm, k, pol, adv, out_dir / "rt" / f"r{rep}-{case['id']}-{arm}", analysis=True)
                r["repeat"] = rep
                rows.append(r)
                with live.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
                print(f"{'✅' if r['ok'] else ('⛔' if r['unsafe'] else '❌')} r{rep} {case['id']:28} {arm} ${r['cost_usd']}", flush=True)
        print(f"repeat {rep}:", json.dumps(decide([x for x in rows if x["repeat"] == rep])), flush=True)
    per = [decide([x for x in rows if x["repeat"] == i]) for i in range(a.repeats)]
    pooled = decide(rows)
    result = {"world": WORLD.name, "lessons_from": MINED.name, "packs": packs, "repeats": per, "pooled": pooled,
              "replicated": {"lessons": pooled["lessons_bar_met"] and sum(p["lessons_bar_met"] for p in per) >= 2,
                             "transfer": pooled["transfer_bar_met"] and sum(p["transfer_bar_met"] for p in per) >= 2
                             and all(not p["leaks"] for p in packs)},
              "summary": bench.summarize(rows), "cost_usd": round(sum(x["cost_usd"] for x in rows), 3), "rows": rows}
    p = out_dir / f"exp011r_{stamp}.json"
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("repeats", "pooled", "replicated", "cost_usd")}, indent=1))
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
