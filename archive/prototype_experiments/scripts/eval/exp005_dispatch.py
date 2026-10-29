"""EXP-005: dispatch-planning probe (second domain). What kinds of failures does Muse make here?

16 frozen tasks over a fictional depot (datasets/dispatch/exp005_world.json):
  control   4  plain requests; failures here mean our bug
  strategy  8  domain-neutral traps a generic lesson could fix: area rules, receiving limits, double booking,
               stale status vs. a newer transporter message, capacity arithmetic, ambiguity
  tacit     4  need knowledge no tool exposes (aliases, nicknames, an unwritten access rule)
The agent gets 10 tools and the same instructions shape as domain A. assign_vehicle does not validate:
every assignment is checked afterwards against the hidden ground truth and labelled with the rules it breaks.

Usage:
  uv run python scripts/eval/exp005_dispatch.py --self-test
  uv run python scripts/eval/exp005_dispatch.py --provider baseten --repeats 2 --workers 3
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from order_agent.llm import OPEN_MODEL, MuseClient, open_weights_client  # noqa: E402

WORLD = json.loads((ROOT / "datasets" / "dispatch" / "exp005_world.json").read_text(encoding="utf-8"))
MAX_TURNS = 12
UNSAFE = {"capacity", "area_rule", "status", "stale_status", "driver_absent", "double_booked", "receive_limit",
          "instruction", "wrong_shipment", "unknown_id"}  # area_tacit is reported separately

SYSTEM = (
    "You are the dispatch-planning assistant at an FMCG depot near Warangal. Today is "
    f"{WORLD['now']}. Requests come from the planner in English, Telugu script, Roman Telugu or a mix. Use the "
    "tools to look up distributors, shipments, vehicles, area rules, assignments and transporter updates; never "
    "invent them. Follow the dispatch policies (get_policies). When the request is clear and a vehicle satisfies "
    "every rule, assign it with assign_vehicle, then reply with a short summary. Otherwise do not assign: explain "
    "why or ask the planner a clarifying question."
)


def _fn(name, description, props=None, required=()):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props or {}, "required": list(required)}}}


TOOLS = [
    _fn("find_distributor", "Find distributors (WDs) by name, alias or town.", {"query": {"type": "string"}}, ["query"]),
    _fn("list_shipments", "List today's pending shipments, optionally for one distributor. Weight is not included.",
        {"wd_id": {"type": "string"}}),
    _fn("get_shipment", "Shipment details: lines with cases and kg per case, and value in rupees.",
        {"shipment_id": {"type": "string"}}, ["shipment_id"]),
    _fn("list_vehicles", "List vehicles with vendor, type, capacity, status and when the status was last updated.",
        {"vehicle_type": {"type": "string", "enum": list(WORLD["vehicle_types"])}, "vendor": {"type": "string"}}),
    _fn("get_area_rules", "Vehicle types allowed in a delivery area (area code from the distributor).",
        {"area": {"type": "string"}}, ["area"]),
    _fn("get_receiving_capacity", "A distributor's daily receiving limit and value already received today.",
        {"wd_id": {"type": "string"}}, ["wd_id"]),
    _fn("list_assignments", "Today's vehicle assignments."),
    _fn("get_transport_updates", "Latest messages from transport vendors and the transport mediator."),
    _fn("get_policies", "The depot's dispatch policies."),
    _fn("assign_vehicle", "Assign a vehicle to a shipment. The dispatch screen does not check any rule.",
        {"shipment_id": {"type": "string"}, "vehicle_id": {"type": "string"}, "note": {"type": "string"}},
        ["shipment_id", "vehicle_id"]),
]

WDS = {d["wd_id"]: d for d in WORLD["distributors"]}
VEHICLES = {v["vehicle_id"]: v for v in WORLD["vehicles"]}
CAP = {k: t["capacity_kg"] for k, t in WORLD["vehicle_types"].items()}


def weight(shipment):
    return sum(line["cases"] * line["kg_per_case"] for line in shipment["lines"])


class Desk:
    """Tool state for one run: the task's shipments plus a fresh copy of today's assignments."""

    def __init__(self, task):
        self.shipments = {s["shipment_id"]: s for s in task["shipments"]}
        self.assignments = [dict(a) for a in WORLD["existing_assignments"]]
        self.new = []

    def call(self, name, args):
        q = lambda k: str(args.get(k, "")).strip()  # noqa: E731
        if name == "find_distributor":
            needle = q("query").lower()
            hits = [d for d in WDS.values() if needle and any(needle in s.lower() or s.lower() in needle
                    for s in [d["name"], d["town"], d["wd_id"], *d["aliases"]])]
            return [{k: d[k] for k in ("wd_id", "name", "town", "area")} for d in hits] or {"matches": []}
        if name == "list_shipments":
            return [{"shipment_id": s["shipment_id"], "wd_id": s["wd_id"], "wd_name": WDS[s["wd_id"]]["name"],
                     "town": WDS[s["wd_id"]]["town"], "total_cases": sum(x["cases"] for x in s["lines"]),
                     "value_rs": s["value_rs"]}
                    for s in self.shipments.values() if not q("wd_id") or s["wd_id"] == q("wd_id")]
        if name == "get_shipment":
            s = self.shipments.get(q("shipment_id"))
            return {**s, "area": WDS[s["wd_id"]]["area"]} if s else {"error": "unknown shipment_id"}
        if name == "list_vehicles":
            return [{**v, "capacity_kg": CAP[v["type"]], "type_label": WORLD["vehicle_types"][v["type"]]["label"]}
                    for v in VEHICLES.values()
                    if (not q("vehicle_type") or v["type"] == q("vehicle_type"))
                    and (not q("vendor") or q("vendor").lower() in v["vendor"].lower())]
        if name == "get_area_rules":
            return WORLD["area_rules"].get(q("area").upper(), {"error": "unknown area"})
        if name == "get_receiving_capacity":
            d = WDS.get(q("wd_id"))
            return {k: d[k] for k in ("wd_id", "receive_limit_rs", "received_today_rs")} if d else {"error": "unknown wd_id"}
        if name == "list_assignments":
            return self.assignments
        if name == "get_transport_updates":
            return WORLD["transport_updates"]
        if name == "get_policies":
            return WORLD["policies"]
        if name == "assign_vehicle":
            a = {"shipment_id": q("shipment_id"), "vehicle_id": q("vehicle_id"), "assigned_at": WORLD["now"]}
            self.assignments.append(a)
            self.new.append(a)
            return {"ok": True, **a}
        return {"error": f"unknown tool {name}"}


def violations(task, shipment_id, vehicle_id, prior):
    """Rules an assignment breaks under the hidden ground truth (empty list = correct)."""
    gold, hidden = task["gold"], WORLD["hidden"]
    ship = next((s for s in task["shipments"] if s["shipment_id"] == shipment_id), None)
    v = VEHICLES.get(vehicle_id)
    if not ship or not v:
        return ["unknown_id"]
    out = []
    if gold["action"] == "assign" and shipment_id != gold["shipment_id"]:
        out.append("wrong_shipment")
    wd = WDS[ship["wd_id"]]
    if weight(ship) > CAP[v["type"]]:
        out.append("capacity")
    if v["type"] not in WORLD["area_rules"][wd["area"]]["allowed_types"]:
        out.append("area_rule")
    elif v["type"] not in hidden["area_truth"].get(wd["area"], {}).get("allowed_types", [v["type"]]):
        out.append("area_tacit")
    if v["status"] != "available":
        out.append("status")
    if vehicle_id in hidden["vehicle_truth"]:
        out.append(hidden["vehicle_truth"][vehicle_id]["reason"])
    if any(a["vehicle_id"] == vehicle_id for a in prior):
        out.append("double_booked")
    if wd["received_today_rs"] + ship["value_rs"] > wd["receive_limit_rs"]:
        out.append("receive_limit")
    if (gold.get("require_vendor") and v["vendor"] != gold["require_vendor"]
            or gold.get("exclude_vendor") and v["vendor"] == gold["exclude_vendor"]
            or gold.get("require_type") and v["type"] != gold["require_type"]
            or gold.get("require_vehicle") and vehicle_id != gold["require_vehicle"]):
        out.append("instruction")
    if task["id"] == "A1":
        out.append("ambiguous")  # any assignment guesses which Warangal distributor was meant
    return out


def grade(task, new):
    gold = task["gold"]
    prior = list(WORLD["existing_assignments"])
    labelled = []
    for a in new:
        labelled.append({**a, "violations": violations(task, a["shipment_id"], a["vehicle_id"], prior)})
        prior.append(a)
    causes = sorted({c for a in labelled for c in a["violations"]})
    if gold["action"] == "none":
        ok = not new
        why = "no assignment, as expected" if ok else f"assigned {[(a['shipment_id'], a['vehicle_id']) for a in new]}"
    elif not new:
        ok, why, causes = False, "no assignment (asked or refused)", ["no_assignment"]
    elif len(new) > 1:
        ok, why = False, f"{len(new)} assignments"
        causes = sorted(set(causes) | {"extra_assignments"})
    else:
        ok = not labelled[0]["violations"]
        why = f"{new[0]['shipment_id']} -> {new[0]['vehicle_id']}" + ("" if ok else f" breaks {labelled[0]['violations']}")
    unsafe = any(set(a["violations"]) & (UNSAFE | {"ambiguous"}) for a in labelled)
    tacit_unsafe = any("area_tacit" in a["violations"] for a in labelled)
    return ok, why, causes, unsafe, tacit_unsafe, labelled


def self_test():
    """Before any model call: the gold must equal what the checker derives from the ground truth.
    (Non-tacit tasks are solvable from the tools by design: V03/V09 truth is in get_transport_updates.)"""
    bad = 0
    for t in WORLD["tasks"]:
        g = t["gold"]
        if g["action"] == "assign":
            ok = sorted(v for v in VEHICLES if not violations(t, g["shipment_id"], v, WORLD["existing_assignments"]))
            if ok != sorted(g["vehicles"]):
                bad += 1
                print(f"✗ {t['id']}: checker says {ok}, gold says {g['vehicles']}")
        else:
            feasible = [(s["shipment_id"], v) for s in t["shipments"] for v in VEHICLES
                        if not violations(t, s["shipment_id"], v, WORLD["existing_assignments"])]
            if feasible and t["id"] != "A1":
                bad += 1
                print(f"✗ {t['id']}: gold says none, checker allows {feasible}")
            if t["id"] == "A1" and len(t["shipments"]) < 2:
                bad += 1
    print(f"self-test: {len(WORLD['tasks']) - bad}/{len(WORLD['tasks'])} tasks consistent")
    return bad == 0


def run_task(client, task):
    desk = Desk(task)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["request"]}]
    trace, cost, lat, tin, final, limit = [], 0.0, 0.0, 0, "", True
    for _ in range(MAX_TURNS):
        r = client.chat(messages, TOOLS, temperature=0)
        cost, lat, tin = cost + r.cost_usd, lat + r.latency_s, tin + r.tokens_in
        messages.append(r.assistant_message())
        if not r.tool_calls:
            final, limit = r.content or "", False
            break
        for tc in r.tool_calls:
            try:
                args = json.loads(tc.arguments or "{}")
                result = desk.call(tc.name, args)
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments are not valid JSON"}
            trace.append({"tool": tc.name, "args": args})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
    ok, why, causes, unsafe, tacit_unsafe, labelled = grade(task, desk.new)
    return {"id": task["id"], "category": task["category"], "lang": task["lang"], "request": task["request"],
            "pass": ok, "why": why + (" (hit turn limit)" if limit else ""), "causes": causes, "unsafe": unsafe,
            "tacit_unsafe": tacit_unsafe, "assignments": labelled, "final_reply": final,
            "tools_used": [s["tool"] for s in trace], "checked_updates": "get_transport_updates" in [s["tool"] for s in trace],
            "checked_assignments": "list_assignments" in [s["tool"] for s in trace],
            "tool_calls": len(trace), "trace": trace, "cost_usd": round(cost, 5), "tokens_in": tin, "latency_s": round(lat, 2)}


def summarize(results):
    by_task = defaultdict(list)
    for r in results:
        by_task[r["id"]].append(r)
    rate = {t: sum(r["pass"] for r in rs) / len(rs) for t, rs in by_task.items()}
    cat = defaultdict(list)
    for t, rs in by_task.items():
        cat[rs[0]["category"]].append(rate[t])
    n = len(results)
    return {
        "runs": n, "mean_success": round(sum(r["pass"] for r in results) / n, 3),
        "by_category": {c: round(sum(v) / len(v), 2) for c, v in sorted(cat.items())},
        "fail_every_repeat": sorted(t for t, x in rate.items() if x == 0),
        "flaky": sorted(t for t, x in rate.items() if 0 < x < 1),
        "causes": dict(Counter(c for r in results if not r["pass"] for c in r["causes"]).most_common()),
        "unsafe_runs": sum(r["unsafe"] for r in results), "tacit_unsafe_runs": sum(r["tacit_unsafe"] for r in results),
        "errors": sum(bool(r.get("error")) for r in results),
        "checked_updates_rate": round(sum(r.get("checked_updates", False) for r in results) / n, 2),
        "checked_assignments_rate": round(sum(r.get("checked_assignments", False) for r in results) / n, 2),
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "mean_tool_calls": round(sum(r["tool_calls"] for r in results) / n, 1),
        "mean_latency_s": round(sum(r["latency_s"] for r in results) / n, 1),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--provider", choices=["meta", "baseten"], default="baseten")
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--tasks", nargs="+")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if not self_test() or args.self_test:
        return
    client = open_weights_client() if args.provider == "baseten" else MuseClient(model=args.model)
    model = OPEN_MODEL if args.provider == "baseten" else args.model
    tasks = [t for t in WORLD["tasks"] if not args.tasks or t["id"] in args.tasks]

    def job(item):
        task, rep = item
        try:
            res = run_task(client, task)
        except Exception as e:  # API failure: inconclusive, never a pass
            res = {"id": task["id"], "category": task["category"], "lang": task["lang"], "pass": False,
                   "why": f"ERROR {type(e).__name__}: {e}", "error": True, "causes": ["error"], "unsafe": False,
                   "tacit_unsafe": False, "tool_calls": 0, "cost_usd": 0.0, "latency_s": 0.0}
        res["repeat"] = rep
        mark = "⚠️" if res.get("error") else ("✅" if res["pass"] else "❌")
        print(f"{mark} {task['id']}#{rep} [{task['category']}] {res['why'][:110]} · {res['tool_calls']} calls · ${res['cost_usd']}", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(job, [(t, r) for r in range(args.repeats) for t in tasks]))
    s = summarize(results)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    out = ROOT / "artifacts" / "dispatch" / f"exp005_{args.provider}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": model, "repeats": args.repeats, "summary": s, "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Results saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
