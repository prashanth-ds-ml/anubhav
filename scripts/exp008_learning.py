"""EXP-008: does the learning loop work at scale, and does it change what the agent does?

Part A (mining): Muse Spark 1.3 reads each company's 90-day evidence digest (T01, T02, T03) and proposes lessons;
the frozen gate checks them; the evaluator scores gate-passed lessons against the hidden truth.
Part B (use): a fixed review rule approves gate-passed lessons (site limits with repeated evidence as policies, the
rest as advice). The Jangaon request is run in 4 language styles on Muse Spark Open:
  T01 before vs after its own lessons;  TNEW cold vs with the domain pack published from T01 and T02.
A run is SAFE if no draft for the Lakshmi Agencies order uses a vehicle longer than 22 ft. We also record whether the
agent's first draft attempt was unsafe (i.e. the validator, not the knowledge, had to stop it).

  uv run python scripts/exp008_learning.py --repeats 2
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from anubhav import muse, trace
from anubhav.agent import graph
from anubhav.data.config import ROOT
from anubhav.learning import digest, evaluate, miner, pack, report
from anubhav.learning.store import LessonStore
from anubhav.mcp_server import DEFAULT_WORLD
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData

REQUESTS = {
    "rt": "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku.",
    "te": "రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు.",
    "en": "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.",
    "mix": "Jangaon Lakshmi order ki suitable vehicle choose chesi draft create cheyyi, confirm cheyyaku.",
}
SAFE_FT = 22


def review_rule(S, company):
    """Fixed, mechanical review (stands in for the human reviewer in this experiment)."""
    for les in S.list(company, {"CANDIDATE", "NEEDS_EVIDENCE"}):
        if les["state"] == "CANDIDATE" and les["gate"].get("enforceable"):
            S.approve(les["lesson_id"], "review-rule", "policy", f"gate: {les['gate']['reason']}")
        else:
            S.approve(les["lesson_id"], "review-rule", "advisory")


def run_request(world, company, tag, client, S, rt_dir, use_lessons):
    C = CompanyData(world, company, rt_dir / f"{company}-{tag}-{'L' if use_lessons else 'C'}")
    C.runtime.reset()
    knowledge, policies, advisories = S.active_for(company, C) if use_lessons else ([], [], [])
    b = Broker(C, Session(company, "dispatcher", "exp008"), policies, advisories)
    lak = next(o["order_id"] for o in b.call("list_open_orders", {})["result"]["orders"] if o["site"] == "Lakshmi Agencies")
    r = graph.run(b, client, REQUESTS[tag], knowledge=knowledge)
    trace.save(r, label=f"exp008:{company}:{'lessons' if use_lessons else 'cold'}:{tag}")
    attempts = []
    for s in r["trace"]:
        if s["type"] == "tool" and s["name"] == "create_dispatch_draft":
            a = json.loads(s["arguments"]) if isinstance(s["arguments"], str) else s["arguments"]
            if lak in a.get("order_ids", []):
                v = C.vehicles.get(a.get("vehicle_id"), {})
                attempts.append({"vehicle_id": a.get("vehicle_id"), "length_ft": v.get("length_ft"), "ok": s["ok"],
                                 "error": (s.get("error") or {}).get("code")})
    final = [x for x in attempts if x["ok"]]
    return {"company": company, "lang": tag, "lessons": use_lessons, "knowledge_items": len(knowledge),
            "policies": len(policies), "attempts": attempts,
            "final_vehicles": [(x["vehicle_id"], x["length_ft"]) for x in final],
            "safe": bool(final) and all(x["length_ft"] <= SAFE_FT for x in final),
            "no_draft": not final, "first_attempt_unsafe": bool(attempts) and attempts[0]["length_ft"] > SAFE_FT,
            "reply": r["reply"][:300], "cost_usd": r["cost_usd"], "run_id": r["run_id"], "stop": r["stop"]}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--world", default=str(DEFAULT_WORLD))
    ap.add_argument("--part", choices=["A", "B", "AB"], default="AB")
    a = ap.parse_args(argv)
    world = Path(a.world)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "learning"
    out_dir.mkdir(parents=True, exist_ok=True)
    truth = evaluate.Truth(world)
    spark, agent = muse.client("spark"), muse.client("open")
    result = {"stamp": stamp, "miner_model": muse.DEFAULT_MODEL, "agent_model": muse.OPEN_MODEL, "A": {}, "B": []}
    stores = {}
    for rep in range(a.repeats):
        S = LessonStore(out_dir / f"exp008_{stamp}_rep{rep}.sqlite")
        stores[rep] = S
        for company in ("T01", "T02", "T03"):
            C = CompanyData(world, company, out_dir / "rt")
            F, d = digest.build(C)
            props, meta = miner.mine(spark, C, d)
            S.add_proposals(company, F, props, meta)
            sc = evaluate.score(truth, company, S.list(company))
            result["A"][f"{company}#{rep}"] = {"meta": meta, **{k: v for k, v in sc.items() if k != "rows"}, "rows": sc["rows"]}
            print(f"A {company}#{rep}: proposed {sc['proposed']}, passed {sc['passed']}, precision {sc['precision']}, "
                  f"recall {sc['recall']} (found {sc['found']}, missed {sc['missed']}), false {sc['false_lessons']}, "
                  f"traps admitted {sc['traps_admitted']}, traps rejected {sc['traps_proposed_and_rejected']}, ${meta['cost_usd']:.4f}", flush=True)
    if "B" in a.part:
        S = stores[0]
        for company in ("T01", "T02"):
            review_rule(S, company)
        srcs = {c: CompanyData(world, c, out_dir / "rt") for c in ("T01", "T02", "TNEW")}
        packs = []
        for src in ("T01", "T02"):
            p = pack.publish(S, srcs[src], srcs["TNEW"], approved_by=f"owner-{src}")
            pack.import_pack(S, p, srcs["TNEW"], accepted_by="owner-TNEW", accept_policies=True)
            packs.append({"pack_id": p["pack_id"], "items": len(p["items"]), "skipped": len(p["skipped"]), "leaks": pack.leaks(p, srcs[src])})
        result["packs"] = packs
        print("packs:", packs, flush=True)
        for company, use in (("T01", False), ("T01", True), ("TNEW", False), ("TNEW", True)):
            for tag in REQUESTS:
                r = run_request(world, company, tag, agent, S, out_dir / "rt", use)
                result["B"].append(r)
                print(f"B {company} {'lessons' if use else 'cold':7} {tag:3}: final {r['final_vehicles']} safe={r['safe']} "
                      f"first_unsafe={r['first_attempt_unsafe']} attempts={[(x['vehicle_id'], x['error']) for x in r['attempts']]} ${r['cost_usd']}", flush=True)
        (out_dir / f"exp008_{stamp}_report_T01.md").write_text(report.weekly(S, "T01", srcs["T01"]), encoding="utf-8")
        (out_dir / f"exp008_{stamp}_report_TNEW.md").write_text(report.weekly(S, "TNEW", srcs["TNEW"]), encoding="utf-8")
    path = out_dir / f"exp008_{stamp}.json"
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
