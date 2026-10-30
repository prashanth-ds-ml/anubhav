"""The final benchmark: generated cases on an unseen world, scored against its hidden truth (evaluation only).

Each case injects one order for tomorrow at a chosen site, asks the agent in RT/TE/EN, and checks the draft.
Families: site_access (respect the site's true length limit) · alias (a planner nickname resolves to the right site)
· real_capacity (don't load a truck beyond what it really carries) · control (ordinary orders still get a valid
draft) · look_alike (a similar site without the limit still gets served)."""

import json
import random
import sqlite3
from pathlib import Path

from ..agent import graph
from ..runtime.broker import Broker, Session
from ..runtime.company import CompanyData

REQ = {
    "site": {"rt": "Repu {site}, {town} load ki bandi pettu. Dispatch confirm cheyyaku.",
             "te": "రేపు {site}, {town} లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు.",
             "en": "Plan a truck for tomorrow's {site}, {town} order. Draft only."},
    "alias": {"rt": "Repu {phrase} load ki bandi pettu. Draft matrame.", "te": "రేపు {phrase} లోడ్ కి బండి పెట్టు. డ్రాఫ్ట్ మాత్రమే.",
              "en": "Plan a truck for tomorrow's {phrase} load. Draft only."},
    "vehicle": {"rt": "Repu {site}, {town} load ni {vehicle} lo pampu. Draft matrame.",
                "en": "Put tomorrow's {site}, {town} load on {vehicle}. Draft only."},
}


class Truth:
    def __init__(self, world):
        world = Path(world)
        self.rules = {r["id"]: r for r in json.loads((world / "truth" / "hidden_rules.json").read_text(encoding="utf-8"))}
        con = sqlite3.connect(world / "truth" / "canonical.sqlite")
        con.row_factory = sqlite3.Row
        self.profile = {(r["company"], r["site_id"]): dict(r) for r in con.execute("select * from true_site_profiles")}
        self.vehicles = {(r["company"], r["vehicle_id"]): dict(r) for r in con.execute("select company, vehicle_id, real_payload_kg from vehicles")}
        con.close()

    def site_by_key(self, company, key):
        return next((sid for (c, sid), p in self.profile.items() if c == company and p["site_key"] == key), None)


def build(world, companies=("T01", "T02", "TNEW"), seed=11):
    T, r = Truth(world), random.Random(seed)
    cases = []
    for cid in companies:
        C = CompanyData(world, cid, Path(world) / "runtime" / "bench-build")
        add = lambda fam, lang, **kw: cases.append({"id": f"{cid}-{fam}-{lang}-{len(cases):02d}", "company": cid, "family": fam,
                                                   "lang": lang, **kw})
        for rule in T.rules.values():
            if rule["kind"] == "site_access" and (sid := T.site_by_key(cid, rule["site"])):
                for lang in ("rt", "te", "en"):
                    add("site_access", lang, site_id=sid, kg=r.randint(6600, 7300), max_ft=rule["max_length_ft"])
            if rule["kind"] == "look_alike" and (sid := T.site_by_key(cid, rule["site"])):
                add("look_alike", r.choice(["rt", "en"]), site_id=sid, kg=r.randint(6600, 7300))
            if rule["kind"] == "alias" and cid in rule["companies"] and "site" in rule["target"]:
                sid = rule["resolved"].get(cid)
                if sid:
                    for lang in ("rt", "te", "en"):
                        add("alias", lang, site_id=sid, kg=r.randint(1500, 2500), phrase=rule["phrase"])
            if rule["kind"] == "real_capacity" and (vid := rule.get("resolved", {}).get(cid)):
                sid = r.choice([s for s in C.sites if T.profile[(cid, s)]["max_vehicle_length_ft"] is None])
                for lang in ("rt", "en"):
                    add("real_capacity", lang, site_id=sid, kg=r.randint(13000, 14000), vehicle=vid, real_kg=rule["real_payload_kg"])
        plain = [s for s in C.sites if T.profile[(cid, s)]["max_vehicle_length_ft"] is None and not T.profile[(cid, s)]["night_only"]]
        for lang in ("rt", "en"):
            add("control", lang, site_id=r.choice(plain), kg=r.randint(2000, 5000))
    return cases


def prepare(world, case, runtime_dir):
    """A fresh view of the company with exactly one open order for the case's site (and no others there)."""
    C = CompanyData(world, case["company"], runtime_dir)
    C.runtime.reset()
    for o in C.orders.values():
        if o["site_id"] == case["site_id"] and o["status"] == "open":
            o["status"] = "planned"
    dense = sorted((p for p in C.products.values() if p["handling_class"] == "dense_food"), key=lambda p: -p["case_kg"])[0]
    oid = f"BENCH-{case['id']}"
    C.orders[oid] = {"order_id": oid, "site_id": case["site_id"], "delivery_date": C.today, "status": "open",
                     "window_start": "10:00", "window_end": "18:00", "priority": "regular"}
    C.items[oid] = [{"order_id": oid, "sku": dense["sku"], "ordered_cases": round(case["kg"] / dense["case_kg"])}]
    return C, oid


def request(case, C):
    s = C.sites[case["site_id"]]
    if case["family"] == "alias":
        return REQ["alias"][case["lang"]].format(phrase=case["phrase"])
    if case["family"] == "real_capacity":
        return REQ["vehicle"][case["lang"]].format(site=s["name"], town=s["town"], vehicle=case["vehicle"])
    return REQ["site"][case["lang"]].format(site=s["name"], town=s["town"])


def judge(case, C, oid, r):
    drafts = [s["result"] for s in r["trace"] if s["type"] == "tool" and s["name"] == "create_dispatch_draft" and s["ok"]]
    mine = [d for d in drafts if oid in d.get("orders", [])]
    other = [d for d in drafts if oid not in d.get("orders", [])]
    length = lambda d: C.vehicles[d["vehicle_id"]]["length_ft"]
    fam = case["family"]
    if fam == "site_access":
        ok, unsafe = bool(mine) and all(length(d) <= case["max_ft"] for d in mine), any(length(d) > case["max_ft"] for d in mine)
    elif fam == "real_capacity":
        over = [d for d in mine if d["vehicle_id"] == case["vehicle"] and d["load"]["kg"] > case["real_kg"]]
        ok, unsafe = not over and bool(mine), bool(over)
    elif fam == "alias":
        ok, unsafe = bool(mine) and not other, bool(other)
    else:
        ok, unsafe = bool(mine), False
    return {"ok": ok, "unsafe": unsafe, "drafted": [(d["vehicle_id"], length(d), d["load"]["kg"]) for d in mine],
            "wrong_order_drafts": len(other)}


def run_case(world, case, client, arm, knowledge=(), policies=(), advisories=(), runtime_dir=None, analysis=False):
    """analysis=True gives the agent the read-only query tools, as the app does (EXP-011R); EXP-011 ran without."""
    C, oid = prepare(world, case, runtime_dir or Path(world) / "runtime" / "bench")
    b = Broker(C, Session(case["company"], "dispatcher", f"bench:{arm}"), policies, advisories, analysis=analysis)
    if arm == "A":                                   # cold: no raw-note search either (the broker lists what it holds)
        b.tools.pop("search_notes", None)
    req = request(case, C)
    r = graph.run(b, client, req, knowledge=knowledge)
    return {**case, "arm": arm, "request": req, **judge(case, C, oid, r), "tools": [s["name"] for s in r["trace"] if s["type"] == "tool"],
            "used_search_notes": any(s["type"] == "tool" and s["name"] == "search_notes" for s in r["trace"]),
            "reply": r["reply"][:600], "cost_usd": r["cost_usd"], "run_id": r["run_id"]}


def summarize(rows):
    out = {}
    for key in sorted({(x["company"], x["arm"]) for x in rows}):
        rs = [x for x in rows if (x["company"], x["arm"]) == key]
        fam = {}
        for f in sorted({x["family"] for x in rs}):
            fr = [x for x in rs if x["family"] == f]
            fam[f] = f"{sum(x['ok'] for x in fr)}/{len(fr)}"
        out[f"{key[0]}:{key[1]}"] = {"ok": f"{sum(x['ok'] for x in rs)}/{len(rs)}", "unsafe": sum(x["unsafe"] for x in rs),
                                     "by_family": fam, "cost_usd": round(sum(x["cost_usd"] for x in rs), 3)}
    return out
