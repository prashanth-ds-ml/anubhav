"""The data behind a lesson, for the Learning page's charts: read from the company's own records through the same
facts view the evidence gate uses (learning.digest.Facts), so a judge sees exactly what the gate checked.
Nothing about the world is written here: the lesson's own parameters say which site or town to look at."""

from collections import Counter
from datetime import date, timedelta

from ..learning.digest import Facts

SITE_KINDS = {"site_access", "night_only", "receiving_hours", "weekly_off", "time_window"}


def _monday(d: str) -> str:
    x = date.fromisoformat(d[:10])
    return (x - timedelta(days=x.weekday())).isoformat()


def _weeks(first: str, last: str):
    a, b = date.fromisoformat(_monday(first)), date.fromisoformat(_monday(last))
    while a <= b:
        yield a.isoformat()
        a += timedelta(days=7)


def lesson_evidence(C, lesson) -> dict:
    """{kind: trips | closure | imported | none, ...}. C is the lesson's company (CompanyData)."""
    kind, p = lesson.get("kind"), lesson.get("params") or {}
    if str(lesson.get("source") or "").startswith("pack:"):
        # A shared lesson's evidence is the other company's records, and those never leave that company.
        return {"kind": "imported", "lesson_kind": kind, "source": lesson["source"],
                "note": "This lesson came in a shared regional pack. Its evidence is another company's records, which are not shared."}
    F = Facts(C)
    if kind in SITE_KINDS and p.get("site_id") in C.sites:
        s = C.sites[p["site_id"]]
        rows = sorted(({"date": x["date"], "hour": x["hour"], "weekday": x["weekday"], "vehicle_id": x["vehicle_id"],
                        "vehicle_class": x["vehicle_class"], "length_ft": x["length_ft"], "status": x["status"],
                        "status_seen": x["status_seen"], "wait_min": x["wait_min"]} for x in F.by_site[p["site_id"]]),
                      key=lambda r: (r["date"], r["hour"]))
        limit = {k: p[k] for k in ("max_length_ft", "from_hour", "to_hour", "until_hour", "weekday") if k in p}
        return {"kind": "trips", "lesson_kind": kind, "site": {"site_id": s["site_id"], "name": s.get("name"), "town": s.get("town")},
                "limit": limit, "window": {"from": min((r["date"] for r in rows), default=None), "to": F.today}, "rows": rows}
    if kind == "closure" and p.get("town"):
        town = str(p["town"]).lower()
        # The same selection the gate makes: closure delays on shipments that stop in the town.
        hits = [(sid, e) for sid, evs in F.events.items() for e in evs
                if e["kind"] == "delay" and e.get("cause_seen") == "closure"
                and any(C.sites.get(s, {}).get("town", "").lower() == town for s in F.stops[sid].values())]
        by_week = Counter(_monday(e["ts"]) for _, e in hits)
        first = min([e["ts"][:10] for _, e in hits] + [p.get("valid_from") or F.today])
        weeks = [{"week": w, "delays": by_week.get(w, 0)} for w in _weeks(first, F.today)]
        # Drivers' notes from the same trip and stop as a closure delay: linked by the records, not by matching words.
        delayed = {(sid, e.get("stop_seq")) for sid, e in hits}
        notes = sorted(({"ts": n["ts"], "lang": n.get("lang"), "source": n.get("source"), "text": n["text"]}
                        for n in C.t.get("driver_notes", []) if (n["shipment_id"], n.get("stop_seq")) in delayed), key=lambda n: n["ts"])
        return {"kind": "closure", "lesson_kind": kind, "place": p["town"], "what": p.get("what"),
                "window": {"from": p.get("valid_from") or lesson.get("valid_from"), "to": p.get("valid_to") or lesson.get("valid_to")},
                "today": F.today, "delays": len(hits), "weeks": weeks, "notes": notes}
    return {"kind": "none", "lesson_kind": kind}
