"""EXP-006: does the agent improve by itself from its own history, and does a second customer of the same
type start better with what the first one learned (a domain pack)?

Customer A = SVR Logistics (datasets/dispatch/exp005_world.json + 60 days of trip history, generated here).
Customer B = Ramappa Carriers (datasets/dispatch/exp006_world_B.json): same region and distributors, own fleet.
The unwritten knowledge exists in A's history only as patterns (planner messages, trip outcomes); nobody states it.

Pipeline (no human teaching):
  mine   Muse Spark 1.3 reads A's trip history and proposes knowledge items (aliases, area access limits)
  gate   deterministic checks against the history (frozen below): aliases need >= 2 supporting messages and
         0 contradictions; an access limit needs 0 delivered counter-examples AND >= 1 failed trip that it
         explains (absence alone is a habit, not a rule)
  pack   items that mention only entities that also exist in B's world (distributors, areas) go to B;
         A's vehicle and vendor nicknames stay private to A
Arms (agent = Muse Spark Open on Baseten, temperature 0): A-cold, A-self (A + its own gated items),
B-cold, B-pack (B + A's pack). Leak check: no A-private item, vehicle or vendor may appear in B's prompt or output.

Usage:
  uv run python scripts/eval/exp006_transfer.py --gen-history     # writes datasets/dispatch/exp006_history_A.csv
  uv run python scripts/eval/exp006_transfer.py --self-test
  uv run python scripts/eval/exp006_transfer.py --repeats 2 --workers 3
"""

import argparse
import csv
import io
import json
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from order_agent.llm import OPEN_MODEL, MuseClient, open_weights_client  # noqa: E402

DATA = ROOT / "datasets" / "dispatch"
HISTORY = DATA / "exp006_history_A.csv"
MAX_TURNS = 12
MINER_MODEL = "muse-spark-1.3"
UNSAFE = {"capacity", "area_rule", "status", "stale_status", "driver_absent", "double_booked", "receive_limit",
          "instruction", "wrong_shipment", "unknown_id", "ambiguous"}


class World:
    def __init__(self, path):
        self.w = json.loads(path.read_text(encoding="utf-8"))
        self.name = self.w.get("company", "SVR Logistics")
        self.wds = {d["wd_id"]: d for d in self.w["distributors"]}
        self.vehicles = {v["vehicle_id"]: v for v in self.w["vehicles"]}
        self.cap = {k: t["capacity_kg"] for k, t in self.w["vehicle_types"].items()}

    def system(self, knowledge: list[str]):
        s = (f"You are the dispatch-planning assistant at an FMCG depot near Warangal. Today is {self.w['now']}. "
             "Requests come from the planner in English, Telugu script, Roman Telugu or a mix. Use the tools to look up "
             "distributors, shipments, vehicles, area rules, assignments and transporter updates; never invent them. "
             "Follow the dispatch policies (get_policies). When the request is clear and a vehicle satisfies every rule, "
             "assign it with assign_vehicle, then reply with a short summary. Otherwise do not assign: explain why or ask "
             "the planner a clarifying question.")  # identical to EXP-005 when there is no knowledge
        if knowledge:
            s += ("\n\nVerified knowledge learned from past operations (each item passed checks against the trip "
                  "history; it adds to what the tools say):\n" + "\n".join(f"- {k}" for k in knowledge))
        return s


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
        {"vehicle_type": {"type": "string", "enum": ["LCV", "9MT", "32FT", "36FT"]}, "vendor": {"type": "string"}}),
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


def weight(s):
    return sum(x["cases"] * x["kg_per_case"] for x in s["lines"])


class Desk:
    def __init__(self, world, task):
        self.W, self.shipments = world, {s["shipment_id"]: s for s in task["shipments"]}
        self.assignments = [dict(a) for a in world.w["existing_assignments"] + task.get("extra_assignments", [])]
        self.new = []

    def call(self, name, args):
        W, q = self.W, (lambda k: str(args.get(k, "")).strip())
        if name == "find_distributor":
            needle = q("query").lower()
            hits = [d for d in W.wds.values() if needle and any(needle in s.lower() or s.lower() in needle
                    for s in [d["name"], d["town"], d["wd_id"], *d["aliases"]])]
            return [{k: d[k] for k in ("wd_id", "name", "town", "area")} for d in hits] or {"matches": []}
        if name == "list_shipments":
            return [{"shipment_id": s["shipment_id"], "wd_id": s["wd_id"], "wd_name": W.wds[s["wd_id"]]["name"],
                     "town": W.wds[s["wd_id"]]["town"], "total_cases": sum(x["cases"] for x in s["lines"]),
                     "value_rs": s["value_rs"]} for s in self.shipments.values() if not q("wd_id") or s["wd_id"] == q("wd_id")]
        if name == "get_shipment":
            s = self.shipments.get(q("shipment_id"))
            return {**s, "area": W.wds[s["wd_id"]]["area"]} if s else {"error": "unknown shipment_id"}
        if name == "list_vehicles":
            return [{**v, "capacity_kg": W.cap[v["type"]], "type_label": W.w["vehicle_types"][v["type"]]["label"]}
                    for v in W.vehicles.values() if (not q("vehicle_type") or v["type"] == q("vehicle_type"))
                    and (not q("vendor") or q("vendor").lower() in v["vendor"].lower())]
        if name == "get_area_rules":
            return W.w["area_rules"].get(q("area").upper(), {"error": "unknown area"})
        if name == "get_receiving_capacity":
            d = W.wds.get(q("wd_id"))
            return {k: d[k] for k in ("wd_id", "receive_limit_rs", "received_today_rs")} if d else {"error": "unknown wd_id"}
        if name == "list_assignments":
            return self.assignments
        if name == "get_transport_updates":
            return W.w["transport_updates"]
        if name == "get_policies":
            return W.w["policies"]
        if name == "assign_vehicle":
            a = {"shipment_id": q("shipment_id"), "vehicle_id": q("vehicle_id"), "assigned_at": W.w["now"]}
            self.assignments.append(a)
            self.new.append(a)
            return {"ok": True, **a}
        return {"error": f"unknown tool {name}"}


def violations(W, task, shipment_id, vehicle_id, prior):
    gold, hidden = task["gold"], W.w["hidden"]
    ship = next((s for s in task["shipments"] if s["shipment_id"] == shipment_id), None)
    v = W.vehicles.get(vehicle_id)
    if not ship or not v:
        return ["unknown_id"]
    out = []
    if gold["action"] == "assign" and shipment_id != gold["shipment_id"]:
        out.append("wrong_shipment")
    wd = W.wds[ship["wd_id"]]
    if weight(ship) > W.cap[v["type"]]:
        out.append("capacity")
    if v["type"] not in W.w["area_rules"][wd["area"]]["allowed_types"]:
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
        out.append("ambiguous")
    return out


def grade(W, task, new):
    gold = task["gold"]
    prior = list(W.w["existing_assignments"]) + task.get("extra_assignments", [])
    labelled = []
    for a in new:
        labelled.append({**a, "violations": violations(W, task, a["shipment_id"], a["vehicle_id"], prior)})
        prior.append(a)
    causes = sorted({c for a in labelled for c in a["violations"]})
    if gold["action"] == "none":
        ok, why = not new, ("no assignment, as expected" if not new else f"assigned {[(a['shipment_id'], a['vehicle_id']) for a in new]}")
    elif not new:
        ok, why, causes = False, "no assignment (asked or refused)", ["no_assignment"]
    elif len(new) > 1:
        ok, why, causes = False, f"{len(new)} assignments", sorted(set(causes) | {"extra_assignments"})
    else:
        ok = not labelled[0]["violations"]
        why = f"{new[0]['shipment_id']} -> {new[0]['vehicle_id']}" + ("" if ok else f" breaks {labelled[0]['violations']}")
    unsafe = any(set(a["violations"]) & UNSAFE for a in labelled)
    tacit_unsafe = any("area_tacit" in a["violations"] for a in labelled)
    return ok, why, causes, unsafe, tacit_unsafe, labelled


# ---------- customer A's trip history (generated once, then frozen in the repo)
def gen_history():
    W = World(DATA / "exp005_world.json")
    rng = random.Random(6)
    area_truth = {**{a: r["allowed_types"] for a, r in W.w["area_rules"].items()},
                  **{a: r["allowed_types"] for a, r in W.w["hidden"]["area_truth"].items()}}
    weights = {"WD-HNK": (2000, 19000), "WD-WGL": (3000, 14500), "WD-WG2": (3000, 14500), "WD-KZP": (300, 740),
               "WD-KMM": (15500, 19500), "WD-JGN": (2500, 8900)}
    order = ["LCV", "9MT", "32FT", "36FT"]
    rows, start = [], date(2026, 8, 28)

    def pick(wd_id, kg):
        area = W.wds[wd_id]["area"]
        for t in order:  # smallest allowed type that fits
            if t in area_truth[area] and W.cap[t] >= kg:
                return rng.choice([v for v in W.vehicles.values() if v["type"] == t])
        raise ValueError((wd_id, kg))

    def message(wd, v):
        if v["vehicle_id"] == "V08" and rng.random() < 0.6:
            ref = "nalla lorry"
        elif v["vendor"] == "SVR Transport" and rng.random() < 0.35:
            ref = "Anna vallu bandi"
        else:
            ref = rng.choice([v["vehicle_id"], v["reg_no"]])
        if wd["wd_id"] == "WD-WGL" and rng.random() < 0.45:
            return f"Pedda godown load ki {ref} pettu"
        if wd["wd_id"] == "WD-HNK" and rng.random() < 0.4:
            return f"Chowrasta load ki {ref} pettu"
        return rng.choice([f"{wd['town']} load ki {ref} pettu", f"{wd['name']} ki {ref} assign cheyyi",
                           f"Assign {ref} for {wd['name']}, {wd['town']}", f"{wd['town']} shipment {ref} lo pampu"])

    noise_days = {7, 23, 41}
    for d in range(60):
        day = start + timedelta(days=d)
        for _ in range(2):
            wd_id = rng.choices(list(weights), [22, 22, 12, 12, 16, 16])[0]
            wd = W.wds[wd_id]
            kg = rng.randrange(*weights[wd_id], 50)
            v = pick(wd_id, kg)
            outcome, note = "delivered", ""
            if d in noise_days and wd_id in ("WD-HNK", "WD-WGL"):
                outcome, note = "failed", "Distributor godown full, unloaded next morning."
                noise_days.discard(d)
            rows.append([day.isoformat(), message(wd, v), wd_id, wd["town"], wd["area"], kg, v["vehicle_id"],
                         v["type"], v["vendor"], outcome, note])
        if day == date(2026, 9, 12):  # the one event that reveals the Jangaon lane
            jg = W.wds["WD-JGN"]
            rows.append([day.isoformat(), f"{jg['town']} load ki V10 pettu", "WD-JGN", jg["town"], "JGN", 12000, "V10",
                         "32FT", "Kakatiya Logistics", "failed",
                         "Driver: Jangaon godown lane lo 32 adugula lorry tiragaledu, load venakki vachindi."])
        if day == date(2026, 9, 13):
            for vid, kg in (("V05", 6000), ("V09", 6000)):
                v = W.vehicles[vid]
                rows.append([day.isoformat(), f"Jangaon load rendu bandlalo pampu, {vid} pettu", "WD-JGN", "Jangaon",
                             "JGN", kg, vid, v["type"], v["vendor"], "delivered", "Re-sent load from 2026-09-12, split."])
    with HISTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["trip_id", "date", "planner_message", "wd_id", "town", "area", "weight_kg", "vehicle_id",
                    "vehicle_type", "vendor", "outcome", "outcome_note"])
        for i, r in enumerate(rows, 1):
            w.writerow([f"T{i:03d}", *r])
    print(f"wrote {len(rows)} trips to {HISTORY.relative_to(ROOT)}")


def load_history():
    return list(csv.DictReader(HISTORY.open(encoding="utf-8")))


# ---------- mining (Muse) and the deterministic gate
MINE_PROMPT = """You are reviewing a transport company's trip history to find unwritten knowledge its planners rely on:
nicknames planners use for distributors, vehicles or vendors, and access limits for delivery areas.
Only propose an access limit if the history shows it is a real constraint, not just a habit.
For each item, say whether it is "regional" (true for anyone operating in this area) or "company" (specific to this company).

Distributors: {wds}
Vehicles: {vehicles}
Written area rules: {rules}

Trip history (CSV):
{history}

Reply with JSON only:
{{"items": [
  {{"kind": "distributor_alias", "phrase": "...", "wd_id": "...", "scope": "regional|company", "evidence_trip_ids": ["T001"]}},
  {{"kind": "vehicle_alias", "phrase": "...", "vehicle_id": "...", "scope": "...", "evidence_trip_ids": []}},
  {{"kind": "vendor_alias", "phrase": "...", "vendor": "...", "scope": "...", "evidence_trip_ids": []}},
  {{"kind": "area_access_limit", "area": "...", "allowed_types": ["LCV", "9MT"], "reason": "...", "scope": "...", "evidence_trip_ids": []}}
]}}"""


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else {}


def mine(client, W, history):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(history[0]))
    w.writeheader()
    w.writerows(history)
    prompt = MINE_PROMPT.format(
        wds=json.dumps([{k: d[k] for k in ("wd_id", "name", "town", "area")} for d in W.wds.values()]),
        vehicles=json.dumps([{k: v[k] for k in ("vehicle_id", "reg_no", "vendor", "type")} for v in W.vehicles.values()]),
        rules=json.dumps(W.w["area_rules"]), history=buf.getvalue())
    r = client.chat([{"role": "user", "content": prompt}], None, temperature=0)
    return parse_json(r.content).get("items", []), r.cost_usd, r.latency_s


def gate(items, history, W):
    """Frozen checks against A's history. Returns (kept, rejected-with-reason)."""
    kept, rejected = [], []
    for it in items:
        kind = it.get("kind")
        if kind in ("distributor_alias", "vehicle_alias", "vendor_alias"):
            field, col = {"distributor_alias": ("wd_id", "wd_id"), "vehicle_alias": ("vehicle_id", "vehicle_id"),
                          "vendor_alias": ("vendor", "vendor")}[kind]
            phrase = str(it.get("phrase", "")).strip().lower()
            hits = [h for h in history if phrase and phrase in h["planner_message"].lower()]
            good = sum(h[col] == it.get(field) for h in hits)
            if len(phrase) < 3 or good < 2 or good != len(hits):
                rejected.append({**it, "why": f"{good} supporting / {len(hits)} messages"})
            else:
                kept.append({**it, "support": good})
        elif kind == "area_access_limit":
            area, allowed = it.get("area"), set(it.get("allowed_types") or [])
            trips = [h for h in history if h["area"] == area]
            counter = [h for h in trips if h["outcome"] == "delivered" and h["vehicle_type"] not in allowed]
            explained = [h for h in trips if h["outcome"] == "failed" and h["vehicle_type"] not in allowed]
            if not allowed or not allowed <= set(W.cap) or counter or not explained:
                rejected.append({**it, "why": f"{len(counter)} delivered counter-examples, {len(explained)} failures explained"})
            else:
                kept.append({**it, "support": len(trips)})
        else:
            rejected.append({**it, "why": "unknown kind"})
    return kept, rejected


def render(it, W):
    k = it["kind"]
    if k == "distributor_alias":
        d = W.wds.get(it["wd_id"], {})
        return f'"{it["phrase"]}" means distributor {it["wd_id"]} ({d.get("name", "?")}, {d.get("town", "?")}).'
    if k == "vehicle_alias":
        return f'"{it["phrase"]}" means vehicle {it["vehicle_id"]}.'
    if k == "vendor_alias":
        return f'"{it["phrase"]}" means vendor {it["vendor"]}.'
    return (f'Area {it["area"]}: only {", ".join(sorted(it["allowed_types"]))} vehicles can deliver there '
            f'({it.get("reason", "learned from trip outcomes")}).')


def pack_for(kept, B):
    """Only items whose entities exist in B's world travel; everything else stays private to A."""
    keep, private = [], []
    for it in kept:
        ok = (it["kind"] == "distributor_alias" and it.get("wd_id") in B.wds
              or it["kind"] == "area_access_limit" and it.get("area") in B.w["area_rules"]
              or it["kind"] == "vehicle_alias" and it.get("vehicle_id") in B.vehicles
              or it["kind"] == "vendor_alias" and it.get("vendor") in {v["vendor"] for v in B.vehicles.values()})
        (keep if ok else private).append(it)
    return keep, private


def leak_tokens(A, B, private_items):
    toks = {str(it.get("phrase", "")).lower() for it in private_items if it.get("phrase")}
    toks |= {v["reg_no"].lower() for v in A.vehicles.values()} | {v["vehicle_id"].lower() for v in A.vehicles.values()}
    toks |= {v["vendor"].lower() for v in A.vehicles.values()} - {v["vendor"].lower() for v in B.vehicles.values()}
    return sorted(t for t in toks if len(t) >= 3)


def leaks(text, toks):
    low = text.lower()
    return [t for t in toks if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low)]


# ---------- agent runs
def run_task(client, W, task, knowledge):
    desk = Desk(W, task)
    system = W.system(knowledge)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task["request"]}]
    trace, cost, lat, final, limit = [], 0.0, 0.0, "", True
    for _ in range(MAX_TURNS):
        r = client.chat(messages, TOOLS, temperature=0)
        cost, lat = cost + r.cost_usd, lat + r.latency_s
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
    ok, why, causes, unsafe, tacit_unsafe, labelled = grade(W, task, desk.new)
    return {"id": task["id"], "category": task["category"], "lang": task["lang"], "pass": ok,
            "why": why + (" (hit turn limit)" if limit else ""), "causes": causes, "unsafe": unsafe,
            "tacit_unsafe": tacit_unsafe, "assignments": labelled, "final_reply": final, "system_prompt": system,
            "tool_calls": len(trace), "trace": trace, "cost_usd": round(cost, 5), "latency_s": round(lat, 2)}


def summarize(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r["pass"])
    n = len(rows)
    return {"runs": n, "mean": round(sum(r["pass"] for r in rows) / n, 3),
            "by_category": {c: round(sum(v) / len(v), 2) for c, v in sorted(by.items())},
            "failing": sorted({r["id"] for r in rows if not r["pass"]}),
            "causes": dict(Counter(c for r in rows if not r["pass"] for c in r["causes"]).most_common()),
            "unsafe_runs": sum(r["unsafe"] for r in rows), "tacit_unsafe_runs": sum(r["tacit_unsafe"] for r in rows),
            "errors": sum(bool(r.get("error")) for r in rows), "leak_runs": sum(bool(r.get("leaks")) for r in rows),
            "cost_usd": round(sum(r["cost_usd"] for r in rows), 4)}


def self_test(A, B, history):
    bad = 0
    for W in (A, B):
        for t in W.w["tasks"]:
            g, prior = t["gold"], W.w["existing_assignments"] + t.get("extra_assignments", [])
            if g["action"] == "assign":
                ok = sorted(v for v in W.vehicles if not violations(W, t, g["shipment_id"], v, prior))
                if ok != sorted(g["vehicles"]):
                    bad += 1
                    print(f"✗ {W.name} {t['id']}: checker {ok} vs gold {g['vehicles']}")
            elif t["id"] != "A1" and any(not violations(W, t, s["shipment_id"], v, prior)
                                         for s in t["shipments"] for v in W.vehicles):
                bad += 1
                print(f"✗ {W.name} {t['id']}: gold none but checker allows an assignment")
    truth = [{"kind": "distributor_alias", "phrase": "Pedda godown", "wd_id": "WD-WGL"},
             {"kind": "distributor_alias", "phrase": "Chowrasta load", "wd_id": "WD-HNK"},
             {"kind": "vehicle_alias", "phrase": "nalla lorry", "vehicle_id": "V08"},
             {"kind": "vendor_alias", "phrase": "Anna vallu", "vendor": "SVR Transport"},
             {"kind": "area_access_limit", "area": "JGN", "allowed_types": ["LCV", "9MT"]}]
    traps = [{"kind": "area_access_limit", "area": "KMM", "allowed_types": ["36FT"]},
             {"kind": "distributor_alias", "phrase": "Pedda godown", "wd_id": "WD-HNK"}]
    kept, rej = gate(truth + traps, history, A)
    if len(kept) != len(truth) or len(rej) != len(traps):
        bad += 1
        print(f"✗ gate: kept {[k.get('phrase') or k.get('area') for k in kept]}, rejected {[r.get('why') for r in rej]}")
    to_b, private = pack_for(kept, B)
    if sorted(i.get("phrase") or i["area"] for i in to_b) != ["Chowrasta load", "JGN", "Pedda godown"]:
        bad += 1
        print(f"✗ pack: {to_b}")
    print(f"self-test: {'OK' if not bad else f'{bad} problem(s)'} · history {len(history)} trips · "
          f"gold/checker on {len(A.w['tasks'])}+{len(B.w['tasks'])} tasks · gate and pack on the true items + 2 traps")
    return bad == 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-history", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if args.gen_history:
        return gen_history()
    A, B, history = World(DATA / "exp005_world.json"), World(DATA / "exp006_world_B.json"), load_history()
    if not self_test(A, B, history) or args.self_test:
        return
    miner, agent = MuseClient(model=MINER_MODEL), open_weights_client()

    mining = []
    for rep in range(args.repeats):
        items, cost, lat = mine(miner, A, history)
        kept, rejected = gate(items, history, A)
        to_b, private = pack_for(kept, B)
        mining.append({"repeat": rep, "proposed": items, "kept": kept, "rejected": rejected, "pack_for_B": to_b,
                       "private_to_A": private, "cost_usd": round(cost, 5), "latency_s": round(lat, 2)})
        print(f"mining #{rep}: proposed {len(items)}, kept {len(kept)}, to B {len(to_b)}, private {len(private)}, ${cost:.4f}")
        for it in items:
            tag = "KEEP" if it in [{k: v for k, v in x.items() if k != "support"} for x in kept] else "drop"
            print(f"   {tag} {json.dumps({k: it.get(k) for k in ('kind', 'phrase', 'wd_id', 'vehicle_id', 'vendor', 'area', 'allowed_types', 'scope') if it.get(k)}, ensure_ascii=False)}")

    jobs = []
    for rep, m in enumerate(mining):
        a_know = [render(i, A) for i in m["kept"]]
        b_know = [render(i, B) for i in m["pack_for_B"]]
        toks = leak_tokens(A, B, m["private_to_A"])
        for arm, W, know in (("A-cold", A, []), ("A-self", A, a_know), ("B-cold", B, []), ("B-pack", B, b_know)):
            for t in W.w["tasks"]:
                jobs.append((arm, W, t, know, rep, toks if arm.startswith("B") else []))

    def job(j):
        arm, W, t, know, rep, toks = j
        try:
            r = run_task(agent, W, t, know)
            r["leaks"] = leaks(r["system_prompt"] + " " + r["final_reply"] + " " + json.dumps(r["trace"]), toks) if toks else []
        except Exception as e:
            r = {"id": t["id"], "category": t["category"], "pass": False, "why": f"ERROR {type(e).__name__}: {e}",
                 "error": True, "causes": ["error"], "unsafe": False, "tacit_unsafe": False, "cost_usd": 0.0, "leaks": []}
        r.update(arm=arm, repeat=rep)
        mark = "⚠️" if r.get("error") else ("✅" if r["pass"] else "❌")
        print(f"{mark} {arm:6} {t['id']:4}#{rep} [{t['category']}] {r['why'][:90]}{' LEAK ' + str(r['leaks']) if r.get('leaks') else ''}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(job, jobs))
    summary = {arm: summarize([r for r in results if r["arm"] == arm]) for arm in ("A-cold", "A-self", "B-cold", "B-pack")}
    summary["mining_cost_usd"] = round(sum(m["cost_usd"] for m in mining), 4)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    out = ROOT / "artifacts" / "dispatch" / f"exp006_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"agent_model": OPEN_MODEL, "miner_model": MINER_MODEL, "repeats": args.repeats,
                               "summary": summary, "mining": mining, "results": results}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"Results saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
