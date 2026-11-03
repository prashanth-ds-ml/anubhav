"""EXP-018 (scaling check): does learning get better as the company has more history?

Muse Spark 1.3 (Meta API) mines the demo world's T01 from its first 30, 60 and 90 days of records, 3 repeats each,
each run into an empty lesson store; the frozen evidence gate checks every proposal against the same records the
miner saw; evaluate.score (as in EXP-008/009b) scores what passed against the generator's hidden rules.

Replay "as of day N": every record list is cut at the end of day N with the same rule as digest.Facts(until=...),
and the company's "today" is the day after the cutoff. The cut is applied to the company view itself (not only to
Facts) so the digest's staff edits and planner messages, the miner's "Today is", and the gate's expiry dates are
all as of that day. At 90 days this is the live path (fresh.learn: digest -> mine -> gate) unchanged.

  uv run python scripts/exp018_scaling.py --dry       # no model call: digest sizes, rules with evidence by cutoff
  uv run python scripts/exp018_scaling.py --freeze    # write artifacts/benchmark/exp018_frozen.json (hashes + plan)
  baseten_api_key= uv run python scripts/exp018_scaling.py --smoke             # 1 call (30 days), not scored in the result
  baseten_api_key= uv run python scripts/exp018_scaling.py --budget 1.40 [--resume STAMP]
"""

import argparse
import copy
import hashlib
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp_freeze  # noqa: E402

from anubhav import muse  # noqa: E402
from anubhav.data.config import ROOT  # noqa: E402
from anubhav.learning import digest, evaluate, miner  # noqa: E402
from anubhav.learning.store import LessonStore  # noqa: E402
from anubhav.mcp_server import DEFAULT_WORLD  # noqa: E402
from anubhav.runtime.company import CompanyData  # noqa: E402

TAG = "exp018"
SCRIPT = "scripts/exp018_scaling.py"
COMPANY = "T01"
LENGTHS = (30, 60, 90)
REPEATS = 3
OUT = ROOT / "artifacts" / "learning"
EXTRA = ["src/anubhav/learning/digest.py", "src/anubhav/learning/miner.py", "src/anubhav/learning/store.py",
         "src/anubhav/learning/evaluate.py", "src/anubhav/runtime/company.py", "src/anubhav/data/config.py"]

PLAN = {
    "id": "EXP-018",
    "question": "Does learning get better as the company has more history? (scaling check)",
    "world": "data/worlds/full_seed20261104 (demo world), company T01; records 2026-08-01 to 2026-10-29",
    "arms": "history length 30, 60, 90 days: records cut at the end of 2026-08-30, 2026-09-29, 2026-10-29; "
            "company 'today' = the day after the cutoff (90 days = the live path unchanged)",
    "pipeline": "digest (5 digests, as digest.build) -> miner.mine with Muse Spark 1.3 on the Meta API, temperature 0 -> "
                "evidence gate (store.add_proposals) checking against the same cut records; each run into an empty store",
    "repeats": "3 per length (9 mining calls), order rep0: 30,60,90; rep1: 30,60,90; rep2: 30,60,90",
    "scoring": "evaluate.score unchanged (EXP-008/009b): passed = CANDIDATE, NEEDS_EVIDENCE or EXPIRED; recall = hidden "
               "learnable rules found / learnable rules over all 90 days (fixed denominator); precision = passed lessons "
               "matching a non-trap hidden rule / passed; traps = trap rules (habit, contradiction, look_alike, one_off, "
               "cold_chain) among passed lessons",
    "bar": {
        "B1": "mean recall at 90 days >= mean recall at 30 days (fixed denominator, mean over the 3 repeats)",
        "B2": "precision at 90 days >= 0.85, pooled over the 3 repeats (true passed / passed)",
        "B3": "0 trap rules admitted in every run at every length",
        "verdict": "met only if B1, B2 and B3 are all met; a miss is reported as a miss",
    },
    "reported_not_judged": "60 days; recall against only the rules with any evidence by the cutoff (same learnable "
                           "definition as evaluate.Truth, restricted to records up to the cutoff); rules found per "
                           "length; proposals, passed, false lessons; digest size; cost",
    "partial": "if the budget stops the run, only lengths with at least one completed repeat are judged and the result "
               "is labelled partial",
    "budget": "hard cap $1.50 total Meta spend: 1 smoke call (30 days, not part of the result) + main run capped at $1.40 "
              "in the script (stops before a call that could pass it). Meta API only; baseten_api_key blanked.",
    "caveats": "one company, one generated world, hidden rules from our own generator; temperature 0 so repeats "
               "measure only API nondeterminism; fewer rules have any evidence in 30 days, so fixed-denominator recall "
               "mixes 'not learnable yet' with 'missed'; the visible-by-cutoff recall separates them.",
}


def file_hashes():
    h = exp_freeze.hashes(SCRIPT)
    for f in EXTRA:
        h[f] = hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]
    return h


def freeze():
    h = file_hashes()
    plan_text = json.dumps(PLAN, sort_keys=True, ensure_ascii=False)
    doc = dict(h) | {"plan": PLAN, "plan_sha256": hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16],
                     "frozen_at": datetime.now().isoformat(timespec="seconds")}
    exp_freeze.path(TAG).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def check():
    p = exp_freeze.path(TAG)
    if not p.exists():
        sys.exit(f"refusing to run: {p.name} is missing; pre-register and freeze first")
    frozen = json.loads(p.read_text(encoding="utf-8"))
    changed = [f for f, h in file_hashes().items() if frozen.get(f) != h]
    if changed:
        sys.exit(f"refusing to run: frozen files changed: {changed}")
    if json.dumps(frozen.get("plan"), sort_keys=True, ensure_ascii=False) != json.dumps(PLAN, sort_keys=True, ensure_ascii=False):
        sys.exit("refusing to run: the plan differs from the frozen plan")


def cutoffs(C):
    start = date.fromisoformat(json.loads((C_world() / "manifest.json").read_text(encoding="utf-8"))["window"][0])
    return {n: (start + timedelta(days=n - 1)).isoformat() for n in LENGTHS}


def C_world():
    return Path(DEFAULT_WORLD)


def as_of(C, until):
    """The company view as of the end of `until`: every record list cut with digest.Facts' rule; today = next day."""
    cut = until + "T99"
    keep = lambda r: (r.get("ts") or r.get("arrived_at") or r.get("confirmed_at") or r.get("planned_at") or "") <= cut
    V = copy.copy(C)
    V.t = {k: [r for r in v if keep(r)] if isinstance(v, list) else v for k, v in C.t.items()}
    V.today = (date.fromisoformat(until) + timedelta(days=1)).isoformat()
    return V


def build(V):
    F = digest.Facts(V)
    return F, {"sites": digest.site_digest(F), "phrases": digest.phrase_digest(F), "vehicles": digest.vehicle_digest(F),
               "vendors": digest.vendor_digest(F), "delays": digest.delay_digest(F)}


def visible(truth, world, company, until):
    """evaluate.Truth.learnable, restricted to the truth records up to the end of `until`."""
    cut = until + "T99"
    con = sqlite3.connect(Path(world) / "truth" / "canonical.sqlite")
    traces = defaultdict(int)
    for table, col in (("trip_outcomes", "arrived_at"), ("trip_events", "ts"), ("vehicle_placements", "confirmed_at")):
        for rid, ts in con.execute(f"select rule_id, {col} from {table} where company = ? and rule_id is not null", (company,)):
            if (ts or "") <= cut:
                traces[rid] += 1
    mentions = defaultdict(int)
    for text, ts in con.execute("select text, ts from planner_messages where company = ?", (company,)):
        if (ts or "") > cut:
            continue
        for rid, rule in truth.rules.items():
            if rule["kind"] == "alias" and company in rule["companies"] and rule["phrase"].lower() in text.lower():
                mentions[rid] += 1
    con.close()
    out = []
    for rid in truth.learnable(company):
        r = truth.rules[rid]
        if r["kind"] == "alias" and mentions[rid] >= 2 or traces[rid] >= 1:
            out.append(rid)
    return sorted(out), dict(traces), dict(mentions)


def summarize(rows, truth):
    learn_all = truth.learnable(COMPANY)
    by = {}
    for n in LENGTHS:
        rs = [r for r in rows if r["days"] == n]
        if not rs:
            continue
        passed = sum(r["passed"] for r in rs)
        true_passed = sum(r["true_passed"] for r in rs)
        by[n] = {"runs": len(rs), "cutoff": rs[0]["cutoff"],
                 "recall_mean": round(sum(r["recall"] or 0 for r in rs) / len(rs), 3),
                 "recall_per_run": [r["recall"] for r in rs],
                 "recall_visible_mean": round(sum(r["recall_visible"] or 0 for r in rs) / len(rs), 3),
                 "visible_rules": rs[0]["visible"], "learnable_all": learn_all,
                 "precision_pooled": round(true_passed / passed, 3) if passed else None,
                 "precision_per_run": [r["precision"] for r in rs],
                 "passed": passed, "true_passed": true_passed, "proposed": sum(r["proposed"] for r in rs),
                 "traps_admitted": sorted({t for r in rs for t in r["traps_admitted"]}),
                 "found_any_run": sorted({f for r in rs for f in r["found"]}),
                 "false_lessons": sum(len(r["false_lessons"]) for r in rs),
                 "cost_usd": round(sum(r["cost_usd"] for r in rs), 4)}
    v = {}
    if 30 in by and 90 in by:
        v["B1"] = by[90]["recall_mean"] >= by[30]["recall_mean"]
    if 90 in by:
        v["B2"] = by[90]["precision_pooled"] is not None and by[90]["precision_pooled"] >= 0.85
    v["B3"] = all(not r["traps_admitted"] for r in rows)
    complete = all(by.get(n, {}).get("runs") == REPEATS for n in LENGTHS)
    v["met"] = all(v.get(k) for k in ("B1", "B2", "B3"))
    v["partial"] = not complete
    return by, v


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--budget", type=float, default=1.40)
    ap.add_argument("--resume")
    a = ap.parse_args(argv)
    world = C_world()
    truth = evaluate.Truth(world)
    C = CompanyData(world, COMPANY, OUT / "rt18")
    cuts = cutoffs(C)

    if a.freeze:
        print(json.dumps(freeze(), indent=1, ensure_ascii=False))
        return

    if a.dry:
        full = sum(len(v) for v in C.t.values() if isinstance(v, list))
        for n, until in cuts.items():
            V = as_of(C, until)
            F, d = build(V)
            vis, _, _ = visible(truth, world, COMPANY, until)
            prompt = miner.PROMPT.format(company=V.company, today=V.today, kinds=miner.KINDS, **d)
            kept = sum(len(v) for v in V.t.values() if isinstance(v, list))
            print(f"{n} days (to {until}, today {V.today}): records kept {kept}/{full}, visits {len(F.visits)}, "
                  f"prompt {len(prompt)} chars, rules with evidence {len(vis)}/{len(truth.learnable(COMPANY))}: {vis}")
        print("traps for T01:", truth.traps(COMPANY))
        return

    check()
    if os.environ.get("baseten_api_key", "").strip():
        sys.exit("refusing to run: blank baseten_api_key (Meta API only)")
    client = muse.client("spark")
    assert isinstance(client, muse.MuseClient) and client.model == muse.DEFAULT_MODEL and "meta.ai" in str(client._client.base_url)

    if a.smoke:
        V = as_of(C, cuts[30])
        F, d = build(V)
        props, meta = miner.mine(client, V, d)
        print(f"smoke: model {meta['model']}, {len(props)} proposals, ${meta['cost_usd']:.4f}, {meta['latency_s']} s, "
              f"{meta['tokens_in']} in / {meta['tokens_out']} out")
        p = OUT / f"{TAG}_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        p.write_text(json.dumps({"meta": meta, "proposals": props}, indent=1, ensure_ascii=False), encoding="utf-8")
        print("saved", p.relative_to(ROOT))
        return

    stamp = a.resume or datetime.now().strftime("%Y%m%d_%H%M%S")
    rows_path = OUT / f"{TAG}_{stamp}_rows.jsonl"
    rows = [json.loads(x) for x in rows_path.read_text(encoding="utf-8").splitlines()] if rows_path.exists() else []
    done = {(r["days"], r["rep"]) for r in rows}
    store = LessonStore(OUT / f"{TAG}_{stamp}_lessons.sqlite")
    spent = sum(r["cost_usd"] for r in rows)
    worst = max([r["cost_usd"] for r in rows] + [0.10])
    stopped = None
    for rep in range(REPEATS):
        for n in LENGTHS:
            if (n, rep) in done:
                continue
            if spent + worst > a.budget:
                stopped = f"budget: ${spent:.3f} spent, next call could pass ${a.budget:.2f}"
                break
            until = cuts[n]
            V = as_of(C, until)
            F, d = build(V)
            props, meta = miner.mine(client, V, d)
            spent += meta["cost_usd"]
            worst = max(worst, meta["cost_usd"])
            key = f"{COMPANY}@d{n}r{rep}"
            store.add_proposals(key, F, props, meta)
            s = evaluate.score(truth, COMPANY, store.list(key))
            vis, _, _ = visible(truth, world, COMPANY, until)
            true_passed = sum(1 for r in s["rows"] if r["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "EXPIRED") and r["matches"] and not r["trap"])
            row = {"days": n, "rep": rep, "cutoff": until, "today": V.today, "visible": vis,
                   "recall_visible": round(len(set(s["found"]) & set(vis)) / len(vis), 3) if vis else None,
                   "true_passed": true_passed, "cost_usd": meta["cost_usd"], "meta": meta,
                   **{k: v for k, v in s.items()}}
            rows.append(row)
            with rows_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            print(f"{n}d rep{rep}: proposed {s['proposed']}, passed {s['passed']}, precision {s['precision']}, "
                  f"recall {s['recall']} (visible {row['recall_visible']}; found {s['found']}), traps {s['traps_admitted']}, "
                  f"false {len(s['false_lessons'])}, ${meta['cost_usd']:.4f} (total ${spent:.3f})", flush=True)
        if stopped:
            break
    by, verdict = summarize(rows, truth)
    out = {"stamp": stamp, "tag": TAG, "plan": PLAN, "model": muse.DEFAULT_MODEL, "world": str(world.relative_to(ROOT)),
           "company": COMPANY, "cutoffs": cuts, "per_length": by, "verdict": verdict, "stopped": stopped,
           "cost_usd": round(spent, 4), "runs": len(rows)}
    p = OUT / f"{TAG}_{stamp}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    for n, b in by.items():
        print(f"{n} days: recall {b['recall_mean']} (visible {b['recall_visible_mean']}), precision {b['precision_pooled']}, "
              f"traps {b['traps_admitted']}, ${b['cost_usd']}")
    print("verdict:", verdict, "| stopped:", stopped, f"| ${spent:.3f}")
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
