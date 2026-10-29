"""Steps 2-8: simulate each company day by day. Orders arrive, a simulated planner (with habits and only
partial knowledge) builds shipments and picks trucks, vendors place them (or don't), trips meet the hidden
truth plus everyday noise, and paperwork and people's edits/feedback follow.

Every row a company would see is kept apart from the hidden cause (`true_cause`, `rule_id`), which the
export step drops from agent-visible databases."""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from .config import as_date, rng

HOUR = timedelta(hours=1)
FOODS = {"dense_food", "light_food", "liquid"}


def daterange(a, b):
    d = as_date(a)
    while d <= as_date(b):
        yield d
        d += timedelta(days=1)


def at(d, hour, minute=0):
    return datetime(d.year, d.month, d.day) + timedelta(hours=hour, minutes=minute)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M")


def random_probe(r):
    """A throwaway copy of the planner's random stream, so checking 'does any truck fit?' doesn't use it up."""
    import random
    p = random.Random()
    p.setstate(r.getstate())
    return p


def split_load(ld, prod):
    """Split a load into two halves (by stops if there are several, else by quantity), as a planner would
    ('rendu bandlalo pampu'). Returns None when it can't be split further."""
    if len(ld["stops"]) > 1:
        first, second = ld["stops"][: len(ld["stops"]) // 2], ld["stops"][len(ld["stops"]) // 2:]
        parts = [[x for x in ld["lines"] if x[0]["site_id"] in first], [x for x in ld["lines"] if x[0]["site_id"] in second]]
    else:
        a, b = [], []
        for o, it, q in ld["lines"]:
            h = q // 2
            if h:
                a.append((o, it, h))
            if q - h:
                b.append((o, it, q - h))
        parts = [a, b]
    if not all(parts):
        return None
    out = []
    for lines in parts:
        stops = [s for s in ld["stops"] if any(o["site_id"] == s for o, _, _ in lines)]
        out.append({"stops": stops, "lines": lines, "kg": sum(prod[it["sku"]]["case_kg"] * q for _, it, q in lines),
                    "m3": sum(prod[it["sku"]]["case_m3"] * q for _, it, q in lines)})
    return out


class Sim:
    def __init__(self, W, start, end):
        self.W, self.cfg = W, W.cfg
        self.start, self.end = as_date(start), as_date(end)
        self.t = defaultdict(list)                      # table name -> rows
        self.n = defaultdict(int)                       # id counters
        self.prod = {p["sku"]: p for p in W.products}
        self.vc = self.cfg["vehicle_classes"]
        self.learned = defaultdict(set)                 # (company, planner) -> rule ids learned from failures
        self.fail_count = defaultdict(int)              # (company, rule id) -> failures seen
        self.busy = defaultdict(set)                    # (company, date) -> vehicle ids used
        self.free_at = {}                               # (company, vehicle) -> when its last trip ended
        self.blocked = {}                               # (company, vehicle) -> date its papers are renewed
        self.fired = set()                              # one-time hidden events already played out
        self.bandh = {}
        cal = self.cfg["calendar"]
        r = rng(self.cfg, "disruptions", "bandh")
        days = list(daterange(self.start, self.end))
        self.bandh_days = set(r.sample(days, min(len(days), self.cfg["rates"]["bandh_days_per_90"] * len(days) // 90)))
        self.festival = (as_date(cal["festival"]["start"]), as_date(cal["festival"]["end"]))
        self.closed_days = {as_date(x) for x in cal["festival"].get("closed_days", [])}
        self.monsoon = (as_date(cal["monsoon"]["start"]), as_date(cal["monsoon"]["end"]))

    # ---------- helpers
    def nid(self, kind, company):
        self.n[(kind, company)] += 1
        return f"{company}-{kind}{self.n[(kind, company)]:05d}"

    def add(self, table, **row):
        self.t[table].append(row)
        return row

    def rush(self, d):
        month_end = (d + timedelta(days=self.cfg["calendar"]["month_end_days"])).month != d.month
        return month_end or self.festival[0] <= d <= self.festival[1]

    def in_monsoon(self, d):
        return self.monsoon[0] <= d <= self.monsoon[1]

    def demand_factor(self, d):
        cal = self.cfg["calendar"]
        f = cal["sunday_factor"] if d.weekday() == 6 else 1.0
        if (d + timedelta(days=cal["month_end_days"])).month != d.month:
            f *= cal["month_end_factor"]
        if self.festival[0] <= d <= self.festival[1]:
            f *= cal["festival"]["factor"]
        return 0.0 if d in self.closed_days else f

    def knows(self, company, planner, rid):
        return rid in planner["knows"] or rid in self.learned[(company, planner["name"])]

    def saw_failure(self, company, rid):
        self.fail_count[(company, rid)] += 1
        for p in self.W.companies[company]["planners"]:
            if self.fail_count[(company, rid)] >= p["learns_after"]:
                self.learned[(company, p["name"])].add(rid)

    def corridor_of(self, region, town):
        for i, c in enumerate(self.cfg["corridors"][region]):
            if town in c:
                return i
        return 99

    def travel_min(self, a, b):
        km_ = self.W.town_km(a, b)
        return round(km_ / self.cfg["speed_kmh"]["highway"] * 60 + (20 if a != b else 10)), km_

    # ---------- run
    def run(self):
        for cid, c in self.W.companies.items():
            if c.get("history", True) is False:
                continue
            for d in daterange(self.start, self.end):
                self.day(cid, c, d)
        return self.t

    def day(self, cid, c, d):
        rd, rs = rng(self.cfg, "demand", cid, d), rng(self.cfg, "resources", cid, d)
        rx = rng(self.cfg, "disruptions", cid, d)
        planner = rs.choices(c["planners"], [p.get("share", 1) for p in c["planners"]])[0]
        orders = self.make_orders(cid, c, d, rd)
        orders += [o for o in self.t["_resend"] if o["company"] == cid and o["delivery_date"] == d.isoformat()]
        orders = [o for o in orders if self.order_ok(cid, o, d, rd)]
        for seg, group in self.group(cid, c, orders):
            for load in self.pack(cid, c, d, group, planner, seg):
                self.dispatch(cid, c, d, load, planner, rs, rx)

    # ---------- step 2: demand
    def make_orders(self, cid, c, d, r):
        W, cfg = self.W, self.cfg
        sites = [s for s in W.sites if s["company"] == cid]
        n = max(0, round(r.gauss(c["orders_per_day"] * self.demand_factor(d), 1.5)))
        picks = r.choices(sites, [s["demand_weight"] for s in sites], k=n)
        for rule in W.rules:
            for e in rule.get("exposures", []):
                if e["company"] == cid and as_date(e["date"]) == d:
                    s = W.site_by_key(cid, e.get("site", rule.get("site")))
                    if s:
                        picks.append(s | {"_min_kg": e.get("min_kg", 0), "_rule": rule["id"]})
        out = []
        for s in picks:
            brands = [b for b in c["brands"]]
            items = []
            lo, hi = cfg["site_types"][s["type"]]["cases"]
            heavy = [x for x in brands if W.cfg["brands"][x]["class"] in ("dense_food", "liquid")]
            b = r.choice(heavy) if s.get("_min_kg") and heavy else r.choice(brands)
            skus = [p for p in W.products if p["brand"] == b]
            scale = 0.4 if skus[0]["handling_class"] == "chilled" else 1.0
            for p in r.sample(skus, r.randint(1, len(skus))):
                items.append([p["sku"], max(5, round(r.uniform(lo, hi) * scale / 1.5))])
            while s.get("_min_kg") and sum(self.prod[k]["case_kg"] * q for k, q in items) < s["_min_kg"]:
                dense = [p for p in W.products if p["brand"] == b]
                items.append([r.choice(dense)["sku"], r.randint(80, 200)])
            merged = {}
            for sku, q in items:                       # one line per product, as on a real order
                merged[sku] = merged.get(sku, 0) + q
            items = sorted(merged.items())
            urgent = r.random() < cfg["rates"]["urgent"] and not s.get("_min_kg")
            created = at(d, 9, 0) if urgent else at(d - timedelta(days=1), r.randint(8, 11), r.choice([0, 15, 30, 45]))
            late = (not urgent) and r.random() < cfg["rates"]["late_order"]
            if late:
                created = at(d - timedelta(days=1), r.randint(13, 17), r.choice([0, 20, 40]))
            if s["type"] == "modern_trade":
                win = (6, 9)
            else:
                win = r.choice([(8, 13), (9, 14), (10, 18), (8, 20)])
            oid = self.nid("O", cid)
            o = self.add("orders", company=cid, order_id=oid, site_id=s["site_id"], created_at=iso(created),
                         delivery_date=d.isoformat(), window_start=f"{win[0]:02d}:00", window_end=f"{win[1]:02d}:00",
                         priority="urgent" if urgent else "regular",
                         channel=r.choice(["sales_app", "sales_app", "phone", "whatsapp"]), status="open",
                         late_after_cutoff=late, _exposure=s.get("_rule"))
            for sku, q in items:
                self.add("order_items", company=cid, order_id=oid, sku=sku, ordered_cases=q, cancelled_cases=0,
                         allocated_cases=0, delivered_cases=0, returned_cases=0)
            out.append(o)
            if late:
                self.replan(cid, created, "late_order", oid)
        return out

    def order_ok(self, cid, o, d, r):
        rates = self.cfg["rates"]
        if o.get("_resend") or o.get("_exposure"):     # planned evidence must actually happen
            return True
        if r.random() < rates["cancel"]:
            o["status"] = "cancelled"
            for it in self.items(cid, o["order_id"]):
                it["cancelled_cases"] = it["ordered_cases"]
            self.replan(cid, at(d - timedelta(days=1), 14), "order_cancelled", o["order_id"])
            return False
        if r.random() < rates["credit_hold"]:
            o["status"] = "credit_hold"
            self.add("events_office", company=cid, ts=iso(at(d - timedelta(days=1), 12, 30)), kind="credit_hold",
                     order_id=o["order_id"], detail="distributor over credit limit")
            return False
        if r.random() < rates["qty_change"]:
            it = r.choice(self.items(cid, o["order_id"]))
            it["ordered_cases"] = max(5, round(it["ordered_cases"] * r.choice([0.6, 0.8, 1.25, 1.5])))
            self.replan(cid, at(d - timedelta(days=1), 13, 30), "qty_changed", o["order_id"])
        return True

    def items(self, cid, oid):
        return [i for i in self.t["order_items"] if i["company"] == cid and i["order_id"] == oid]

    # ---------- step 3: shipments
    def group(self, cid, c, orders):
        """Group by corridor and handling (food apart from chemicals; chilled apart)."""
        g = defaultdict(list)
        for o in orders:
            s = self.W.site(cid, o["site_id"])
            for it in self.items(cid, o["order_id"]):
                hc = self.prod[it["sku"]]["handling_class"]
                seg = "chem" if hc == "chemical" else "chilled" if hc == "chilled" else "food"
                g[(self.corridor_of(c["region"], s["town"]), seg)].append((o, it))
        return [(k[1], g[k]) for k in sorted(g)]

    def pack(self, cid, c, d, group, planner, seg="food"):
        """Greedy packing into loads of up to 3 stops, nearest stop first, within the biggest allowed truck."""
        depot = c["depot"]
        by_site = defaultdict(list)
        for o, it in group:
            by_site[o["site_id"]].append((o, it))
        sites = sorted(by_site, key=lambda sid: (self.W.town_km(depot, self.W.site(cid, sid)["town"]), sid))
        loads, cur = [], None
        for sid in sites:
            lines = by_site[sid]
            kg = sum(self.prod[it["sku"]]["case_kg"] * it["ordered_cases"] for _, it in lines)
            m3 = sum(self.prod[it["sku"]]["case_m3"] * it["ordered_cases"] for _, it in lines)
            cap = self.max_class(cid, planner, [sid], seg)
            if cur and len(cur["stops"]) < 3 and cur["kg"] + kg <= self.vc[cap]["payload_kg"] \
                    and cur["m3"] + m3 <= self.vc[cap]["volume_m3"] and self.max_class(cid, planner, cur["stops"] + [sid], seg) == cap:
                cur["stops"].append(sid)
                cur["lines"] += lines
                cur["kg"] += kg
                cur["m3"] += m3
            else:
                cur = {"stops": [sid], "lines": list(lines), "kg": kg, "m3": m3}
                loads.append(cur)
        out = []
        for ld in loads:   # split loads bigger than the biggest allowed truck
            cap = self.max_class(cid, planner, ld["stops"], seg)
            while ld["kg"] > self.vc[cap]["payload_kg"] or ld["m3"] > self.vc[cap]["volume_m3"]:
                part = {"stops": list(ld["stops"]), "lines": [], "kg": 0.0, "m3": 0.0}
                rest = []
                for o, it in ld["lines"]:
                    p = self.prod[it["sku"]]
                    fit = int(min((self.vc[cap]["payload_kg"] - part["kg"]) / p["case_kg"],
                                  (self.vc[cap]["volume_m3"] - part["m3"]) / p["case_m3"]))
                    q = it.get("_rem", it["ordered_cases"])
                    take = max(0, min(q, fit))
                    if take:
                        part["lines"].append((o, it, take))
                        part["kg"] += take * p["case_kg"]
                        part["m3"] += take * p["case_m3"]
                    if q - take:
                        it["_rem"] = q - take
                        rest.append((o, it))
                    else:
                        it.pop("_rem", None)
                out.append(part)
                ld = {"stops": ld["stops"], "lines": rest,
                      "kg": sum(self.prod[i["sku"]]["case_kg"] * i["_rem"] for _, i in rest),
                      "m3": sum(self.prod[i["sku"]]["case_m3"] * i["_rem"] for _, i in rest)}
                for _, i in rest:
                    i["_whole"] = False
            ld["lines"] = [(o, it, it.pop("_rem", it["ordered_cases"])) for o, it in ld["lines"]]
            if ld["lines"]:
                out.append(ld)
        for ld in out:
            used = {o["site_id"] for o, _, _ in ld["lines"]}
            ld["stops"] = [s for s in ld["stops"] if s in used]
        return [ld for ld in out if ld["lines"]]

    def max_class(self, cid, planner, stop_ids, seg="food"):
        """Biggest truck the planner believes can serve every stop (only rules the planner knows count)."""
        limit = 99
        for sid in stop_ids:
            s = self.W.site(cid, sid)
            known = s["known"].get("max_vehicle_length_ft")
            if known:
                limit = min(limit, known)
            for r in self.W.rules_of("site_access"):
                if r["site"] == s["site_key"] and self.knows(cid, planner, r["id"]):
                    limit = min(limit, r["max_length_ft"])
            for r in self.W.rules_of("time_window"):
                if r["site"] == s["site_key"] and self.knows(cid, planner, r["id"]):
                    limit = min(limit, r["min_length_ft"] - 1)
        if seg == "chilled" and any(v["class"] == "REEFER14" for v in self.W.vehicles if v["company"] == cid):
            return "REEFER14"
        ok = [k for k, v in self.vc.items() if v["length_ft"] <= limit and k != "REEFER14"]
        return max(ok, key=lambda k: self.vc[k]["payload_kg"])

    # ---------- step 4-7: dispatch, supply, outcomes, paperwork
    def choose_vehicle(self, cid, c, d, ld, planner, r, chilled, exclude=()):
        need_kg, need_m3 = ld["kg"], ld["m3"]
        cap = self.max_class(cid, planner, ld["stops"])
        towns = {self.W.site(cid, s)["town"] for s in ld["stops"]}
        classes = sorted((k for k, v in self.vc.items() if v["payload_kg"] >= need_kg and v["volume_m3"] >= need_m3
                          and v["length_ft"] <= self.vc[cap]["length_ft"]), key=lambda k: self.vc[k]["payload_kg"])
        if chilled and need_kg <= self.vc["REEFER14"]["payload_kg"]:
            classes = ["REEFER14"] + [k for k in classes if k != "REEFER14"]
        elif not chilled:
            classes = [k for k in classes if k != "REEFER14"]
        for h in self.W.rules_of("habit"):
            if h["company"] == cid and h["town"] in towns and h["vehicle_class"] in self.vc:
                classes = [h["vehicle_class"]] + classes            # the Khammam habit (H-08)
        avoid = set()
        for vr in self.W.rules_of("vendor_reliability"):
            if vr["company"] == cid and self.rush(d) and self.knows(cid, planner, vr["id"]):
                avoid.add(vr["vendor"])
        pool = [v for v in self.W.vehicles if v["company"] == cid and v["vehicle_id"] not in self.busy[(cid, d)]
                and v["vehicle_id"] not in exclude and not (v["maintenance_day"] and v["maintenance_day"] == d.day)
                and self.free_at.get((cid, v["vehicle_id"]), datetime.min) <= at(d - timedelta(days=1), 21)
                and self.blocked.get((cid, v["vehicle_id"]), d) <= d]
        for cls in classes:
            cands = [v for v in pool if v["class"] == cls and v["vendor"] not in avoid]
            checked = [v for v in cands if r.random() < 0.7 or min(v[k] for k in ("fitness_until", "permit_until",
                       "insurance_until", "puc_until")) >= d.isoformat()]   # the planner checks documents most of the time
            for owner in ("own", "attached", "spot"):
                vs = [v for v in checked if v["owner"] == owner]
                if vs:
                    return r.choice(sorted(vs, key=lambda v: v["vehicle_id"]))
        return None

    def dispatch(self, cid, c, d, ld, planner, r, rx, depth=0):
        W, rates = self.W, self.cfg["rates"]
        chilled = any(self.prod[it["sku"]]["handling_class"] == "chilled" for _, it, _ in ld["lines"])
        if depth < 2 and not self.choose_vehicle(cid, c, d, ld, planner, random_probe(r), chilled):
            halves = split_load(ld, self.prod)
            if halves:
                for h in halves:
                    self.dispatch(cid, c, d, h, planner, r, rx, depth + 1)
                return
        plan_time = at(d - timedelta(days=1), r.randint(12, 15), r.choice([0, 10, 25, 40, 50]))
        sid = self.nid("S", cid)
        v = self.choose_vehicle(cid, c, d, ld, planner, r, chilled)
        cc = next((rr for rr in W.rules_of("cold_chain") if rr["company"] == cid), None)
        if chilled and v and v["class"] != "REEFER14" and cc and rx.random() > cc["shortcut_share"]:
            self.replan(cid, at(d - timedelta(days=1), 16), "no_reefer", sid)
            self.resend(cid, d, ld["lines"], "no_reefer", r)
            return
        tried = []
        mult = rates["rush_multiplier"] if self.rush(d) else 1.0
        while v:
            self.busy[(cid, d)].add(v["vehicle_id"])
            placed, report_late = "on_time", 0
            if v["owner"] != "own":
                p_ns = rates["spot_no_show"] if v["owner"] == "spot" else rates["vendor_no_show"] * mult
                for vr in W.rules_of("vendor_reliability"):
                    if vr["company"] == cid and vr["vendor"] == v["vendor"]:
                        p_ns = vr["rush_no_show"] if self.rush(d) else vr["normal_no_show"]
                        rid = vr["id"]
                if rx.random() < p_ns:
                    placed = "no_show"
                elif rx.random() < rates["late_report"] * mult:
                    placed, report_late = "late", rx.randint(60, 240)
            if v["owner"] != "own" or placed != "on_time":
                self.add("vehicle_placements", company=cid, shipment_id=sid, vehicle_id=v["vehicle_id"],
                         vendor=v["vendor"], confirmed_at=iso(plan_time + timedelta(minutes=30)), status=placed,
                         reported_late_min=report_late,
                         true_cause=("vendor_reliability" if placed == "no_show" and any(
                             vr["company"] == cid and vr["vendor"] == v["vendor"] for vr in W.rules_of("vendor_reliability")) else None),
                         rule_id=next((vr["id"] for vr in W.rules_of("vendor_reliability")
                                       if vr["company"] == cid and vr["vendor"] == v["vendor"] and placed == "no_show"), None))
            if placed != "no_show":
                break
            if any(vr["company"] == cid and vr["vendor"] == v["vendor"] for vr in W.rules_of("vendor_reliability")):
                self.saw_failure(cid, next(vr["id"] for vr in W.rules_of("vendor_reliability") if vr["vendor"] == v["vendor"]))
            tried.append(v["vehicle_id"])
            nv = self.choose_vehicle(cid, c, d, ld, planner, r, chilled, exclude=tried)
            self.replan(cid, at(d - timedelta(days=1), 18), "vendor_no_show", sid)
            if nv:
                self.add("staff_edits", company=cid, ts=iso(at(d - timedelta(days=1), 18, 15)), user=planner["name"],
                         entity="shipment", entity_id=sid, field="vehicle_id", old=v["vehicle_id"], new=nv["vehicle_id"],
                         reason_code="vendor_no_show", correct=True)
            v = nv
        if not v:
            for o, it, q in ld["lines"]:
                o["status"] = "rolled_over"
            self.replan(cid, at(d - timedelta(days=1), 19), "no_vehicle", sid)
            self.resend(cid, d, ld["lines"], "no_vehicle", r)
            return
        self.run_trip(cid, c, d, ld, planner, v, sid, plan_time, report_late, chilled, r, rx)

    def run_trip(self, cid, c, d, ld, planner, v, sid, plan_time, report_late, chilled, r, rx):
        W, rates = self.W, self.cfg["rates"]
        stops = [W.site(cid, s) for s in ld["stops"]]
        orders = {o["order_id"]: o for o, _, _ in ld["lines"]}
        win0 = min(int(o["window_start"][:2]) for o in orders.values())
        # planner works backwards from the earliest window (spec §2.1)
        t_first, _ = self.travel_min(c["depot"], stops[0]["town"])
        target = at(d, win0)
        for s in stops:
            for rr in W.rules_of("night_only"):
                if rr["site"] == s["site_key"] and self.knows(cid, planner, rr["id"]):
                    target = at(d - timedelta(days=1), 22, 30)
        depart = target - timedelta(minutes=t_first + 30)
        load_start = depart - timedelta(minutes=r.randint(60, 120)) + timedelta(minutes=report_late)
        load_start = max(load_start, self.free_at.get((cid, v["vehicle_id"]), datetime.min))
        driver = self.driver_for(cid, v, d, rx)
        self.add("shipments", company=cid, shipment_id=sid, plan_date=(d - timedelta(days=1)).isoformat(),
                 delivery_date=d.isoformat(), planned_by=planner["name"], vehicle_id=v["vehicle_id"],
                 vehicle_class=v["class"], driver=driver, weight_kg=round(ld["kg"], 1), volume_m3=round(ld["m3"], 2),
                 stops=len(stops), planned_at=iso(plan_time), load_sequence="last-drop-first")
        for i, s in enumerate(stops, 1):
            self.add("shipment_stops", company=cid, shipment_id=sid, seq=i, site_id=s["site_id"])
        for o, it, q in ld["lines"]:
            self.add("shipment_items", company=cid, shipment_id=sid, order_id=o["order_id"], sku=it["sku"], cases=q)
            it["allocated_cases"] += q
            o["status"] = "planned"
        ev = lambda ts, kind, **kw: self.add("trip_events", company=cid, shipment_id=sid, ts=iso(ts), kind=kind, **kw)
        t = load_start
        ev(t, "reported" if not report_late else "reported_late", minutes=report_late)
        # loading checks: documents, weighbridge (paper overload and real capacity)
        docs_min = min(v[k] for k in ("fitness_until", "permit_until", "insurance_until", "puc_until"))
        if docs_min < d.isoformat():
            ev(t, "rejected_at_loading", reason="vehicle documents expired", true_cause="documents_expired")
            renew = d + timedelta(days=rx.randint(3, 10))
            self.blocked[(cid, v["vehicle_id"])] = renew
            for k in ("fitness_until", "permit_until", "insurance_until", "puc_until"):
                if v[k] < d.isoformat():
                    self.add("staff_edits", company=cid, ts=iso(at(renew, 11)), user=planner["name"], entity="vehicle",
                             entity_id=v["vehicle_id"], field=k, old=v[k], new=(renew + timedelta(days=365)).isoformat(),
                             reason_code="documents_renewed", correct=True)
                    v[k] = (renew + timedelta(days=365)).isoformat()
            self.replan(cid, t, "documents_expired", sid)
            self.busy[(cid, d)].add(v["vehicle_id"])
            nv = self.choose_vehicle(cid, c, d, ld, planner, r, chilled, exclude=[v["vehicle_id"]])
            if not nv:
                for o in orders.values():
                    o["status"] = "rolled_over"
                self.resend(cid, d, ld["lines"], "no_vehicle", r)
                return
            self.add("staff_edits", company=cid, ts=iso(t + timedelta(minutes=10)), user=planner["name"],
                     entity="shipment", entity_id=sid, field="vehicle_id", old=v["vehicle_id"], new=nv["vehicle_id"],
                     reason_code="documents_expired", correct=True)
            self.t["shipments"][-1]["vehicle_id"], self.t["shipments"][-1]["vehicle_class"] = nv["vehicle_id"], nv["class"]
            self.busy[(cid, d)].add(nv["vehicle_id"])
            v = nv
        t += timedelta(minutes=r.randint(45, 90) + (r.randint(30, 120) if rx.random() < rates["loading_delay"] else 0))
        kg = ld["kg"]
        if rx.random() < rates["planner_overload_mistake"]:
            kg = v["payload_kg"] * rx.uniform(1.05, 1.15)
        limit = min(v["payload_kg"], v["real_payload_kg"])
        offloaded = 0.0
        if kg > limit + 1:
            offloaded = kg - limit
            real = v["real_payload_kg"] < v["payload_kg"] and kg > v["real_payload_kg"]
            rid = next((rr["id"] for rr in W.rules_of("real_capacity") if rr.get("resolved", {}).get(cid) == v["vehicle_id"]), None)
            ev(t, "weighbridge_offload", kg=round(offloaded), true_cause="real_capacity" if real else "overload",
               rule_id=rid if real else None)
            if real and rid:
                self.saw_failure(cid, rid)
        ev(t, "loaded", kg=round(kg - offloaded))
        t += timedelta(minutes=15)
        ev(t, "departed")
        value = sum(self.prod[it["sku"]]["price_rs"] * q for _, it, q in ld["lines"])
        km_total, here = 0.0, c["depot"]
        ewb_missing = value > 50000 and rx.random() < rates["missing_eway_bill"]
        offload_left = offloaded
        for i, s in enumerate(stops, 1):
            mins, km_ = self.travel_min(here, s["town"])
            km_total += km_
            t += timedelta(minutes=mins)
            self.road(cid, c, d, sid, v, here, s, t, rx, ev, i, ewb_missing and i == 1)
            t = datetime.fromisoformat(self.t["trip_events"][-1]["ts"]) if self.t["trip_events"][-1]["kind"] != "departed" else t
            here = s["town"]
            t = self.at_stop(cid, c, d, sid, v, s, i, t, ld, orders, planner, rx, ev, offload_left, chilled)
            offload_left = 0
        self.free_at[(cid, v["vehicle_id"])] = t + timedelta(hours=1)
        self.paperwork(cid, sid, d, ld, value, km_total, v, rx)

    def driver_for(self, cid, v, d, rx):
        if v["owner"] != "own":
            return f"{v['vendor']} driver"
        ds = [x for x in self.W.drivers if x["company"] == cid]
        own = sorted(x["vehicle_id"] for x in self.W.vehicles if x["company"] == cid and x["owner"] == "own")
        idx = own.index(v["vehicle_id"]) % len(ds)
        if rx.random() < self.cfg["rates"]["driver_absent"]:
            self.replan(cid, at(d - timedelta(days=1), 20), "driver_absent", v["vehicle_id"])
            idx = (idx + 1) % len(ds)
        return ds[idx]["driver_id"]

    def road(self, cid, c, d, sid, v, frm, s, t, rx, ev, seq, ewb_missing):
        rates = self.cfg["rates"]
        delay, causes = 0, []
        if d in self.bandh_days:
            delay += rx.randint(120, 300)
            causes.append(("bandh", None))
        if self.in_monsoon(d) and self.W.towns[s["town"]]["tier"] == 3 and rx.random() < rates["rain_delay"]:
            delay += rx.randint(30, 120)
            causes.append(("rain", None))
        for cl in self.W.rules_of("closure"):
            if as_date(cl["valid_from"]) <= d <= as_date(cl["valid_to"]) and cl["town"] in (frm, s["town"]) and frm != s["town"]:
                delay += cl["delay_min"]
                causes.append(("closure", cl["id"]))
        if rx.random() < rates["breakdown"]:
            delay += rx.randint(90, 300)
            causes.append(("breakdown", None))
        if ewb_missing:
            delay += rx.randint(150, 240)
            causes.append(("missing_eway_bill", None))
        for cause, rid in causes:
            ev(t, "delay", stop_seq=seq, cause_seen=cause, true_cause=cause, rule_id=rid)
        ev(t + timedelta(minutes=delay), "arrived", stop_seq=seq, site_id=s["site_id"])

    def at_stop(self, cid, c, d, sid, v, s, seq, t, ld, orders, planner, rx, ev, offloaded, chilled):
        W, rates = self.W, self.cfg["rates"]
        tp = s["true"]
        lines = [(o, it, q) for o, it, q in ld["lines"] if o["site_id"] == s["site_id"]]
        fail, wait, rid, cause = None, 0, None, None
        for rr in W.rules_of("one_off"):
            if as_date(rr["date"]) == d and rr["town"] == s["town"]:
                fail, cause, rid = "road_blocked", "rain_waterlogging", rr["id"]
        for rr in W.rules_of("moved_godown"):
            if rr["site"] == s["site_key"] and d >= as_date(rr["from_date"]) and not self.knows(cid, planner, rr["id"]):
                t += timedelta(minutes=rr["delay_min"])
                ev(t, "delay", stop_seq=seq, cause_seen="address", true_cause="moved_godown", rule_id=rr["id"])
                self.saw_failure(cid, rr["id"])
        if not fail and tp["weekly_off"] is not None and d.weekday() == tp["weekly_off"]:
            rid = next((rr["id"] for rr in W.rules_of("weekly_off") if rr["town"] == s["town"]), None)
            fail, cause = "shop_closed", "weekly_off"
        if not fail and d in self.closed_days:
            fail, cause = "shop_closed", "festival_holiday"
        if not fail and tp["max_vehicle_length_ft"] and v["length_ft"] > tp["max_vehicle_length_ft"]:
            rid = next((rr["id"] for rr in W.rules_of("site_access") if rr["site"] == s["site_key"]), None)
            fail, cause = "could_not_enter", "site_access"
        for rr in W.rules_of("contradiction"):
            if not fail and rr["site"] == s["site_key"] and as_date(rr["false_note_date"]) <= d and (cid, rr["id"]) not in self.fired:
                fail, cause, rid = "could_not_enter", "driver_error", rr["id"]
                self.fired.add((cid, rr["id"]))
        if not fail:
            hour = t.hour + t.minute / 60
            if tp["night_only"] and 6 <= hour < 22:
                wait += (at(t.date(), 22) - t).total_seconds() / 60
                cause, rid = "night_only", next((rr["id"] for rr in W.rules_of("night_only") if rr["site"] == s["site_key"]), None)
            for rr in W.rules_of("time_window"):
                if rr["site"] == s["site_key"] and v["length_ft"] >= rr["min_length_ft"] and rr["from_hour"] <= hour < rr["to_hour"]:
                    wait += (at(t.date(), rr["to_hour"]) - t).total_seconds() / 60
                    cause, rid = "time_window", rr["id"]
            if not tp["night_only"] and hour >= tp["receiving_until_hour"]:
                wait += (at(t.date() + timedelta(days=1), 8) - t).total_seconds() / 60
                cause = "receiving_hours"
                rid = next((rr["id"] for rr in W.rules_of("receiving_hours") if rr["site"] == s["site_key"]), None)
            if rx.random() < rates["godown_full"]:
                wait += rx.randint(240, 720)
                cause = cause or "godown_full"
            elif rx.random() < rates["unloading_wait_long"]:
                wait += rx.randint(120, 240)
                cause = cause or "unloading_wait"
        if wait:
            ev(t, "waiting", stop_seq=seq, minutes=round(wait), true_cause=cause, rule_id=rid)
            t += timedelta(minutes=wait)
        if fail:
            ev(t, "not_delivered", stop_seq=seq, status_seen=fail, true_cause=cause, rule_id=rid)
            if rid and cause in ("site_access", "weekly_off", "rain_waterlogging", "driver_error"):
                self.saw_failure(cid, rid)
            self.resend(cid, d, lines, fail, rx)
            for o, it, q in lines:
                it["returned_cases"] += q
                o["status"] = "returned"
            self.add("trip_outcomes", company=cid, shipment_id=sid, stop_seq=seq, site_id=s["site_id"], status="returned",
                     delivered_cases=0, returned_cases=sum(q for _, _, q in lines), wait_min=round(wait),
                     arrived_at=iso(t), true_cause=cause, rule_id=rid)
            return t + timedelta(minutes=20)
        t += timedelta(hours=tp["typical_unload_hours"])
        delivered, returned, status = 0, 0, "delivered"
        cc = next((rr for rr in W.rules_of("cold_chain") if rr["company"] == cid), None)
        spoil = chilled and v["class"] != "REEFER14" and rx.random() < (cc["spoil_prob"] if cc else 1.0)
        for o, it, q in lines:
            q_ok = q
            if offloaded > 0:
                cut = min(q, math.ceil(offloaded / self.prod[it["sku"]]["case_kg"]))
                q_ok -= cut
                offloaded -= cut * self.prod[it["sku"]]["case_kg"]
                status = "partial"
            if spoil and self.prod[it["sku"]]["handling_class"] == "chilled":
                returned += q_ok
                it["returned_cases"] += q_ok
                q_ok, status = 0, "partial"
            elif q_ok > 0 and rx.random() < rates["partial_acceptance"]:
                back = max(1, q_ok // 5)
                q_ok -= back
                returned += back
                it["returned_cases"] += back
                status = "partial"
            it["delivered_cases"] += q_ok
            delivered += q_ok
            o["status"] = "delivered" if status == "delivered" else "partially_delivered"
        damaged = rx.randint(1, 6) if rx.random() < rates["damage"] else 0
        if spoil:
            cause, rid, wait_rule = "cold_chain", cc["id"] if cc else None, True
        else:
            wait_rule = bool(wait)
        ev(t, "delivered" if status == "delivered" else "partially_delivered", stop_seq=seq,
           true_cause=cause if wait_rule else None, rule_id=rid if wait_rule else None)
        self.add("trip_outcomes", company=cid, shipment_id=sid, stop_seq=seq, site_id=s["site_id"], status=status,
                 delivered_cases=delivered, returned_cases=returned, wait_min=round(wait), damaged_cases=damaged,
                 arrived_at=iso(t), true_cause=cause if wait_rule else None, rule_id=rid if wait_rule else None)
        return t + timedelta(minutes=10)

    def resend(self, cid, d, lines, why, r):
        nd = d + timedelta(days=1)
        seen = set()
        for o, it, q in lines:
            if o["order_id"] in seen:
                continue
            seen.add(o["order_id"])
            ro = dict(o, order_id=self.nid("O", cid), delivery_date=nd.isoformat(), status="open", _resend=True,
                      resend_of=o["order_id"], priority="resend", created_at=iso(at(d, 19)))
            self.t["orders"].append(ro)
            self.t["_resend"].append(ro)
            for oo, ii, qq in lines:
                if oo is o:
                    self.add("order_items", company=cid, order_id=ro["order_id"], sku=ii["sku"], ordered_cases=qq,
                             cancelled_cases=0, allocated_cases=0, delivered_cases=0, returned_cases=0)
        self.replan(cid, at(d, 19), f"resend_{why}", None)

    def paperwork(self, cid, sid, d, ld, value, km_total, v, r):
        by_order = defaultdict(float)
        for o, it, q in ld["lines"]:
            by_order[o["order_id"]] += self.prod[it["sku"]]["price_rs"] * q
        ev_missing = any(e["shipment_id"] == sid and e.get("cause_seen") == "missing_eway_bill" for e in self.t["trip_events"][-30:])
        for oid, val in by_order.items():
            inv = self.nid("INV", cid)
            self.add("invoices", company=cid, invoice_no=inv, order_id=oid, shipment_id=sid, value_rs=round(val),
                     gstin=self.W.site(cid, next(o["site_id"] for o, _, _ in ld["lines"] if o["order_id"] == oid))["gstin"])
            lr = self.nid("LR", cid)
            self.add("lorry_receipts", company=cid, lr_no=lr, shipment_id=sid, order_id=oid, invoice_no=inv)
            if val > 50000:
                days = max(1, math.ceil(km_total / 200))
                self.add("eway_bills", company=cid, ewb_no=f"{r.randint(10**11, 10**12 - 1)}", invoice_no=inv,
                         generated_at=iso(at(d - timedelta(days=1), 17)),
                         valid_until=iso(at(d - timedelta(days=1), 23, 59) + timedelta(days=days)),
                         status="missing_at_checkpost" if ev_missing else "ok")
        for oc in [x for x in self.t["trip_outcomes"] if x["shipment_id"] == sid]:
            if oc["status"] != "returned":
                self.add("proof_of_delivery", company=cid, shipment_id=sid, stop_seq=oc["stop_seq"],
                         signed=r.random() > 0.04, received_by=r.choice(["owner", "munim", "godown staff", "store manager"]))
            det = self.cfg["detention"]
            if oc["wait_min"] / 60 > det["free_hours"]:
                self.add("trip_charges", company=cid, shipment_id=sid, kind="detention",
                         amount_rs=round((oc["wait_min"] / 60 - det["free_hours"]) * det["rate_per_hour"]))
        if v["owner"] == "spot":
            base = self.vc[v["class"]]["rate_per_km"] * km_total
            self.add("trip_charges", company=cid, shipment_id=sid, kind="spot_premium",
                     amount_rs=round(base * self.cfg["spot_premium"]))

    def replan(self, cid, t, reason, ref):
        self.add("replans", company=cid, ts=iso(t), date=t.date().isoformat(), reason=reason, ref=ref)
