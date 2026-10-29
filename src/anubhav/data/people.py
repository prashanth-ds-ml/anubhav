"""Step 8: people. Daily small staff edits (2-6 a day; some wrong, some reversed) and feedback/complaints.
Runs after the trips on its own random stream, so it can't change what happened on the road."""

from collections import defaultdict
from datetime import datetime, timedelta

from .config import rng
from .simulate import at, daterange, iso

# cause -> (field, right value, wrong value, how a person would write it)
SITE_FIELD = {"site_access": ("max_vehicle_length_ft", 22, 32, lambda v: f"{v} ft"),
              "receiving_hours": ("receiving_until_hour", 18, 20, lambda v: f"{v}:00"),
              "night_only": ("night_only", True, False, lambda v: "night only (22:00-06:00)" if v else "any time"),
              "weekly_off": ("weekly_off", 1, None, lambda v: "Tuesday" if v == 1 else "none"),
              "time_window": ("day_entry_restricted", True, False, lambda v: "no big trucks 09:00-20:00" if v else "none"),
              "moved_godown": ("address", "new godown", "old address", str)}
CONTACTS = ["Srinivas", "Ravi", "Prasad", "Murali", "Kishore", "Anil", "Venu", "Raghu", "Sathish", "Mohan"]
LANDMARKS = ["near bus stand", "opposite SBI", "behind market yard", "near railway gate", "beside petrol bunk",
             "near temple arch", "next to rice mill"]
REMARKS = ["call before coming", "unload at back side", "munim available after 10", "no unloading during lunch",
           "send invoice copy on WhatsApp"]


def run(W, t, start, end):
    cfg = W.cfg
    for e in t["staff_edits"]:            # edits made during re-plans in the simulation
        if "edit_id" not in e:
            t["_edit_seq"].append(1)
            e.update(edit_id=f"{e['company']}-E{len(t['_edit_seq']):05d}", scope="this_shipment", reverts=None)
    for cid, c in W.companies.items():
        if c.get("history", True) is False:
            continue
        outcomes = defaultdict(list)
        for o in t["trip_outcomes"]:
            if o["company"] == cid:
                outcomes[o["arrived_at"][:10]].append(o)
        for d in daterange(start, end):
            r = rng(cfg, "people", cid, d)
            day = d.isoformat()
            edits = [e for e in t["staff_edits"] if e["company"] == cid and e["ts"][:10] == day]
            user = lambda: r.choice(c["planners"])["name"]
            # learning-relevant edits after a problem at a site (mostly local fixes, rarely the master record)
            for o in outcomes.get(day, []):
                if o["true_cause"] in SITE_FIELD and r.random() < 0.35:
                    field, right, wrong, show = SITE_FIELD[o["true_cause"]]
                    correct = r.random() < 0.7
                    scope = "this_order"         # fixed for this order only: the rule stays in people's heads
                    when = datetime.fromisoformat(o["arrived_at"]) + timedelta(hours=r.randint(1, 20))
                    e = _edit(t, cid, when, user(), "site", o["site_id"], field, show(wrong if correct else right),
                              show(right if correct else wrong), o["true_cause"], correct, scope)
                    edits.append(e)
                    if scope == "master" and correct and field in W.site(cid, o["site_id"])["known"]:
                        W.site(cid, o["site_id"])["known"][field] = right
            # vendor reliability marks after no-shows
            for p in t["vehicle_placements"]:
                if p["company"] == cid and p["confirmed_at"][:10] == day and p["status"] == "no_show" and r.random() < 0.3:
                    edits.append(_edit(t, cid, at(d, 20, 10), user(), "vendor", p["vendor"], "reliability_note", "",
                                       "bandi pettaledu", "vendor_no_show", True, "master"))
            # everyday noise edits up to the day's target
            target = r.randint(2, 6) if d.weekday() != 6 else r.randint(0, 2)
            my_sites = [x for x in W.sites if x["company"] == cid]
            while len(edits) < target:
                s = r.choice(my_sites)
                kind = r.choice(["phone", "contact_person", "landmark", "remarks"])
                old, new = {"phone": (s["phone"], f"9{r.randint(100000000, 999999999)}"),
                            "contact_person": (r.choice(CONTACTS), r.choice(CONTACTS)),
                            "landmark": ("", r.choice(LANDMARKS)), "remarks": ("", r.choice(REMARKS))}[kind]
                why = {"phone": "number changed", "contact_person": "new munim", "landmark": "driver could not find",
                       "remarks": "distributor asked"}[kind]
                edits.append(_edit(t, cid, at(d, r.randint(9, 19), r.choice([0, 15, 30, 45])), user(), "site", s["site_id"],
                                   kind, old, new, why, True, "master"))
            # ~10% reversed the next morning
            for e in list(edits):
                if r.random() < 0.10 and e["entity"] != "shipment":
                    _edit(t, cid, at(d + timedelta(days=1), 9, r.randint(0, 50)), user(), e["entity"], e["entity_id"],
                          e["field"], e["new"], e["old"], "reverted", True, e.get("scope", "master"), reverts=e["edit_id"])
            _feedback(t, W, cid, d, r, outcomes.get(day, []))
    return t


def _edit(t, cid, ts, user, entity, eid, field, old, new, reason, correct, scope, reverts=None):
    t["_edit_seq"].append(1)
    row = {"company": cid, "edit_id": f"{cid}-E{len(t['_edit_seq']):05d}", "ts": iso(ts), "user": user, "entity": entity,
           "entity_id": eid, "field": field, "old": str(old), "new": str(new), "reason_code": reason, "scope": scope,
           "reverts": reverts, "correct": correct}
    t["staff_edits"].append(row)
    return row


def _feedback(t, W, cid, d, r, outs):
    for o in outs:
        if o["wait_min"] >= 180 and r.random() < 0.5:
            t["feedback"].append({"company": cid, "ts": iso(datetime.fromisoformat(o["arrived_at"]) + timedelta(minutes=30)),
                                  "source": "driver", "kind": "long_wait", "site_id": o["site_id"],
                                  "shipment_id": o["shipment_id"], "hours": round(o["wait_min"] / 60, 1)})
        if o.get("damaged_cases") and r.random() < 0.6:
            t["feedback"].append({"company": cid, "ts": iso(datetime.fromisoformat(o["arrived_at"]) + timedelta(hours=3)),
                                  "source": "distributor", "kind": "damage", "site_id": o["site_id"],
                                  "shipment_id": o["shipment_id"], "cases": o["damaged_cases"]})
        if o["status"] == "returned" and r.random() < 0.4:
            t["feedback"].append({"company": cid, "ts": iso(datetime.fromisoformat(o["arrived_at"]) + timedelta(hours=2)),
                                  "source": "distributor", "kind": "not_received", "site_id": o["site_id"],
                                  "shipment_id": o["shipment_id"]})
    if r.random() < 0.3:
        s = r.choice([x for x in W.sites if x["company"] == cid])
        t["feedback"].append({"company": cid, "ts": iso(at(d, r.randint(10, 18))), "source": "distributor",
                              "kind": r.choice(["late", "rate_query", "short_supply"]), "site_id": s["site_id"],
                              "shipment_id": None, "hours": r.randint(1, 4)})
