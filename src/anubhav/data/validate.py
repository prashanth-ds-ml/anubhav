"""Step 11: integrity checks on the canonical world, leak checks on agent-visible data, and the evidence
report (does every hidden rule leave the traces it is supposed to?). Generation fails on any critical issue."""

import re
from collections import Counter, defaultdict
from datetime import datetime

from .store import HIDDEN_COLUMNS, company_view

LEAK_PATTERNS = [re.compile(r"\bH-\d{2}[ab]?\b"), re.compile(r"hidden", re.I), re.compile(r"true_cause|rule_id|oracle", re.I)]


def integrity(W, t):
    """Return a list of critical violations (empty = clean)."""
    bad = []
    def dup(table, *key):
        c = Counter(tuple(r[k] for k in key) for r in t[table])
        bad.extend(f"{table}: duplicate {key}={k}" for k, n in c.items() if n > 1)
    for table, key in (("orders", ("company", "order_id")), ("shipments", ("company", "shipment_id")),
                       ("invoices", ("company", "invoice_no")), ("lorry_receipts", ("company", "lr_no")),
                       ("staff_edits", ("company", "edit_id"))):
        dup(table, *key)
    dup_sites = Counter((s["company"], s["site_id"]) for s in W.sites)
    bad += [f"sites: duplicate {k}" for k, n in dup_sites.items() if n > 1]
    orders = {(o["company"], o["order_id"]): o for o in t["orders"]}
    ships = {(s["company"], s["shipment_id"]): s for s in t["shipments"]}
    sites = {(s["company"], s["site_id"]) for s in W.sites}
    vehicles = {(v["company"], v["vehicle_id"]): v for v in W.vehicles}
    for o in t["orders"]:
        if (o["company"], o["site_id"]) not in sites:
            bad.append(f"orders: {o['order_id']} unknown site {o['site_id']}")
        if o["created_at"][:10] > o["delivery_date"]:
            bad.append(f"orders: {o['order_id']} created after its delivery date")
    for i in t["order_items"]:
        if (i["company"], i["order_id"]) not in orders:
            bad.append(f"order_items: orphan {i['order_id']}")
        if min(i[k] for k in ("ordered_cases", "allocated_cases", "delivered_cases", "returned_cases", "cancelled_cases")) < 0:
            bad.append(f"order_items: negative quantity in {i['order_id']}")
        if i["allocated_cases"] > i["ordered_cases"] - i["cancelled_cases"]:
            bad.append(f"order_items: {i['order_id']} {i['sku']} allocated {i['allocated_cases']} > ordered-cancelled")
        if i["delivered_cases"] + i["returned_cases"] > i["allocated_cases"]:
            bad.append(f"order_items: {i['order_id']} {i['sku']} delivered+returned > allocated")
    alloc = defaultdict(int)
    for si in t["shipment_items"]:
        if (si["company"], si["shipment_id"]) not in ships:
            bad.append(f"shipment_items: orphan {si['shipment_id']}")
        alloc[(si["company"], si["order_id"], si["sku"])] += si["cases"]
    for i in t["order_items"]:
        if alloc[(i["company"], i["order_id"], i["sku"])] != i["allocated_cases"]:
            bad.append(f"allocation mismatch {i['order_id']} {i['sku']}: shipments {alloc[(i['company'], i['order_id'], i['sku'])]} vs {i['allocated_cases']}")
    for s in t["shipments"]:
        v = vehicles.get((s["company"], s["vehicle_id"]))
        if not v:
            bad.append(f"shipments: {s['shipment_id']} unknown vehicle")
            continue
        if s["weight_kg"] > v["payload_kg"] + 1 or s["volume_m3"] > v["volume_m3"] + 0.01:
            bad.append(f"shipments: {s['shipment_id']} planned {s['weight_kg']} kg / {s['volume_m3']} m3 on {v['class']}")
        kinds = {next(p["handling_class"] for p in W.products if p["sku"] == si["sku"])
                 for si in t["shipment_items"] if si["shipment_id"] == s["shipment_id"] and si["company"] == s["company"]}
        if "chemical" in kinds and kinds & {"dense_food", "light_food", "liquid", "chilled"}:
            bad.append(f"shipments: {s['shipment_id']} mixes food and chemicals")
    # chronology and vehicle overlap
    by_ship = defaultdict(list)
    for e in t["trip_events"]:
        by_ship[(e["company"], e["shipment_id"])].append(e)
    spans = defaultdict(list)
    for k, evs in by_ship.items():
        ts = [e["ts"] for e in evs]
        if ts != sorted(ts):
            bad.append(f"trip_events: {k[1]} events out of order")
        s = ships.get(k)
        if s:
            spans[(k[0], s["vehicle_id"])].append((ts[0], ts[-1], k[1]))
    for (cid, vid), sp in spans.items():
        sp.sort()
        for (a0, a1, sa), (b0, b1, sb) in zip(sp, sp[1:]):
            if b0 < a1 or b0 == a0:
                bad.append(f"vehicle {vid} in two trips at once: {sa} until {a1} and {sb} from {b0}")
    for n in t["driver_notes"]:
        first = by_ship[(n["company"], n["shipment_id"])][0]["ts"]
        if n["ts"] < first:
            bad.append(f"driver_notes: note before its trip started ({n['shipment_id']})")
    for inv in t["invoices"]:
        if inv["value_rs"] > 50000 and not any(e["invoice_no"] == inv["invoice_no"] and e["company"] == inv["company"]
                                               for e in t["eway_bills"]):
            bad.append(f"invoices: {inv['invoice_no']} over Rs 50,000 without an e-way bill")
    return bad


def leaks(W, t):
    """Hidden truth must never appear in what a company (and so the agent) can see."""
    bad = []
    for cid in W.companies:
        view = company_view(W, t, cid)
        for name, rows in view.items():
            for r in rows:
                for k, v in r.items():
                    if k in HIDDEN_COLUMNS or k.startswith("_"):
                        bad.append(f"{cid}.{name}: hidden column {k}")
                    if isinstance(v, str) and any(p.search(v) for p in LEAK_PATTERNS):
                        bad.append(f"{cid}.{name}.{k}: leak-like text {v[:60]!r}")
    return bad


def evidence(W, t, companies, start, end):
    """For each hidden rule, count the traces it left in this run."""
    rep = {}
    for r in W.rules:
        rid = r["id"]
        ev = {"failures": sum(1 for o in t["trip_outcomes"] if o.get("rule_id") == rid and o["status"] == "returned"),
              "waits": sum(1 for e in t["trip_events"] if e.get("rule_id") == rid and e["kind"] in ("waiting", "delay")),
              "offloads": sum(1 for e in t["trip_events"] if e.get("rule_id") == rid and e["kind"] == "weighbridge_offload"),
              "no_shows": sum(1 for p in t["vehicle_placements"] if p.get("rule_id") == rid),
              "notes": sum(1 for n in t["driver_notes"] if n.get("_rule_id") == rid),
              "mentions": 0}
        if r["kind"] == "alias":
            ev["mentions"] = sum(r["phrase"].lower() in m["text"].lower() for m in t["planner_messages"]
                                 if m["company"] in r["companies"])
        if r["kind"] == "habit":
            ships = [s for s in t["shipments"] if s["company"] == r["company"] and any(
                W.site(s["company"], x["site_id"])["town"] == r["town"] for x in t["shipment_stops"]
                if x["shipment_id"] == s["shipment_id"] and x["company"] == s["company"])]
            ev["habit_trips"] = sum(s["vehicle_class"] == r["vehicle_class"] for s in ships)
            ev["town_trips"] = len(ships)
        if r["kind"] in ("look_alike", "contradiction"):
            ev["successes_long"] = sum(1 for o in t["trip_outcomes"] if o["status"] != "returned" and
                                       W.site(o["company"], o["site_id"])["site_key"] == r["site"] and
                                       next(s for s in t["shipments"] if s["shipment_id"] == o["shipment_id"]
                                            and s["company"] == o["company"])["vehicle_class"] in ("T32S", "T32M"))
        ev["total"] = sum(v for k, v in ev.items() if k in ("failures", "waits", "offloads", "no_shows", "mentions"))
        exp = [e for e in r.get("exposures", []) if e["company"] in companies and start <= str(e["date"]) <= end]
        ev["planned_exposures_in_window"] = len(exp)
        ev["strength"] = r["strength"]
        rep[rid] = ev
    return rep


def evidence_problems(rep, W):
    """Rules with planned exposures in the window must show evidence; aliases must be used."""
    bad = []
    for rid, ev in rep.items():
        kind = W.rule(rid)["kind"]
        if ev["planned_exposures_in_window"] and kind not in ("look_alike", "contradiction") and ev["total"] == 0:
            bad.append(f"{rid}: {ev['planned_exposures_in_window']} planned exposures but no evidence")
        if kind in ("look_alike", "contradiction") and ev["planned_exposures_in_window"] > 1 and ev.get("successes_long", 0) == 0:
            bad.append(f"{rid}: look-alike site never got a long truck successfully")
    return bad


def stats(t):
    langs = Counter(n["lang"] for n in t["driver_notes"]) + Counter(m["lang"] for m in t["planner_messages"])
    tot = sum(langs.values()) or 1
    return {"languages": {k: round(v / tot, 3) for k, v in langs.items()},
            "voice_share": round(sum(n["source"] == "voice" for n in t["driver_notes"]) / max(1, len(t["driver_notes"])), 3),
            "vague_share": round(sum(bool(n["_vague"]) for n in t["driver_notes"]) / max(1, len(t["driver_notes"])), 3)}
