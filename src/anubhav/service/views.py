"""Read models: a saved run turned into something a person can read, and the dashboard's views. No framework; works for
live runs and replays. Dashboard reads call the tools' own code directly, so opening a page doesn't fill the audit log."""

import json

from .. import events
from ..agents.team import Stops, _sequence_stops
from ..learning import profile
from ..runtime.broker import Day, ListOpenOrders, ToolError, get_transport_policy, list_open_orders, list_vehicles, plan_board, NoArgs, ListVehicles
from ..trace import walk


def tool_steps(r):
    return [s for s in r["trace"] if s["type"] == "tool"]


def args_of(step):
    a = step["arguments"]
    return json.loads(a) if isinstance(a, str) else (a or {})


def summarize(step):
    """One readable line per tool result."""
    if not step["ok"]:
        return f"✗ {step['error']['code']}: {step['error']['message'][:120]}"
    res = step.get("result") or {}
    name = step["name"]
    if name == "find_site":
        m = res.get("matches", [])
        return ", ".join(f"{x['name']} ({x['town']})" for x in m[:3]) or "no match"
    if name == "list_open_orders":
        return f"{len(res.get('orders', []))} open orders"
    if name == "list_vehicles":
        return f"{len(res.get('vehicles', []))} vehicles"
    if name == "get_site_constraints":
        extra = ""
        if res.get("approved_policies"):
            extra = " · approved rule: " + "; ".join(p["rule"] for p in res["approved_policies"])
        if res.get("advisories"):
            extra += " · advice: " + "; ".join(a["text"] for a in res["advisories"])
        return f"site master: {res.get('recorded_in_site_master')}{extra}"
    if name == "create_dispatch_draft":
        return f"draft {res.get('draft_id')} · {res.get('vehicle_id')} · {res.get('load', {}).get('kg')} kg"
    if name == "check_vehicle_availability":
        return "free" if res.get("available") else f"not free ({res.get('status')}, held={res.get('held_by_draft')})"
    if name == "get_route_info":
        return f"{res.get('road_km_from_depot')} km · ~{res.get('drive_minutes')} min"
    return json.dumps(res, ensure_ascii=False, default=str)[:140]


def drafts(r):
    """Drafts created in a run, read from its trace (works for live runs and replays alike)."""
    out = []
    for s in tool_steps(r):
        if s["name"] == "create_dispatch_draft" and s["ok"]:
            out.append(_one_shape(s["result"]))
        if s["name"] == "create_dispatch_drafts" and s["ok"]:
            # the several-drafts tool names the orders order_ids and keeps the date once, for all of them
            out += [_one_shape(x, s["result"].get("delivery_date")) for x in s["result"]["results"] if x.get("ok")]
        if s["name"] == "cancel_dispatch_draft" and s["ok"]:
            out = [d for d in out if d["draft_id"] != (s.get("result") or {}).get("draft_id")]
    return out


def _one_shape(d, date=None):
    """One draft, the same fields whichever tool made it (and when a retry returned the earlier draft)."""
    d = dict(d)
    d["orders"] = list(d.get("orders") or d.get("order_ids") or [])
    d.setdefault("delivery_date", date)
    d["warnings"] = list(d.get("warnings") or [])
    return d


def lessons_used(r):
    used = []
    text = r.get("reply", "")
    for k in r.get("knowledge", []):
        lid = k.rsplit("[", 1)[-1].rstrip("]").split()[-1] if "[" in k else ""
        if lid and lid in text:
            used.append(k)
    return used


# ---------- dashboard
def orders(ws, cid, day=None):
    """Open orders for one delivery day (today by default), and every day from today on that has open orders."""
    b, _ = ws.broker(cid, False)
    d = day if day and day >= b.C.today else b.C.today
    drafted = b.C.runtime.orders_in_drafts(d)
    rows = list_open_orders(b, ListOpenOrders(delivery_date=d))["orders"]
    days = {}
    for o in b.C.orders.values():
        if o.get("status") == "open" and (o.get("delivery_date") or "") >= b.C.today:
            days[o["delivery_date"]] = days.get(o["delivery_date"], 0) + 1
    return {"delivery_date": d, "today": b.C.today, "days": [{"date": k, "open": n} for k, n in sorted(days.items())],
            "orders": [dict(o, in_draft=o["order_id"] in drafted) for o in rows]}


def fleet(ws, cid):
    b, _ = ws.broker(cid, True)
    board = plan_board(b, Day())
    why = {v["vehicle_id"]: v.get("reason") or v.get("why") for v in board["vehicles_not_free"]}
    return {"delivery_date": b.C.today, "vehicles": [dict(v, free=v["vehicle_id"] not in why, reason=why.get(v["vehicle_id"]))
                                                     for v in list_vehicles(b, ListVehicles())["vehicles"]]}


def _results(run):
    for r in walk(run):
        for s in r.get("trace", []):
            if isinstance(s.get("result"), (dict, list)):
                yield s["result"]


def _find(o, test):
    """Every dict inside a tool result that passes test."""
    if isinstance(o, dict):
        if test(o):
            yield o
        for v in o.values():
            yield from _find(v, test)
    elif isinstance(o, list):
        for v in o:
            yield from _find(v, test)


def _key(lesson):
    """Lessons arrive as text or as small objects: one hashable key for either."""
    return lesson if isinstance(lesson, str) else json.dumps(lesson, sort_keys=True, ensure_ascii=False)


def _lesson_sites(run):
    """Which site each site-scoped lesson came with: tools like plan_board return every site's advice, so a lesson
    seen during a run is not necessarily about the sites a draft serves."""
    out = {}
    for res in _results(run):
        for d in _find(res, lambda d: d.get("site_id") and any(d.get(k) for k in events.LESSON_KEYS)):
            for k in events.LESSON_KEYS:
                for x in d.get(k) or []:
                    out.setdefault(_key(x), set()).add(d["site_id"])
    return out


def _draft_sites(run, draft_id):
    for res in _results(run):
        for d in _find(res, lambda d: d.get("draft_id") == draft_id and isinstance(d.get("load"), dict)):
            return set(d["load"].get("sites") or [])
    return None


def why_plan(run, draft_id):
    """Why this draft: the lessons, agents and tools of the run that made it, from that run's events. A lesson tied to
    a site is listed only when the draft serves that site."""
    ev = events.from_run(run)
    if not any(e["type"] == "draft_created" and e["payload"]["draft_id"] == draft_id for e in ev):
        return None
    seen = list({_key(x): x for e in ev if e["type"] == "lesson_used" for x in e["payload"]["lessons"]}.items())
    scoped, sites = _lesson_sites(run), _draft_sites(run, draft_id)
    lessons = [x for k, x in seen if sites is None or k not in scoped or scoped[k] & sites]
    return {"run_id": run["run_id"], "request": run["request"], "lessons": lessons,
            "lessons_in_prompt": len(run.get("knowledge") or []), "agents": sorted({e["agent_id"] for e in ev}),
            "tools": list(dict.fromkeys(e["payload"]["tool"] for e in ev if e["type"] == "tool_call")),
            "checks": [e["payload"] for e in ev if e["type"] == "validator_check" and e["payload"].get("draft_id") == draft_id]}


def _stops(b, draft_id=None, site_ids=None):
    try:
        return _sequence_stops(b, Stops(draft_id=draft_id, site_ids=site_ids))
    except ToolError:
        return None


def _site_names(b, site_ids):
    """The sites a draft serves, by name and town, in the order the draft lists them."""
    return [f"{b.C.sites[s]['name']}, {b.C.sites[s]['town']}" for s in site_ids or [] if s in b.C.sites]


def drafts_for(ws, cid, runs_seen=()):
    """Every draft in this visitor's workspace, whatever its status (draft, approved, rejected, cancelled), each with its
    ordered stops and why it was made. Newest delivery date first, then newest made first, so the list keeps every plan
    a person still has to act on, across requests."""
    b, _ = ws.broker(cid, False)
    made = {d["draft_id"]: r for r in runs_seen for d in drafts(r)}
    out = []
    for row in b.C.runtime.drafts():
        verdict = json.loads(row["verdict"]) if row.get("verdict") else {}
        made_by = made.get(row["draft_id"])
        load = verdict.get("load") or {}
        stops = _stops(b, draft_id=row["draft_id"]) if row["status"] in ("draft", "approved") else None
        out.append({"draft_id": row["draft_id"], "run_id": made_by and made_by["run_id"], "model": made_by and made_by.get("model"), "status": row["status"], "vehicle_id": row["vehicle_id"], "delivery_date": row["delivery_date"],
                    "created_at": row.get("created_at"), "orders": json.loads(row["order_ids"]), "load": verdict.get("load"), "warnings": verdict.get("warnings", []),
                    "sites": [f"{s['name']}, {s['town']}" for s in stops["stops"]] if stops else _site_names(b, load.get("sites")),
                    "stops": stops, "decisions": b.C.runtime.decisions(row["draft_id"]),
                    "why": why_plan(made_by, row["draft_id"]) if made_by else None, "source": "live"})
    out.sort(key=lambda d: (d["created_at"] or "", d["draft_id"]), reverse=True)
    out.sort(key=lambda d: d["delivery_date"] or "", reverse=True)       # stable: newest made first within a date
    return out


def drafts_of_run(ws, cid, run):
    """A run's drafts, read from its trace: a replay creates nothing, but shows what the real run made. A draft this
    visitor's own live run made is in their workspace too: it comes back with its real status, so a person can decide it."""
    b, _ = ws.broker(cid, False)
    out = []
    for d in drafts(run):
        row = b.C.runtime.draft(d["draft_id"])
        if row:                                  # the stored draft is the record: prefer it over the trace
            d = {**d, "orders": json.loads(row["order_ids"]) if row.get("order_ids") else d["orders"],
                 "vehicle_id": row.get("vehicle_id") or d.get("vehicle_id"), "delivery_date": row.get("delivery_date") or d.get("delivery_date")}
        sites = list(dict.fromkeys(b.C.orders[o]["site_id"] for o in d["orders"] if o in b.C.orders))
        out.append({"draft_id": d["draft_id"], "run_id": run["run_id"], "model": run.get("model"), "status": row["status"] if row else "draft (not dispatched)", "vehicle_id": d.get("vehicle_id"),
                    "delivery_date": d.get("delivery_date"), "created_at": row["created_at"] if row else None, "orders": d.get("orders"), "load": d.get("load"),
                    "warnings": d.get("warnings", []), "sites": _site_names(b, sites),
                    "stops": _stops(b, site_ids=sites) if sites else None, "why": why_plan(run, d["draft_id"]),
                    **({"decisions": b.C.runtime.decisions(d["draft_id"])} if row else {}), "source": "live" if row else "run"})
    return out


def company_profile(ws, cid):
    b, _ = ws.broker(cid, False)
    S = ws.store()
    saved = profile.latest(S, cid)
    return {"company": cid, "facts": saved["facts"] if saved else profile.from_records(b.C), "owner": saved["owner"] if saved else {},
            "owner_fields": profile.OWNER_FIELDS, "agent_reads": profile.render(saved) if saved else "", "version": saved["version"] if saved else None,
            "versions": [{k: v[k] for k in ("version", "ts", "actor", "owner")} for v in profile.versions(S, cid)],
            "written_rules": get_transport_policy(b, NoArgs())["policies"]}


def team_parts(run):
    """How many agents and tool calls a saved request really took, teammates included."""
    parts = list(walk(run))
    return {"agents": [p.get("agent_id") or "planner" for p in parts], "tool_calls": sum(p.get("tool_calls", 0) for p in parts)}
