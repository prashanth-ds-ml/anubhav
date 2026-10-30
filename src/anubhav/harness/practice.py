"""Tool practice: the agent answers practice questions generated from a company's own data, and is scored on
whether it looked things up, whether its answer matches the records, and (for evaluation only) whether it used
a fitting tool. Failures feed Loop A; held-out questions show whether a patch generalizes.

The question TYPES below are a curriculum (generic operational questions); entities and numbers come from each
company's data at run time. The expected-tool sets and answer checks are an evaluation oracle: they are never shown
to the agent or to the patch proposer. The proposer only sees what went wrong (no lookup, wrong answer, tool error)."""

import random
import re
from collections import Counter

from ..agent import graph
from ..runtime.broker import REGISTRY, Broker, Session

MONTHS = {"08": ("August", "ఆగస్టు"), "09": ("September", "సెప్టెంబర్"), "10": ("October", "అక్టోబర్")}

TYPES = {
    "sites_in_town": {"tools": {"list_sites", "find_site"}, "q": {
        "en": "List all our sites in {town}.", "rt": "{town} lo mana sites anni list cheyyi.",
        "te": "{town} లో మన సైట్లు అన్నీ లిస్ట్ చెయ్యి."}},
    "towns_served": {"tools": {"list_sites"}, "q": {
        "en": "Which towns do we deliver to?", "rt": "Manam ae ae oorlaki saruku pampistham?",
        "te": "మనం ఏ ఏ ఊర్లకి సరుకు పంపిస్తాం?"}},
    "trips_in_month": {"tools": {"trip_history"}, "q": {
        "en": "How many delivery stops did we make in {town} in {month_en}?",
        "rt": "{month_en} lo {town} lo manam enni deliveries chesam?",
        "te": "{month_te} లో {town} లో మనం ఎన్ని డెలివరీలు చేశాం?"}},
    "returned_at_site": {"tools": {"trip_history"}, "q": {
        "en": "How many deliveries to {site} came back (returned) so far?",
        "rt": "{site} ki ippativaraku enni deliveries venakki vachayi?",
        "te": "{site} కి ఇప్పటివరకు ఎన్ని డెలివరీలు వెనక్కి వచ్చాయి?"}},
    "open_orders_town": {"tools": {"list_open_orders"}, "q": {
        "en": "How many orders are open for tomorrow in {town}?", "rt": "Repu {town} ki enni orders pending lo unnayi?",
        "te": "రేపు {town} కి ఎన్ని ఆర్డర్లు పెండింగ్ లో ఉన్నాయి?"}},
    "orders_in_month": {"tools": {"order_history"}, "q": {
        "en": "How many orders did {site} place for delivery in {month_en}?",
        "rt": "{month_en} lo {site} nunchi enni orders vachayi?",
        "te": "{month_te} లో {site} నుండి ఎన్ని ఆర్డర్లు వచ్చాయి?"}},
}


# Gap questions (D-040, C6): no built tool answers these directly; the agent needs run_query or a tool it learned.
# Kept apart from TYPES so the frozen EXP-010 practice set is unchanged.
GAP_TYPES = {
    "worst_ontime_weekday": {"q": {
        "en": "Which weekday had the worst on-time deliveries in {month_en}?",
        "rt": "{month_en} lo ae weekday lo on-time deliveries worst ga unnayi?",
        "te": "{month_te} లో ఏ వారం రోజున సమయానికి డెలివరీలు అతి తక్కువగా జరిగాయి?"}},
    "busiest_weekday_town": {"q": {
        "en": "On which weekday do we make the most delivery stops in {town}?",
        "rt": "{town} lo ae weekday lo manam ekkuva deliveries chestham?",
        "te": "{town} లో ఏ వారం రోజున మనం ఎక్కువ డెలివరీలు చేస్తాం?"}},
    "returned_cases_town_month": {"q": {
        "en": "How many cases came back (returned cases) from {town} in {month_en}?",
        "rt": "{month_en} lo {town} nunchi enni cases venakki vachayi?",
        "te": "{month_te} లో {town} నుండి ఎన్ని కేసులు వెనక్కి వచ్చాయి?"}},
    "damaged_cases_month": {"q": {
        "en": "How many cases were damaged in delivery in {month_en}?",
        "rt": "{month_en} lo delivery lo enni cases damage ayyayi?",
        "te": "{month_te} లో డెలివరీలో ఎన్ని కేసులు పాడయ్యాయి?"}},
}
# Evaluation oracle only (never shown to the agent): how a weekday may be written in a reply.
WEEKDAY_NAMES = [("monday", "somavaram", "సోమవారం"), ("tuesday", "mangalavaram", "మంగళవారం"),
                 ("wednesday", "budhavaram", "బుధవారం"), ("thursday", "guruvaram", "గురువారం"),
                 ("friday", "shukravaram", "sukravaram", "శుక్రవారం"), ("saturday", "shanivaram", "sanivaram", "శనివారం"),
                 ("sunday", "aadivaram", "adivaram", "ఆదివారం")]


def _first_weekday(text):
    low, best = (text or "").lower(), None
    for i, names in enumerate(WEEKDAY_NAMES):
        pos = [low.find(n) for n in names if low.find(n) >= 0]
        if pos and (best is None or min(pos) < best[1]):
            best = (i, min(pos))
    return best[0] if best else None


def build_gaps(C, seed=7, per_type=3, split="dev"):
    """Gap questions with answers computed from the records (the same on-time rule as the performance tool)."""
    from collections import defaultdict
    from datetime import date
    r = random.Random(f"{seed}:gap:{C.company}")
    towns = sorted({s["town"] for s in C.sites.values()})
    r.shuffle(towns)
    my_towns = towns[:len(towns) // 2] if split == "dev" else towns[len(towns) // 2:]
    ships = {s["shipment_id"]: s for s in C.t.get("shipments", [])}
    orders_of = defaultdict(set)
    for i in C.t.get("shipment_items", []):
        orders_of[i["shipment_id"]].add(i["order_id"])
    outcomes = C.t.get("trip_outcomes", [])
    out, langs, n = [], ["rt", "te", "en"], 0

    def add(qtype, check, **kw):
        nonlocal n
        lang = langs[n % 3]
        n += 1
        out.append({"id": f"{C.company}-gap-{split}-{n:02d}", "company": C.company, "split": split, "type": qtype,
                    "lang": lang, "gap": True, "question": GAP_TYPES[qtype]["q"][lang].format(**kw), "check": check})

    def unique_extreme(counts, worst):
        if not counts:
            return None
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=not worst)
        return ranked[0][0] if len(ranked) == 1 or ranked[0][1] != ranked[1][1] else None

    months = ("09", "08") if split == "dev" else ("10",)        # company-wide questions: held out by month
    for mm in months:
        timed = defaultdict(lambda: [0, 0])
        for o in outcomes:
            sh = ships.get(o["shipment_id"], {})
            day = (o.get("arrived_at") or sh.get("delivery_date") or "")[:10]
            ends = [C.orders[i]["window_end"] for i in orders_of[o["shipment_id"]] if i in C.orders and C.orders[i]["site_id"] == o["site_id"]]
            if day[5:7] == mm and ends and o.get("arrived_at"):
                wd = date.fromisoformat(day).weekday()
                timed[wd][0] += 1
                timed[wd][1] += o["arrived_at"][11:16] <= max(ends)
        wd = unique_extreme({k: round(100 * v[1] / v[0], 1) for k, v in timed.items() if v[0] >= 5}, worst=True)
        if wd is not None:
            add("worst_ontime_weekday", {"weekday": wd}, month_en=MONTHS[mm][0], month_te=MONTHS[mm][1])
    for town in my_towns:
        per_day = Counter(date.fromisoformat(o["arrived_at"][:10]).weekday() for o in outcomes
                          if o.get("arrived_at") and C.sites.get(o["site_id"], {}).get("town") == town)
        wd = unique_extreme(per_day, worst=False)
        if wd is not None and sum(per_day.values()) >= 10 and sum(q["type"] == "busiest_weekday_town" for q in out) < per_type:
            add("busiest_weekday_town", {"weekday": wd}, town=town)
    for town in my_towns:
        for mm in ("09", "08", "10"):
            cases = sum(o.get("returned_cases") or 0 for o in outcomes
                        if (o.get("arrived_at") or "")[5:7] == mm and C.sites.get(o["site_id"], {}).get("town") == town)
            if cases >= 5 and sum(q["type"] == "returned_cases_town_month" for q in out) < per_type:
                add("returned_cases_town_month", {"number": cases}, town=town, month_en=MONTHS[mm][0], month_te=MONTHS[mm][1])
    for mm in months:
        cases = sum(o.get("damaged_cases") or 0 for o in outcomes if (o.get("arrived_at") or "")[5:7] == mm)
        if cases:
            add("damaged_cases_month", {"number": cases}, month_en=MONTHS[mm][0], month_te=MONTHS[mm][1])
    return out


def _numbers(text):
    """Numbers that could be an answer: dates, times, ids and list markers are removed first."""
    t = text or ""
    t = re.sub(r"\d{4}-\d{2}-\d{2}", " ", t)                    # dates
    t = re.sub(r"\b\d{1,2}:\d{2}\b", " ", t)                    # times
    t = re.sub(r"\b[A-Z][A-Z0-9]*-[A-Z0-9-]*\d+\b", " ", t)        # ids like T01-O00879, DFS-T006
    t = re.sub(r"(?m)^\s*\d+[.)]\s", " ", t)                     # list markers
    return {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", t)}


def build(C, seed=7, per_type=4, split="dev"):
    """Questions with checkable answers from the company's records. dev and held-out use different towns/sites."""
    r = random.Random(f"{seed}:{C.company}")
    sites = list(C.sites.values())
    towns = sorted({s["town"] for s in sites})
    r.shuffle(towns)
    half = len(towns) // 2
    my_towns = towns[:half] if split == "dev" else towns[half:]
    my_sites = [s for s in sites if s["town"] in my_towns]
    outcomes = C.t.get("trip_outcomes", [])
    out, langs = [], ["rt", "te", "en"]
    n = 0

    def add(qtype, check, **kw):
        nonlocal n
        lang = langs[n % 3]
        n += 1
        out.append({"id": f"{C.company}-{split}-{n:02d}", "company": C.company, "split": split, "type": qtype, "lang": lang,
                    "question": TYPES[qtype]["q"][lang].format(**kw), "check": check})

    for town in my_towns[:per_type]:
        names = [s["name"] for s in sites if s["town"] == town]
        add("sites_in_town", {"names_any": names, "min_share": 0.6}, town=town)
    if split == "dev":           # one fixed question: practice only, never held out (it would leak)
        add("towns_served", {"names_any": sorted({s["town"] for s in sites}), "min_share": 0.6})
    for town in my_towns:
        for mm in ("09", "08"):
            cnt = sum(1 for o in outcomes if C.sites.get(o["site_id"], {}).get("town") == town and o["arrived_at"][5:7] == mm)
            if cnt >= 3 and sum(q["type"] == "trips_in_month" for q in out) < per_type:
                add("trips_in_month", {"number": cnt}, town=town, month_en=MONTHS[mm][0], month_te=MONTHS[mm][1])
    returned = Counter(o["site_id"] for o in outcomes if o["status"] == "returned")
    for s in [s for s in my_sites if returned.get(s["site_id"])][:per_type]:
        add("returned_at_site", {"number": returned[s["site_id"]]}, site=f"{s['name']}, {s['town']}")
    open_by_town = Counter(C.sites[o["site_id"]]["town"] for o in C.orders.values() if o["status"] == "open")
    for town in [t for t in my_towns if open_by_town.get(t)][:per_type]:
        add("open_orders_town", {"number": open_by_town[town]}, town=town)
    for s in my_sites:
        cnt = sum(1 for o in C.orders.values() if o["site_id"] == s["site_id"] and o["delivery_date"][5:7] == "09")
        if cnt >= 2 and sum(q["type"] == "orders_in_month" for q in out) < per_type:
            add("orders_in_month", {"number": cnt}, site=f"{s['name']}, {s['town']}", month_en=MONTHS["09"][0], month_te=MONTHS["09"][1])
    return out


def score(q, r):
    steps = [s for s in r["trace"] if s["type"] == "tool"]
    called = [s["name"] for s in steps]
    reply = r["reply"] or ""
    c = q["check"]
    if "weekday" in c:
        ok = _first_weekday(reply) == c["weekday"]
    elif "number" in c:
        ok = c["number"] in _numbers(reply)
    else:
        names = c["names_any"]
        ok = sum(n.lower() in reply.lower() for n in names) >= max(1, round(c["min_share"] * len(names)))
    builtin = {t.name for t in REGISTRY}
    fitting = ({"run_query"} | {n for n in called if n not in builtin and n != "describe_tables"}) if q.get("gap")         else TYPES[q["type"]]["tools"]
    return {"used_tool": bool(called), "right_tool": bool(set(called) & fitting),
            "tool_errors": sum(not s["ok"] for s in steps), "answer_ok": ok, "tools": called,
            "cost_usd": r["cost_usd"], "reply": reply, "run_id": r["run_id"]}


def run(C, client, questions, harness=None, analysis=False, learned_tools=()):
    results = []
    for q in questions:
        b = Broker(C, Session(C.company, "dispatcher", "practice"), analysis=analysis, learned_tools=learned_tools)
        r = graph.run(b, client, q["question"], harness=harness)
        results.append({**q, **score(q, r)})
    return results


def summary(results):
    n = len(results) or 1
    return {"questions": len(results), "answer_ok": round(sum(x["answer_ok"] for x in results) / n, 3),
            "right_tool": round(sum(x["right_tool"] for x in results) / n, 3),
            "no_lookup": round(sum(not x["used_tool"] for x in results) / n, 3),
            "tool_errors": sum(x["tool_errors"] for x in results), "cost_usd": round(sum(x["cost_usd"] for x in results), 4)}


def failures_for_proposer(results):
    """What the proposer may see: the question, what the agent did, and what went wrong. Never the expected tool."""
    out = []
    for x in results:
        if x["answer_ok"] and x["used_tool"] and not x["tool_errors"]:
            continue
        why = "answered without looking anything up" if not x["used_tool"] else \
              ("a tool call failed" if x["tool_errors"] else "the answer did not match the company's records")
        out.append({"question": x["question"], "tools_called": x["tools"], "what_went_wrong": why,
                    "reply_excerpt": x["reply"][:300]})
    return out


def gate(base, cand, base_regress, cand_regress):
    """Code decides on held-out questions: answers must improve, nothing may get worse on the regression requests."""
    reasons = []
    if cand["answer_ok"] <= base["answer_ok"]:
        reasons.append(f"held-out answers did not improve ({base['answer_ok']:.0%} → {cand['answer_ok']:.0%})")
    if cand["tool_errors"] > base["tool_errors"]:
        reasons.append(f"more tool errors ({base['tool_errors']} → {cand['tool_errors']})")
    lost = [k for k, d in base_regress.items() if d and not cand_regress.get(k)]
    if lost:
        reasons.append(f"lost drafts on {len(lost)} regression request(s)")
    if base["cost_usd"] and cand["cost_usd"] > 1.5 * base["cost_usd"]:
        reasons.append(f"cost +{cand['cost_usd'] / base['cost_usd'] - 1:.0%}")
    return {"pass": not reasons, "reasons": reasons}
