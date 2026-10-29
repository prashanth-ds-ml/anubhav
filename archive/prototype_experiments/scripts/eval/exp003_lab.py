"""EXP-003: Business Operations Lab head-to-head (project-selection experiment).

Five frozen stock-allocation scenarios (datasets/lab/exp003_scenarios.json) with operator instructions in
Telugu / Roman Telugu / mixed. Methods:
  greedy          basic FIFO by order received, stock only, ignores instructions
  heuristic_base  strong constraint-aware heuristic, data only (no instructions)
  heuristic_gold  strong heuristic with the correct (gold) reading of the instructions
  optimum_gold    exact ILP optimum with the gold reading (upper bound)
  muse_oneshot    Muse plans directly from data + instructions
  muse_feedback   Muse revises its plan up to 2 times with simulator feedback; the simulator checks against
                  Muse's OWN extracted constraints (never the gold ones), as a real Lab would
  hybrid          Muse extracts constraints, the ILP optimizes them
Every plan is scored against the gold constraints with the frozen rules below.

Usage: uv run python scripts/eval/exp003_lab.py --repeats 3
"""

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pulp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from order_agent.llm import MuseClient  # noqa: E402

SCENARIOS = ROOT / "datasets" / "lab" / "exp003_scenarios.json"
WEIGHT = {"gold": 3, "silver": 2, "bronze": 1}
VALUE = {"now": 1.0, "sub": 0.9, "bo": 0.5}  # value of a primary-case equivalent by source

RULES = """Allocation rules (hard constraints):
1. Per source, total allocated cases cannot exceed what is available: primary stock now, substitute stock now, and restock cases.
2. A customer's allocation (now + substitute/ratio + backorder, in primary-case equivalents) cannot exceed the cases they want.
   `substitute_cases_per_primary_case` says how many substitute cases replace one primary case.
3. Credit customers (payment_terms not 'cash'): outstanding + value of all allocated cases incl. GST must not exceed the credit limit.
   Value = cases x the customer's case price (primary or substitute) x (1 + GST). Cash customers have no limit.
4. Customers on credit_status 'hold' get nothing.
5. Backorder cases come only from the restock, and only if the restock date is on or before the customer's deadline (if any).
6. Substitutes are allowed unless the operator says otherwise. Cancelled orders get nothing. "Full" orders must be filled completely.
7. Operator instructions override the data (quantities, cancellations, holds, credit limits, substitutes, deadlines).
Objective: maximise weighted fulfillment = sum over customers of weight x (now + 0.9 x substitute/ratio + 0.5 x backorder)
divided by sum of weight x wanted cases. Weights: gold 3, silver 2, bronze 1."""


# ---------- constraints and scoring
def effective(scn, constraints):
    """Per-customer parameters after applying a constraint set ({customer_id: overrides})."""
    out = {}
    for r in scn["requests"]:
        c = constraints.get(r["customer_id"], {})
        hold = r["credit_status"] == "hold" and not c.get("hold_lifted")
        outstanding = c.get("outstanding_rs", r["outstanding_rs"])
        out[r["customer_id"]] = {
            "req": 0 if c.get("cancel") else c.get("cases", r["requested_cases"]),
            "w": WEIGHT[r["tier"]], "order": r["received_order"],
            "can_sub": not c.get("no_substitute"), "deadline": c.get("deadline"),
            "must_fill": bool(c.get("must_fill")) and not c.get("cancel"), "hold": hold,
            "credit": r["payment_terms"] != "cash",
            "headroom": r["credit_limit_rs"] + c.get("credit_limit_add_rs", 0) - outstanding,
            "p": r["case_price_rs"], "p_sub": r["substitute_case_price_rs"],
        }
    return out


def bo_allowed(scn, e):
    rs = scn["restock"]
    return bool(rs) and (e["deadline"] is None or rs["date"] <= e["deadline"])


def evaluate(scn, plan, constraints):
    """Score a plan {customer_id: {now, sub, bo}} against a constraint set."""
    eff, gst = effective(scn, constraints), 1 + scn["primary"]["gst_pct"] / 100
    ratio = scn["substitute"]["substitute_cases_per_primary_case"]
    v = []
    alloc = {cid: {k: plan.get(cid, {}).get(k, 0) for k in ("now", "sub", "bo")} for cid in eff}
    for cid in plan:
        if cid not in eff:
            v.append(f"{cid}: not a requesting customer")
    for cid, a in alloc.items():
        if any((not isinstance(x, int)) or x < 0 for x in a.values()):
            v.append(f"{cid}: allocations must be whole, non-negative cases")
            a.update({k: max(0, int(x)) if isinstance(x, (int, float)) else 0 for k, x in a.items()})
    for src, cap in (("now", scn["primary"]["stock_cases"]), ("sub", scn["substitute"]["stock_cases"]),
                     ("bo", (scn["restock"] or {}).get("cases", 0))):
        total = sum(a[src] for a in alloc.values())
        if total > cap:
            v.append(f"{src}: {total} cases allocated, only {cap} available")
    num = den = revenue_now = revenue_bo = 0.0
    for cid, a in alloc.items():
        e = eff[cid]
        equiv = a["now"] + a["sub"] / ratio + a["bo"]
        if equiv > e["req"] + 1e-9:
            v.append(f"{cid}: {equiv:g} cases allocated, wants {e['req']}")
        if e["hold"] and equiv > 0:
            v.append(f"{cid}: on credit hold, must get nothing")
        if not e["can_sub"] and a["sub"]:
            v.append(f"{cid}: must not receive substitutes")
        if a["bo"] and not bo_allowed(scn, e):
            v.append(f"{cid}: backorder not allowed (no restock, or restock after deadline {e['deadline']})")
        if e["must_fill"] and abs(equiv - e["req"]) > 1e-9:
            v.append(f"{cid}: must be filled in full ({e['req']}), got {equiv:g}")
        value = (a["now"] * e["p"] + a["sub"] * e["p_sub"] + a["bo"] * e["p"]) * gst
        if e["credit"] and value > e["headroom"] + 1e-6:
            v.append(f"{cid}: value Rs {value:,.0f} exceeds credit headroom Rs {e['headroom']:,.0f}")
        num += e["w"] * (a["now"] * VALUE["now"] + a["sub"] / ratio * VALUE["sub"] + a["bo"] * VALUE["bo"])
        den += e["w"] * e["req"]
        revenue_now += (a["now"] * e["p"] + a["sub"] * e["p_sub"]) * gst
        revenue_bo += a["bo"] * e["p"] * gst
    wf = num / den if den else 0.0
    return {"feasible": not v, "violations": v, "weighted_fulfillment": round(wf, 4),
            "score": round(wf, 4) if not v else 0.0, "revenue_now_rs": round(revenue_now), "revenue_backorder_rs": round(revenue_bo)}


# ---------- conventional methods
def greedy(scn, _constraints=None):
    stock, plan = scn["primary"]["stock_cases"], {}
    for r in sorted(scn["requests"], key=lambda r: r["received_order"]):
        take = min(stock, r["requested_cases"])
        plan[r["customer_id"]] = {"now": take, "sub": 0, "bo": 0}
        stock -= take
    return plan


def heuristic(scn, constraints):
    """Constraint-aware: must-fill first, then customers who refuse substitutes, then by weight and order;
    each takes primary stock, then substitute, then backorder, within credit headroom."""
    eff, gst = effective(scn, constraints), 1 + scn["primary"]["gst_pct"] / 100
    ratio = scn["substitute"]["substitute_cases_per_primary_case"]
    left = {"now": scn["primary"]["stock_cases"], "sub": scn["substitute"]["stock_cases"],
            "bo": (scn["restock"] or {}).get("cases", 0)}
    plan = {}
    for cid, e in sorted(eff.items(), key=lambda kv: (not kv[1]["must_fill"], kv[1]["can_sub"], -kv[1]["w"], kv[1]["order"])):
        a = {"now": 0, "sub": 0, "bo": 0}
        if not e["hold"] and e["req"]:
            room = e["headroom"] if e["credit"] else math.inf
            need = e["req"]
            a["now"] = min(need, left["now"], int(room // (e["p"] * gst)) if e["credit"] else need)
            need, room = need - a["now"], room - a["now"] * e["p"] * gst
            if e["can_sub"] and need:
                a["sub"] = min(need * ratio, left["sub"], int(room // (e["p_sub"] * gst)) if e["credit"] else need * ratio)
                need, room = need - a["sub"] / ratio, room - a["sub"] * e["p_sub"] * gst
            if bo_allowed(scn, e) and need > 0:
                a["bo"] = min(math.floor(need), left["bo"], int(room // (e["p"] * gst)) if e["credit"] else math.floor(need))
        for k in left:
            left[k] -= a[k]
        plan[cid] = a
    return plan


def optimum(scn, constraints):
    eff, gst = effective(scn, constraints), 1 + scn["primary"]["gst_pct"] / 100
    ratio = scn["substitute"]["substitute_cases_per_primary_case"]
    m = pulp.LpProblem("alloc", pulp.LpMaximize)
    x = {(c, k): m.add_variable(f"{k}_{c.replace('-', '')}", lowBound=0, cat="Integer") for c in eff for k in ("now", "sub", "bo")}
    den = sum(e["w"] * e["req"] for e in eff.values()) or 1
    m += pulp.lpSum(e["w"] / den * (x[c, "now"] + VALUE["sub"] / ratio * x[c, "sub"] + VALUE["bo"] * x[c, "bo"])
                    + 1e-9 * e["p"] * (x[c, "now"] + x[c, "bo"]) for c, e in eff.items())
    m += pulp.lpSum(x[c, "now"] for c in eff) <= scn["primary"]["stock_cases"]
    m += pulp.lpSum(x[c, "sub"] for c in eff) <= scn["substitute"]["stock_cases"]
    m += pulp.lpSum(x[c, "bo"] for c in eff) <= (scn["restock"] or {}).get("cases", 0)
    for c, e in eff.items():
        units = ratio * x[c, "now"] + x[c, "sub"] + ratio * x[c, "bo"]
        m += units <= ratio * (0 if e["hold"] else e["req"])
        if e["must_fill"]:
            m += units == ratio * e["req"]
        if not e["can_sub"]:
            m += x[c, "sub"] == 0
        if not bo_allowed(scn, e):
            m += x[c, "bo"] == 0
        if e["credit"]:
            m += (e["p"] * (x[c, "now"] + x[c, "bo"]) + e["p_sub"] * x[c, "sub"]) * gst <= e["headroom"]
    stats = m.solve(pulp.HiGHS(msg=False))
    if stats.status != pulp.LpSolveStatus.Optimal:
        return {}
    return {c: {k: int(round(x[c, k].value())) for k in ("now", "sub", "bo")} for c in eff}


# ---------- Muse
def public_view(scn):
    """What Muse sees: everything except the gold constraints and the design note."""
    return {k: v for k, v in scn.items() if k not in ("gold_constraints", "design_note")}


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else None


PLAN_FORMAT = ('Reply with JSON only: {"allocations": [{"customer_id": "...", "now_cases": 0, "substitute_cases": 0, '
               '"backorder_cases": 0}], "notes": "one line"}. Include every requesting customer.')

EXTRACT_FORMAT = ('Reply with JSON only: {"constraints": {"<customer_id>": {...}}} listing only customers the instructions change, '
                  'using only these keys: cancel (true), cases (new wanted cases), no_substitute (true), deadline (YYYY-MM-DD), '
                  'must_fill (true), hold_lifted (true), outstanding_rs (new outstanding), credit_limit_add_rs (amount added).')


def to_plan(obj):
    plan = {}
    for a in (obj or {}).get("allocations", []):
        plan[a.get("customer_id")] = {"now": a.get("now_cases", 0), "sub": a.get("substitute_cases", 0), "bo": a.get("backorder_cases", 0)}
    return plan


class Meter:
    def __init__(self, client):
        self.client, self.cost, self.latency, self.calls = client, 0.0, 0.0, 0

    def ask(self, messages):
        r = self.client.chat(messages, None, temperature=0)
        self.cost, self.latency, self.calls = self.cost + r.cost_usd, self.latency + r.latency_s, self.calls + 1
        return r.content or ""


def muse_extract(meter, scn):
    msg = [{"role": "system", "content": "You read a wholesale distributor operator's instructions (Telugu, Roman Telugu, English) "
            "and turn them into structured allocation constraints. " + EXTRACT_FORMAT},
           {"role": "user", "content": json.dumps({"business_date": scn["business_date"], "requests": public_view(scn)["requests"],
                                                   "instructions": scn["instructions"]}, ensure_ascii=False)}]
    obj = parse_json(meter.ask(msg))
    return (obj or {}).get("constraints", {}) if isinstance(obj, dict) else {}


def muse_plans(meter, scn, own_constraints):
    """One-shot plan, then up to 2 revisions with simulator feedback against Muse's own constraints."""
    msgs = [{"role": "system", "content": "You are the stock-allocation planner of a wholesale distributor. " + RULES + "\n" + PLAN_FORMAT},
            {"role": "user", "content": json.dumps(public_view(scn), ensure_ascii=False)}]
    text = meter.ask(msgs)
    plans = [to_plan(parse_json(text))]
    for _ in range(2):
        fb = evaluate(scn, plans[-1], own_constraints)
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": "Simulator result for your plan: " + json.dumps(
                     {k: fb[k] for k in ("feasible", "violations", "weighted_fulfillment", "revenue_now_rs", "revenue_backorder_rs")})
                  + " Fix any violations and improve weighted fulfillment if you can; otherwise return the same plan. " + PLAN_FORMAT}]
        text = meter.ask(msgs)
        plans.append(to_plan(parse_json(text)) or plans[-1])
    return plans


def norm(constraints):
    out = {}
    for cid, c in (constraints or {}).items():
        keep = {k: v for k, v in (c or {}).items() if v not in (None, False, "", 0) or k == "outstanding_rs"}
        if keep:
            out[cid] = keep
    return out


def extraction_accuracy(got, gold):
    got, gold = norm(got), norm(gold)
    keys = {(c, k) for c, d in gold.items() for k in d} | {(c, k) for c, d in got.items() for k in d}
    right = sum(got.get(c, {}).get(k) == gold.get(c, {}).get(k) for c, k in keys)
    return right, len(keys)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--no-muse", action="store_true", help="conventional methods only (dry run, no API calls)")
    args = ap.parse_args()
    if args.no_muse:
        args.repeats = 0
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    client = MuseClient(model=args.model)
    rows, details = [], []
    for scn in scenarios:
        gold = scn["gold_constraints"]
        t0 = time.perf_counter()
        conv = {"greedy": greedy(scn), "heuristic_base": heuristic(scn, {}), "heuristic_gold": heuristic(scn, gold),
                "optimum_gold": optimum(scn, gold)}
        conv_ms = (time.perf_counter() - t0) * 1000
        for name, plan in conv.items():
            rows.append({"scenario": scn["id"], "method": name, "repeat": 0, **evaluate(scn, plan, gold),
                         "cost_usd": 0.0, "latency_s": round(conv_ms / 4000, 4), "plan": plan})
        for rep in range(args.repeats):
            meter = Meter(client)
            extracted = muse_extract(meter, scn)
            right, total = extraction_accuracy(extracted, gold)
            ext_cost, ext_lat = meter.cost, meter.latency
            plans = muse_plans(meter, scn, extracted)
            plan_cost, plan_lat = meter.cost - ext_cost, meter.latency - ext_lat
            hybrid = optimum(scn, extracted)
            for name, plan, cost, lat in (("muse_oneshot", plans[0], plan_cost / 3, plan_lat / 3),
                                          ("muse_feedback", plans[-1], plan_cost + ext_cost, plan_lat + ext_lat),
                                          ("hybrid", hybrid, ext_cost, ext_lat)):
                rows.append({"scenario": scn["id"], "method": name, "repeat": rep, **evaluate(scn, plan, gold),
                             "cost_usd": round(cost, 5), "latency_s": round(lat, 2), "plan": plan})
            details.append({"scenario": scn["id"], "repeat": rep, "extracted": extracted, "extraction_right": right,
                            "extraction_total": total, "plans": plans})
            print(f"{scn['id']}#{rep}: extraction {right}/{total} · one-shot {rows[-3]['score']:.3f} · "
                  f"feedback {rows[-2]['score']:.3f} · hybrid {rows[-1]['score']:.3f}", flush=True)

    report(rows, details, scenarios)
    if args.no_muse:
        for r in rows:
            print(r["scenario"], f"{r['method']:15}", r["score"], r["violations"][:2], r["plan"])
        return
    out = ROOT / "artifacts" / "lab" / f"exp003_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "rows": rows, "details": details}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {out.relative_to(ROOT)}")


def report(rows, details, scenarios):
    methods = ["greedy", "heuristic_base", "heuristic_gold", "optimum_gold", "muse_oneshot", "muse_feedback", "hybrid"]
    print("\nMean score (weighted fulfillment if feasible, else 0) by scenario:")
    print(f"{'method':16}" + "".join(f"{s['id']:>8}" for s in scenarios) + f"{'mean':>8}{'feasible':>10}{'$/run':>9}{'s/run':>8}")
    for m in methods:
        mr = [r for r in rows if r["method"] == m]
        if not mr:
            continue
        cells = []
        for s in scenarios:
            sr = [r["score"] for r in mr if r["scenario"] == s["id"]]
            cells.append(sum(sr) / len(sr))
        feas = sum(r["feasible"] for r in mr) / len(mr)
        print(f"{m:16}" + "".join(f"{c:8.3f}" for c in cells) + f"{sum(cells) / len(cells):8.3f}{feas:10.0%}"
              f"{sum(r['cost_usd'] for r in mr) / len(mr):9.4f}{sum(r['latency_s'] for r in mr) / len(mr):8.1f}")
    right = sum(d["extraction_right"] for d in details)
    total = sum(d["extraction_total"] for d in details)
    if not details:
        return
    print(f"\nMuse instruction extraction: {right}/{total} fields correct ({right / total:.0%}); "
          f"scenarios fully correct: {sum(d['extraction_right'] == d['extraction_total'] for d in details)}/{len(details)}")
    print("\nViolations in Muse plans:")
    for r in rows:
        if r["method"].startswith("muse") and r["violations"]:
            print(f"  {r['scenario']}#{r['repeat']} {r['method']}: {r['violations']}")


if __name__ == "__main__":
    main()
