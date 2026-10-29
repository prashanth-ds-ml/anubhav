"""EXP-009: does the sharper evidence gate raise precision without losing recall?

Primary (honest test): a fresh-seed world (seed 4111) that nobody has inspected. Muse Spark 1.3 mines T01, T02, T03
once each; the refined gate checks every proposal; the evaluator scores against that world's hidden truth.
Diagnostic only (in-sample, the fixes were designed after seeing these): the EXP-008 rep-0 proposals re-checked by
the refined gate on the original world.

  uv run python scripts/exp009_gate.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.data.config import ROOT
from anubhav.learning import digest, evaluate, miner
from anubhav.learning.store import LessonStore
from anubhav.runtime.company import CompanyData

FRESH = ROOT / "data" / "worlds" / "full_seed4111"
ORIGINAL = ROOT / "data" / "worlds" / "full_seed20261104"
EXP008 = sorted((ROOT / "artifacts" / "learning").glob("exp008_*_rep0.sqlite"))[-1]


def pooled(scores):
    passed = sum(s["passed"] for s in scores.values())
    true_passed = sum(round((s["precision"] or 0) * s["passed"]) for s in scores.values())
    learn = sum(len(s["learnable"]) for s in scores.values())
    found = sum(len(s["found"]) for s in scores.values())
    return {"precision": round(true_passed / passed, 3) if passed else None, "recall": round(found / learn, 3) if learn else None,
            "passed": passed, "true_passed": true_passed, "learnable": learn, "found": found,
            "traps_admitted": sorted({t for s in scores.values() for t in s["traps_admitted"]})}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "learning"
    out = {"stamp": stamp, "miner": muse.DEFAULT_MODEL}

    # diagnostic: same EXP-008 proposals, refined gate, original world (no model calls)
    old = LessonStore(EXP008)
    truth0 = evaluate.Truth(ORIGINAL)
    diag_store = LessonStore(out_dir / f"exp009_{stamp}_diagnostic.sqlite")
    diag = {}
    for c in ("T01", "T02", "T03"):
        C = CompanyData(ORIGINAL, c, out_dir / "rt9")
        props = [{"kind": l["kind"], "params": l["params"], "claim": l["claim"]} for l in old.list(c)]
        diag_store.add_proposals(c, digest.Facts(C), props, skip_known=False)
        s = evaluate.score(truth0, c, diag_store.list(c))
        diag[c] = {k: v for k, v in s.items() if k != "rows"}
    out["diagnostic_in_sample"] = {"per_company": diag, "pooled": pooled(diag)}
    print("diagnostic (in-sample, EXP-008 proposals re-gated):", out["diagnostic_in_sample"]["pooled"], flush=True)

    # primary: fresh world, fresh mining
    truth = evaluate.Truth(FRESH)
    store = LessonStore(out_dir / f"exp009_{stamp}_fresh.sqlite")
    prim, cost = {}, 0.0
    client = muse.client("spark")
    for c in ("T01", "T02", "T03"):
        C = CompanyData(FRESH, c, out_dir / "rt9f")
        F, d = digest.build(C)
        props, meta = miner.mine(client, C, d)
        cost += meta["cost_usd"]
        store.add_proposals(c, F, props, meta)
        s = evaluate.score(truth, c, store.list(c))
        prim[c] = {k: v for k, v in s.items() if k != "rows"} | {"rows": s["rows"], "cost_usd": meta["cost_usd"]}
        print(f"fresh {c}: proposed {s['proposed']}, passed {s['passed']}, precision {s['precision']}, recall {s['recall']}, "
              f"missed {s['missed']}, false {s['false_lessons']}, traps admitted {s['traps_admitted']}, "
              f"traps rejected {s['traps_proposed_and_rejected']}", flush=True)
    out["primary_fresh_world"] = {"per_company": prim, "pooled": pooled(prim), "cost_usd": round(cost, 4)}
    print("primary (fresh world):", out["primary_fresh_world"]["pooled"], f"${cost:.3f}", flush=True)
    p = out_dir / f"exp009_{stamp}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
