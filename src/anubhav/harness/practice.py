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
from ..runtime.broker import Broker, Session

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
    if "number" in c:
        ok = c["number"] in _numbers(reply)
    else:
        names = c["names_any"]
        ok = sum(n.lower() in reply.lower() for n in names) >= max(1, round(c["min_share"] * len(names)))
    return {"used_tool": bool(called), "right_tool": bool(set(called) & TYPES[q["type"]]["tools"]),
            "tool_errors": sum(not s["ok"] for s in steps), "answer_ok": ok, "tools": called,
            "cost_usd": r["cost_usd"], "reply": reply, "run_id": r["run_id"]}


def run(C, client, questions, harness=None):
    results = []
    for q in questions:
        b = Broker(C, Session(C.company, "dispatcher", "practice"))
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
