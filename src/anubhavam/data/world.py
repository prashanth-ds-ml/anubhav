"""Step 1: the static world. Towns, companies, sites (true and known profiles), products, vendors,
vehicles, drivers, and the hidden rules resolved to concrete ids. Nothing here depends on the calendar."""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import as_date, rng

NAME_HEADS = ["Sri Sai", "Sri Venkateswara", "Lakshmi", "Durga", "Balaji", "Vijaya", "Sai Krishna", "Annapurna",
              "Srinivasa", "Mahalakshmi", "Kanaka Durga", "Raghavendra", "Anjaneya", "Sri Rama", "Bhavani", "Padmavathi",
              "Sri Satya", "Manikanta", "Siddhi Vinayaka", "Venkata Ramana", "Sri Krishna", "Gayathri", "Saraswathi",
              "Renuka", "Mallikarjuna", "Sri Ganga", "Jaya", "Chaitanya", "Sri Sambasiva", "Ayyappa"]
NAME_TAILS = {"old_town_godown": ["Agencies", "Traders", "Distributors", "Enterprises", "Wholesale"],
              "highway_warehouse": ["Warehousing", "Distributors", "Logistics Godown", "Marketing"],
              "modern_trade": ["Supermarket", "Mart", "Hypermarket", "Fresh Mart"],
              "rural_substockist": ["Kirana & General", "General Stores", "Stores", "Traders"]}
STREETS = ["Main Road", "Station Road", "Bus Stand Road", "Market Road", "Old Town", "Bypass Road", "Gandhi Chowk",
           "Kaman Road", "Subhash Nagar", "Industrial Area", "Ring Road", "Mandi Road"]
DRIVER_NAMES = ["Ramesh", "Suresh", "Raju", "Srinu", "Venkatesh", "Mallesh", "Yadagiri", "Narsimha", "Ravi", "Kumar",
                "Sampath", "Anjaneyulu", "Balraj", "Shankar", "Ilaiah", "Komuraiah", "Rajaiah", "Sailu", "Mahender",
                "Bhaskar", "Sudhakar", "Prakash", "Ashok", "Raghu", "Naveen", "Sridhar", "Yakub", "Imran", "Babu", "Lingaiah"]
REG_RTO = {"WGL": ["TS 03", "TS 24", "TS 26"], "HYD": ["TS 07", "TS 08", "TS 09", "TS 10"]}
ID_FORMATS = {"A": ("V{:02d}", "C{:04d}"), "B": ("TRK-{:03d}", "CN-{:04d}"), "C": ("DFS-T{:03d}", "CONS{:05d}")}
PROFILE_FIELDS = ("max_vehicle_length_ft", "receiving_until_hour", "weekly_off", "night_only", "typical_unload_hours")


def km(a, b, cfg):
    """Road km between two towns: haversine x road factor (fallback until OSM distances are added)."""
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)) * cfg["road_factor"], 1)


@dataclass
class World:
    cfg: dict
    companies: dict = field(default_factory=dict)       # id -> company config + resolved fields
    towns: dict = field(default_factory=dict)
    sites: list = field(default_factory=list)            # one row per (company, site)
    products: list = field(default_factory=list)
    vehicles: list = field(default_factory=list)
    drivers: list = field(default_factory=list)
    rules: list = field(default_factory=list)            # hidden rules with resolved ids

    def town_km(self, a, b):
        return 0.0 if a == b else km(self.towns[a], self.towns[b], self.cfg)

    def site(self, company, site_id):
        return next(s for s in self.sites if s["company"] == company and s["site_id"] == site_id)

    def site_by_key(self, company, key):
        return next((s for s in self.sites if s["company"] == company and s["site_key"] == key), None)

    def vehicle(self, company, vid):
        return next(v for v in self.vehicles if v["company"] == company and v["vehicle_id"] == vid)

    def rule(self, rid):
        return next(r for r in self.rules if r["id"] == rid)

    def rules_of(self, kind):
        return [r for r in self.rules if r["kind"] == kind]


def _variant(cfg, cid, c):
    if c["variant"] != "random":
        return c["variant"]
    return rng(cfg, "geography", cid, "variant").choice(["A", "B", "C"])


def _town_pick(r, towns, cfg):
    names = sorted(towns)
    return r.choices(names, [cfg["tier_weight"][towns[n]["tier"]] for n in names])[0]


def _unique_name(r, used, stype):
    for _ in range(200):
        n = f"{r.choice(NAME_HEADS)} {r.choice(NAME_TAILS[stype])}"
        if n not in used:
            used.add(n)
            return n
    raise RuntimeError("ran out of site names")


def _true_profile(r, stype):
    return {"max_vehicle_length_ft": None,
            "receiving_until_hour": r.choice([20, 20, 21, 22]) if stype != "highway_warehouse" else 23,
            "weekly_off": None, "night_only": False,
            "typical_unload_hours": {"old_town_godown": 1.5, "highway_warehouse": 1.0, "modern_trade": 1.0,
                                     "rural_substockist": 0.75}[stype]}


def _known_profile(r, true, cfg, protect=()):
    """What the company's system knows: mostly blank, some right, some outdated or wrong (spec §3.4).
    Fields named in `protect` carry a hidden rule and are never filled correctly."""
    p = cfg["known_profile"]
    known = {}
    for f in PROFILE_FIELDS:
        roll = r.random()
        if f in protect:
            roll = 0.0 if roll < 0.85 else 0.99          # blank, or wrong/outdated
        if roll < p["blank"]:
            known[f] = None
        elif roll < p["blank"] + p["correct"]:
            known[f] = true[f]
        else:
            known[f] = {"max_vehicle_length_ft": 32, "receiving_until_hour": 20, "weekly_off": None, "night_only": False,
                        "typical_unload_hours": 1.0}[f]
            if known[f] == true[f] and f == "receiving_until_hour":
                known[f] = 21
    return known


def build(cfg, company_ids=None) -> World:
    W = World(cfg)
    W.towns = {t["name"]: t for t in cfg["towns"]}
    company_ids = company_ids or list(cfg["companies"])
    for cid in company_ids:
        c = dict(cfg["companies"][cid])
        c["id"], c["variant"] = cid, _variant(cfg, cid, c)
        W.companies[cid] = c
    _products(W)
    _sites(W)
    _fleet(W)
    _rules(W)
    return W


def _products(W):
    for brand, b in W.cfg["brands"].items():
        for i, (name, kg, m3, price) in enumerate(b["skus"]):
            W.products.append({"sku": f"{''.join(w[0] for w in brand.split())}-{i + 1:02d}", "brand": brand,
                               "name": name, "handling_class": b["class"], "case_kg": kg, "case_m3": m3,
                               "price_rs": price, "stack_max": 6 if b["class"] == "light_food" else 10,
                               "temp_band": "2-8C" if b["class"] == "chilled" else "ambient"})


def _sites(W):
    cfg = W.cfg
    anchors = {a["id"]: a for a in cfg["anchor_sites"]}
    r = rng(cfg, "geography", "sites")
    used_names = {a["name"] for a in anchors.values()}
    region_towns = {reg: {n: t for n, t in W.towns.items() if t["region"] == reg} for reg in ("WGL", "HYD")}

    def make_key(rr, prefix, region, stype):
        town = _town_pick(rr, region_towns[region], cfg)
        return {"site_key": f"{prefix}{sum(k['site_key'].startswith(prefix) for k in pool):03d}",
                "name": _unique_name(rr, used_names, stype), "town": town, "type": stype, "entrances": ["main"],
                "street": rr.choice(STREETS)}

    # shared pool for the Warangal region (T01/T02/TNEW overlap), then each company's own sites
    pool = []
    stypes = list(cfg["site_types"])
    sweights = [cfg["site_types"][s]["share"] for s in stypes]
    n_shared = 8
    shared = []
    for _ in range(n_shared):
        k = make_key(r, "SH", "WGL", r.choices(stypes, sweights)[0])
        pool.append(k)
        shared.append(k)
    for cid, c in W.companies.items():
        cr = rng(cfg, "geography", "sites", cid)
        n_total = cr.randint(*c["sites"])
        mine = [anchors[a] | {"site_key": a} for a in anchors if cid in anchors[a]["companies"]]
        if c["region"] == "WGL":
            want_shared = round(cfg["shared_site_share"] * n_total) - sum(1 for a in mine if len(a["companies"]) > 1)
            mine += cr.sample(shared, max(0, min(len(shared), want_shared)))
        while len(mine) < n_total:
            k = make_key(cr, f"{cid}-", c["region"], cr.choices(stypes, sweights)[0])
            pool.append(k)
            mine.append(k)
        fmt = ID_FORMATS[c["variant"]][1]
        for i, s in enumerate(sorted(mine, key=lambda s: s["site_key"])):
            sr = rng(cfg, "geography", "profile", s["site_key"])
            true = _true_profile(sr, s["type"])
            W.sites.append({"company": cid, "site_id": fmt.format(i + 1), "site_key": s["site_key"], "name": s["name"],
                            "town": s["town"], "pin": W.towns[s["town"]]["pin"], "type": s["type"],
                            "street": s.get("street") or sr.choice(STREETS), "entrances": list(s["entrances"]),
                            "phone": f"9{sr.randint(100000000, 999999999)}",
                            "gstin": f"36{sr.choice('ABCDEFGHJK')}{sr.randint(10000, 99999)}{sr.choice('PQRSTUVWXYZ')}{sr.randint(1, 9)}Z{sr.randint(1, 9)}",
                            "demand_weight": cfg["tier_weight"][W.towns[s["town"]]["tier"]] * sr.uniform(0.5, 1.5),
                            "true": true, "known": None, "credit_hold_days": set()})


def _fleet(W):
    cfg = W.cfg
    vc = cfg["vehicle_classes"]
    mix = cfg["fleet_mix"]
    own_share = mix["own"] / (mix["own"] + mix["attached"])
    for cid, c in W.companies.items():
        r = rng(cfg, "resources", "fleet", cid)
        fmt = ID_FORMATS[c["variant"]][0]
        n = 0
        rto = REG_RTO[c["region"]]
        for cls, count in c["fleet"].items():
            for _ in range(count):
                n += 1
                own = r.random() < own_share
                age = r.randint(1, 12)
                start = as_date(cfg["period"]["start"])
                docs = {d: (start + timedelta(days=r.randint(120, 700))).isoformat()
                        for d in ("fitness_until", "permit_until", "insurance_until", "puc_until")}
                if r.random() < 0.12:     # some documents lapse during the 90 days
                    d = r.choice(list(docs))
                    docs[d] = (start + timedelta(days=r.randint(10, 85))).isoformat()
                W.vehicles.append({
                    "company": cid, "vehicle_id": fmt.format(n), "class": cls, "length_ft": vc[cls]["length_ft"],
                    "payload_kg": vc[cls]["payload_kg"], "volume_m3": vc[cls]["volume_m3"],
                    "body": "reefer" if cls == "REEFER14" else ("closed" if cls in ("T14", "T22", "T32S", "T32M") and r.random() < 0.35 else "open"),
                    "owner": "own" if own else "attached", "vendor": c["name"] if own else r.choice(c["vendors"]),
                    "reg_no": f"{r.choice(rto)} {r.choice(['U', 'T', 'Z'])}{r.choice('ABCDEFGH')} {r.randint(1000, 9999)}",
                    "age_years": age, **docs, "maintenance_day": r.randint(1, 28) if own else None,
                    "gps": own or r.random() < 0.4, "real_payload_kg": vc[cls]["payload_kg"]})
        for i in range(c["spot_pool"]):
            cls = r.choice(["LCV407", "T14", "T22", "T32S"])
            W.vehicles.append({
                "company": cid, "vehicle_id": f"SPOT-{i + 1:02d}", "class": cls, "length_ft": vc[cls]["length_ft"],
                "payload_kg": vc[cls]["payload_kg"], "volume_m3": vc[cls]["volume_m3"], "body": "open", "owner": "spot",
                "vendor": "market", "reg_no": f"{r.choice(rto)} {r.choice('UTV')}{r.choice('ABCDEFGH')} {r.randint(1000, 9999)}",
                "age_years": r.randint(4, 15), "fitness_until": "2027-06-30", "permit_until": "2027-06-30",
                "insurance_until": "2027-06-30", "puc_until": "2027-06-30", "maintenance_day": None, "gps": False,
                "real_payload_kg": vc[cls]["payload_kg"]})
        n_drivers = round(1.2 * sum(c["fleet"].values()))
        names = r.sample(DRIVER_NAMES, min(n_drivers, len(DRIVER_NAMES)))
        for i, nm in enumerate(names):
            W.drivers.append({"company": cid, "driver_id": f"{cid}-D{i + 1:02d}", "name": f"{nm} {r.choice('BGKMNRSTVY')}.",
                              "phone": f"9{r.randint(100000000, 999999999)}",
                              "lang": r.choices(list(cfg["driver_languages"]), list(cfg["driver_languages"].values()))[0]})


def _pick_vehicle(W, spec):
    vs = sorted((v for v in W.vehicles if v["company"] == spec["company"] and v["class"] == spec["class"]
                 and v["owner"] != "spot"), key=lambda v: (-v["age_years"], v["vehicle_id"]))
    return vs[spec["index"]] if len(vs) > spec["index"] else None


def _rules(W):
    """Resolve hidden rules to concrete ids, and write their effect into the true (hidden) profiles."""
    for raw in W.cfg["hidden_rules"]:
        r = dict(raw)
        comps = set(W.companies)
        if r["kind"] == "alias":
            r["companies"] = [c for c in r["companies"] if c in comps]
            t = r["target"]
            if "site" in t:
                r["resolved"] = {c: (W.site_by_key(c, t["site"]) or {}).get("site_id") for c in r["companies"]}
            elif "vehicle" in t:
                v = _pick_vehicle(W, t["vehicle"]) if t["vehicle"]["company"] in comps else None
                r["resolved"] = {t["vehicle"]["company"]: v["vehicle_id"]} if v else {}
            else:
                r["resolved"] = {t["vendor"]["company"]: t["vendor"]["name"]} if t["vendor"]["company"] in comps else {}
        if r["kind"] == "real_capacity":
            v = _pick_vehicle(W, r["vehicle"]) if r["vehicle"]["company"] in comps else None
            if v:
                v["real_payload_kg"] = r["real_payload_kg"]
                r["resolved"] = {v["company"]: v["vehicle_id"]}
        for s in W.sites:
            k, t = s["site_key"], s["true"]
            if r["kind"] == "site_access" and k == r["site"]:
                t["max_vehicle_length_ft"] = r["max_length_ft"]
            if r["kind"] == "receiving_hours" and k == r["site"]:
                t["receiving_until_hour"] = r["until_hour"]
            if r["kind"] == "night_only" and k == r["site"]:
                t["night_only"] = True
            if r["kind"] == "weekly_off" and s["town"] == r["town"] and s["type"] in ("old_town_godown", "rural_substockist"):
                t["weekly_off"] = r["weekday"]
        W.rules.append(r)
    protect = {"site_access": "max_vehicle_length_ft", "receiving_hours": "receiving_until_hour",
               "night_only": "night_only", "weekly_off": "weekly_off"}
    for s in W.sites:
        hit = {f for rr in W.rules for kind, f in protect.items()
               if rr["kind"] == kind and (rr.get("site") == s["site_key"] or rr.get("town") == s["town"] and kind == "weekly_off")}
        s["known"] = _known_profile(rng(W.cfg, "geography", "known", s["company"], s["site_key"]), s["true"], W.cfg, hit)
