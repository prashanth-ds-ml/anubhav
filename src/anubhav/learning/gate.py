"""The evidence gate: deterministic checks of every proposed lesson against the company's full records.
Muse's confidence and wording never count. Outcomes:
  candidate       repeated, consistent evidence: the reviewer may approve it as advice or (if enforceable) a policy
  needs_evidence  a single piece of evidence: the reviewer may approve it as advice only
  rejected        contradicted, unsupported, too broad, a habit, or an unsupported kind
  expired         a time-bound fact whose evidence stopped (e.g. a closure that ended)
Thresholds are fixed here and pre-registered with each experiment that reports on them."""

import re
from collections import Counter
from datetime import date, timedelta

LONG_WAIT = 120          # minutes: a wait long enough to be caused by the site, not traffic
STALE_DAYS = 14          # a closure with no evidence for this long is over
ENFORCEABLE = {"site_access"}
SITE_KINDS = {"site_access", "receiving_hours", "night_only", "time_window", "moved_site"}


def _out(verdict, reason, support=0, counter=0, **extra):
    strength = {"candidate": "repeated", "needs_evidence": "single"}.get(verdict, verdict)
    return {"verdict": verdict, "reason": reason, "support": support, "counter": counter, "strength": strength, **extra}


def _level(support, counter, need=2):
    if counter:
        return "rejected"
    if support >= need:
        return "candidate"
    return "needs_evidence" if support == 1 else "rejected"


def _site(F, p):
    sid = p.get("site_id")
    if sid not in F.C.sites:
        return None
    return sid


def check(F, lesson):
    kind, p = lesson.get("kind"), lesson.get("params") or {}
    fn = CHECKS.get(kind)
    if not fn:
        return _out("rejected", f"kind '{kind}' is not supported by the gate; a person must handle it")
    try:
        res = fn(F, p)
    except (KeyError, TypeError, ValueError) as e:
        return _out("rejected", f"params invalid: {e}")
    res["enforceable"] = kind in ENFORCEABLE and res["verdict"] == "candidate"
    return res


def site_access(F, p):
    sid = _site(F, p)
    if not sid:
        return _out("rejected", "needs one existing site_id (a whole town is too broad)")
    mx = int(p["max_length_ft"])
    vs = F.by_site[sid]
    fails = [x for x in vs if x["status"] == "returned" and x["status_seen"] == "could_not_enter" and x["length_ft"] > mx]
    oks = [x for x in vs if x["status"] != "returned" and x["length_ft"] > mx]
    later_oks = [x for x in oks if fails and x["arrived"] > max(f["arrived"] for f in fails)]
    if fails and oks:
        return _out("rejected", f"contradicted: {len(fails)} refused but {len(oks)} delivered with vehicles over {mx} ft"
                    f"{' (incl. ' + str(len(later_oks)) + ' after the last refusal)' if later_oks else ''}",
                    len(fails), len(oks))
    v = _level(len(fails), 0)
    return _out(v, f"{len(fails)} refusal(s) of vehicles over {mx} ft, none delivered" if fails else "no refusal supports it",
                len(fails), 0, evidence=[f"{x['shipment_id']}#{x['stop']}" for x in fails])


def receiving_hours(F, p):
    sid = _site(F, p)
    if not sid:
        return _out("rejected", "needs one existing site_id")
    h = int(p["until_hour"])
    late = [x for x in F.by_site[sid] if x["hour"] >= h and x["status"] != "returned"]
    held = [x for x in late if x["wait_min"] >= 300]
    ok = [x for x in late if x["wait_min"] < 60]
    return _out(_level(len(held), len(ok)), f"{len(held)} arrivals at/after {h}:00 held overnight, {len(ok)} unloaded promptly",
                len(held), len(ok))


def night_only(F, p):
    sid = _site(F, p)
    if not sid:
        return _out("rejected", "needs one existing site_id")
    a, b = int(p.get("from_hour", 22)), int(p.get("to_hour", 6))
    day = [x for x in F.by_site[sid] if b <= x["hour"] < a and x["status"] != "returned"]
    held = [x for x in day if x["wait_min"] >= LONG_WAIT]
    ok = [x for x in day if x["wait_min"] < 60]
    return _out(_level(len(held), len(ok)), f"{len(held)} daytime arrivals waited for night, {len(ok)} unloaded by day",
                len(held), len(ok))


def time_window(F, p):
    sid = _site(F, p)
    if not sid:
        return _out("rejected", "needs one existing site_id")
    ln, a, b = int(p["min_length_ft"]), int(p["from_hour"]), int(p["to_hour"])
    inside = [x for x in F.by_site[sid] if x["length_ft"] >= ln and a <= x["hour"] < b and x["status"] != "returned"]
    held = [x for x in inside if x["wait_min"] >= 60]
    ok = [x for x in inside if x["wait_min"] < 30]
    return _out(_level(len(held), len(ok)), f"{len(held)} vehicles >= {ln} ft held during {a}:00-{b}:00, {len(ok)} not held",
                len(held), len(ok))


def weekly_off(F, p):
    wd = int(p["weekday"])
    if p.get("site_id"):
        sites = [p["site_id"]] if p["site_id"] in F.C.sites else []
    else:
        sites = [s for s, v in F.C.sites.items() if v["town"].lower() == str(p.get("town", "")).lower()]
    if not sites:
        return _out("rejected", "no matching site or town")
    vs = [x for s in sites for x in F.by_site[s] if x["weekday"] == wd]
    closed = [x for x in vs if x["status_seen"] == "shop_closed"]
    open_ = [x for x in vs if x["status"] != "returned"]
    if closed and open_ and not p.get("site_id"):
        return _out("rejected", f"too broad: {len(closed)} closed but {len(open_)} sites in the town received that weekday; "
                    "narrow it to the sites that were closed", len(closed), len(open_))
    return _out(_level(len(closed), len(open_)), f"{len(closed)} visits found it closed, {len(open_)} delivered that weekday",
                len(closed), len(open_))


def alias(F, p):
    phrase, kind, target = str(p["phrase"]).strip().lower(), p["target_kind"], str(p["target_id"])
    if len(phrase) < 3:
        return _out("rejected", "phrase too short")
    msgs = [m for m in F.messages if phrase in m["text"].lower() and m.get("shipment_id") in F.ships]

    def hit(m):
        sid = m["shipment_id"]
        if kind == "site":
            return target in F.stops[sid].values()
        vehs = F.ship_vehicles(sid)
        if kind == "vehicle":
            return target in vehs
        return any(F.C.vehicles.get(v, {}).get("vendor") == target for v in vehs)
    good = sum(map(hit, msgs))
    if kind == "site" and target not in F.C.sites or kind == "vehicle" and target not in F.C.vehicles:
        return _out("rejected", f"unknown target {target}")
    if kind == "site":
        names = {w for w in re.findall(r"[a-z]+", F.C.sites[target]["name"].lower())}
        if set(phrase.split()) <= names:
            return _out("rejected", "the phrase is just the site's own name")
    return _out(_level(good, len(msgs) - good), f"{good} of {len(msgs)} messages using it point to {target}", good, len(msgs) - good)


def real_capacity(F, p):
    vid, mx = p["vehicle_id"], float(p["max_kg"])
    if vid not in F.C.vehicles:
        return _out("rejected", "unknown vehicle")
    off, ok = 0, 0
    for s in F.ships.values():
        if s["vehicle_id"] != vid:
            continue
        evs = F.events[s["shipment_id"]]
        o = next((e for e in evs if e["kind"] == "weighbridge_offload"), None)
        loaded = next((e.get("kg") for e in evs if e["kind"] == "loaded"), None) or 0
        planned = loaded + (o.get("kg") or 0 if o else 0)
        if o and planned > mx:
            off += 1
        elif not o and loaded > mx * 1.02:
            ok += 1
    return _out(_level(off, ok), f"{off} loads above {mx:.0f} kg offloaded at the weighbridge, {ok} carried without offload",
                off, ok)


def vendor_reliability(F, p):
    vendor = p["vendor"]
    c = Counter()
    for ps in F.placements.values():
        for x in ps:
            if x["vendor"] != vendor:
                continue
            d = date.fromisoformat(x["confirmed_at"][:10])
            rush = (d + timedelta(days=9)).month != d.month
            c[(rush, x["status"] == "no_show")] += 1
    rn, rt = c[(True, True)], c[(True, True)] + c[(True, False)]
    nn, nt = c[(False, True)], c[(False, True)] + c[(False, False)]
    if not rt:
        return _out("rejected", "no month-end bookings")
    rate_r, rate_n = rn / rt, nn / max(1, nt)
    ok = rn >= 3 and rate_r >= 2 * max(rate_n, 0.01)
    return _out("candidate" if ok else "rejected", f"month-end no-shows {rn}/{rt} ({rate_r:.0%}) vs other days {nn}/{nt} ({rate_n:.0%})",
                rn, nn)


def closure(F, p):
    town = str(p["town"]).lower()
    rows = sorted(e["ts"][:10] for sid, evs in F.events.items() for e in evs if e["kind"] == "delay" and e.get("cause_seen") == "closure"
                  and any(F.C.sites.get(s, {}).get("town", "").lower() == town for s in F.stops[sid].values()))
    if len(rows) < 3:
        return _out("rejected", f"only {len(rows)} closure delays near {p['town']}")
    last = date.fromisoformat(rows[-1])
    today = date.fromisoformat(F.today)
    valid = {"valid_from": rows[0], "valid_to": rows[-1]}
    if (today - last).days > STALE_DAYS:
        return _out("expired", f"{len(rows)} closure delays from {rows[0]} to {rows[-1]}; none for {(today - last).days} days",
                    len(rows), 0, **valid)
    return _out("candidate", f"{len(rows)} closure delays from {rows[0]} to {rows[-1]}", len(rows), 0, **valid)


def moved_site(F, p):
    sid = _site(F, p)
    if not sid:
        return _out("rejected", "needs one existing site_id")
    n = sum(1 for s, evs in F.events.items() for e in evs if e["kind"] == "delay" and e.get("cause_seen") == "address"
            and F.stops[s].get(e.get("stop_seq")) == sid)
    return _out(_level(n, 0), f"{n} trips delayed going to the old address", n, 0)


def vehicle_requirement(F, p):
    """Only a real constraint if smaller vehicles actually failed there; otherwise it's a habit."""
    cls = p["vehicle_class"]
    sites = [p["site_id"]] if p.get("site_id") else [s for s, v in F.C.sites.items() if v["town"].lower() == str(p.get("town", "")).lower()]
    vs = [x for s in sites for x in F.by_site[s] if x["vehicle_class"] != cls]
    fails = [x for x in vs if x["status"] == "returned"]
    if not fails:
        return _out("rejected", f"habit, not a rule: {len(vs)} trips with other vehicle classes, none failed", 0, len(vs))
    return _out("needs_evidence", f"{len(fails)} failures with other classes", len(fails), len(vs) - len(fails))


CHECKS = {"site_access": site_access, "receiving_hours": receiving_hours, "night_only": night_only,
          "time_window": time_window, "weekly_off": weekly_off, "alias": alias, "real_capacity": real_capacity,
          "vendor_reliability": vendor_reliability, "closure": closure, "moved_site": moved_site,
          "vehicle_requirement": vehicle_requirement}
