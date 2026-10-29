"""When could the agent have known? Replays a company's history day by day and re-runs the same evidence gate on
only the records that existed by each day. No model calls: the lessons are the ones Muse proposed; the dates come
from the data. Also counts how many more incidents happened after a lesson became knowable."""

from datetime import date, timedelta

from . import gate
from .digest import Facts


def days(start, end, step=1):
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=step)


def curve(C, lessons, start, end, step=1):
    """For each lesson: first day it was supported by one observation (advice) and by repeated evidence (rule-ready)."""
    todo = {l["lesson_id"]: l for l in lessons if l["kind"] in gate.CHECKS}
    out = {lid: {"lesson_id": lid, "kind": l["kind"], "claim": l["claim"], "first_seen": None, "learnable": None,
                 "support_then": None} for lid, l in todo.items()}
    for d in days(start, end, step):
        F = Facts(C, until=d)
        for lid, l in todo.items():
            row = out[lid]
            if row["learnable"]:
                continue
            g = gate.check(F, {"kind": l["kind"], "params": l["params"]})
            if g["verdict"] in ("needs_evidence", "candidate", "expired") and not row["first_seen"]:
                row["first_seen"] = d
            if g["verdict"] in ("candidate", "expired"):
                row["learnable"], row["support_then"] = d, g["support"]
    final = Facts(C)
    for lid, l in todo.items():
        g = gate.check(final, {"kind": l["kind"], "params": l["params"]})
        row = out[lid]
        row["support_final"] = g["support"]
        row["incidents_after"] = (g["support"] - row["support_then"]) if row["support_then"] is not None else None
    return sorted(out.values(), key=lambda r: (r["learnable"] or "9999", r["lesson_id"]))
