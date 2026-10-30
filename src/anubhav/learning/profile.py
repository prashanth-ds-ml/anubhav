"""Onboarding: what the business is (D-041, slimmed by D-042). The profile is computed by code from the company's own
records (where it delivers, for whom, with what fleet, how much, what goods, in which languages, on which days), and the
owner may add what the records can't show (industry, what they move, priorities, key customers). Saved per company
with versions in the lesson store, and given to the agent as a short block labelled as data, never as instructions.
Nothing here is written from knowledge of the generated world: every fact is counted from the records."""

import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime

OWNER_FIELDS = {"industry": "Industry", "what_we_move": "What we move, and for whom",
                "priorities": "What matters most (cost, on-time, fill…)", "key_customers": "Customers that must never be late",
                "notes": "Anything else the agent should know"}
MAX_FIELD = 200
MAX_BLOCK = 600
MARKUP = set('{}[]<>`"|#*\\')
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _top(counter, n=3):
    return [k for k, _ in counter.most_common(n)]


def from_records(C):
    """Facts counted from the records. Each fact names the table it came from."""
    t = C.t
    orders = t.get("orders", [])
    days = sorted({o["delivery_date"] for o in orders if o.get("delivery_date")})
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 if days else 0
    towns = Counter(s["town"] for s in t.get("sites", []))
    fleet = Counter(v["class"] for v in t.get("vehicles", []))
    owners = Counter("own" if v["owner"] == "own" else "hired" for v in t.get("vehicles", []))
    by_sku = {p["sku"]: p for p in t.get("products", [])}
    goods, brands = Counter(), Counter()
    for i in t.get("order_items", []):
        p = by_sku.get(i.get("sku"))
        if p:
            goods[p["handling_class"]] += i.get("ordered_cases") or 0
            brands[p["brand"]] += i.get("ordered_cases") or 0
    total = sum(goods.values()) or 1
    langs = Counter(m.get("lang") for m in t.get("planner_messages", []) if m.get("lang"))
    week = Counter(WEEKDAYS[date.fromisoformat(o["delivery_date"]).weekday()] for o in orders if o.get("delivery_date"))
    return {
        "service_area": {"sites": len(t.get("sites", [])), "towns": len(towns), "most_sites_in": _top(towns),
                         "source": "sites"},
        "clients": {"brands": len(brands), "largest": _top(brands), "source": "order_items + products"},
        "fleet": {"vehicles": sum(fleet.values()), "own": owners["own"], "hired": owners["hired"],
                  "classes": dict(fleet.most_common()), "hired_from_vendors": len(t.get("vendors", [])),
                  "source": "vehicles, vendors"},
        "volume": {"orders": len(orders), "days": span, "orders_per_day": round(len(orders) / span, 1) if span else 0,
                   "trips": len(t.get("shipments", [])), "source": "orders, shipments"},
        "goods": {"by_share": {k: round(100 * v / total) for k, v in goods.most_common()}, "source": "order_items + products"},
        "planner_languages": {"by_share": {k: round(100 * v / (sum(langs.values()) or 1)) for k, v in langs.most_common()},
                              "source": "planner_messages"},
        "busiest_days": {"top": _top(week, 2), "quietest": week.most_common()[-1][0] if week else None, "source": "orders"},
        "written_policies": {"count": len(t.get("written_policies", [])), "source": "written_policies"},
    }


def clean(text):
    """Owner text is short plain text: no control characters or markup, at most MAX_FIELD characters."""
    s = "".join(" " if unicodedata.category(ch)[0] in "CZ" or ch in MARKUP else ch for ch in str(text or ""))
    return re.sub(r"\s+", " ", s).strip()[:MAX_FIELD]


def _con(store):
    con = store._con()
    con.execute("create table if not exists profiles (company text, version int, ts text, actor text, facts text, owner text, "
                "primary key (company, version))")
    return con


def save(store, C, actor, owner=None):
    """A new version: fresh facts from the records plus the owner's fields (cleaned). Returns the saved profile."""
    owner = {k: clean(v) for k, v in (owner or {}).items() if k in OWNER_FIELDS and clean(v)}
    facts = from_records(C)
    with _con(store) as con:
        v = (con.execute("select max(version) from profiles where company = ?", (C.company,)).fetchone()[0] or 0) + 1
        con.execute("insert into profiles values (?,?,?,?,?,?)", (C.company, v, datetime.now().isoformat(timespec="seconds"),
                    actor, json.dumps(facts, ensure_ascii=False), json.dumps(owner, ensure_ascii=False)))
    return latest(store, C.company)


def versions(store, company):
    with _con(store) as con:
        rows = con.execute("select * from profiles where company = ? order by version desc", (company,)).fetchall()
    return [dict(r) | {"facts": json.loads(r["facts"]), "owner": json.loads(r["owner"])} for r in rows]


def latest(store, company):
    v = versions(store, company)
    return v[0] if v else None


def render(p):
    """The block the agent reads: at most MAX_BLOCK characters, labelled as data from the records and the owner."""
    if not p:
        return ""
    f, o = p["facts"], p["owner"]
    parts = [f"{f['service_area']['sites']} customer sites in {f['service_area']['towns']} towns "
             f"(most in {', '.join(f['service_area']['most_sites_in'])})",
             f"{f['fleet']['vehicles']} vehicles ({f['fleet']['own']} own, {f['fleet']['hired']} hired)",
             f"about {f['volume']['orders_per_day']} orders a day for {f['clients']['brands']} client brands",
             "goods: " + ", ".join(f"{k} {v}%" for k, v in list(f["goods"]["by_share"].items())[:3]),
             f"busiest days {', '.join(f['busiest_days']['top'])}"]
    text = "From its records: " + "; ".join(parts) + "."
    if o:
        text += " The owner says: " + "; ".join(f"{OWNER_FIELDS[k].split(' (')[0].lower()}: {v}" for k, v in o.items()) + "."
    return text[:MAX_BLOCK]
