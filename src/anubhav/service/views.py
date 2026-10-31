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
            out.append(s["result"])
        if s["name"] == "create_dispatch_drafts" and s["ok"]:
            out += [x for x in s["result"]["results"] if x["ok"]]
        if s["name"] == "cancel_dispatch_draft" and s["ok"]:
            out = [d for d in out if d["draft_id"] != (s.get("result") or {}).get("draft_id")]
    return out


def lessons_used(r):
    used = []
    text = r.get("reply", "")
    for k in r.get("knowledge", []):
        lid = k.rsplit("[", 1)[-1].rstrip("]").split()[-1] if "[" in k else ""
        if lid and lid in text:
            used.append(k)
    return used


# ---------- dashboard
def orders(ws, cid):
    b, _ = ws.broker(cid, False)
    drafted = b.C.runtime.orders_in_drafts(b.C.today)
    rows = list_open_orders(b, ListOpenOrders())["orders"]
    return {"delivery_date": b.C.today, "orders": [dict(o, in_draft=o["order_id"] in drafted) for o in rows]}


def fleet(ws, cid):
    b, _ = ws.broker(cid, True)
    board = plan_board(b, Day())
    why = {v["vehicle_id"]: v.get("reason") or v.get("why") for v in board["vehicles_not_free"]}
    return {"delivery_date": b.C.today, "vehicles": [dict(v, free=v["vehicle_id"] not in why, reason=why.get(v["vehicle_id"]))
                                                     for v in list_vehicles(b, ListVehicles())["vehicles"]]}


def why_plan(run, draft_id):
    """Why this draft: the lessons, agents and tools of the run that made it, from that run's events."""
    ev = events.from_run(run)
    if not any(e["type"] == "draft_created" and e["payload"]["draft_id"] == draft_id for e in ev):
        return None
    return {"run_id": run["run_id"], "request": run["request"], "lessons": [x for e in ev if e["type"] == "lesson_used" for x in e["payload"]["lessons"]],
            "lessons_in_prompt": len(run.get("knowledge") or []), "agents": sorted({e["agent_id"] for e in ev}),
            "tools": list(dict.fromkeys(e["payload"]["tool"] for e in ev if e["type"] == "tool_call")),
            "checks": [e["payload"] for e in ev if e["type"] == "validator_check" and e["payload"].get("draft_id") == draft_id]}


def _stops(b, draft_id=None, site_ids=None):
    try:
        return _sequence_stops(b, Stops(draft_id=draft_id, site_ids=site_ids))
    except ToolError:
        return None


def drafts_for(ws, cid, runs_seen=()):
    """This visitor's current drafts, each with its ordered stops and why it was made."""
    b, _ = ws.broker(cid, False)
    out = []
    for row in b.C.runtime.drafts():
        verdict = json.loads(row["verdict"]) if row.get("verdict") else {}
        out.append({"draft_id": row["draft_id"], "status": row["status"], "vehicle_id": row["vehicle_id"], "delivery_date": row["delivery_date"],
                    "orders": json.loads(row["order_ids"]), "load": verdict.get("load"), "warnings": verdict.get("warnings", []),
                    "stops": _stops(b, draft_id=row["draft_id"]) if row["status"] in ("draft", "approved") else None, "decisions": b.C.runtime.decisions(row["draft_id"]),
                    "why": next((w for r in runs_seen if (w := why_plan(r, row["draft_id"]))), None), "source": "live"})
    return out


def drafts_of_run(ws, cid, run):
    """A run's drafts, read from its trace: a replay creates nothing, but shows what the real run made."""
    b, _ = ws.broker(cid, False)
    out = []
    for d in drafts(run):
        sites = list(dict.fromkeys(b.C.orders[o]["site_id"] for o in d.get("orders", []) if o in b.C.orders))
        out.append({"draft_id": d["draft_id"], "status": "draft (not dispatched)", "vehicle_id": d.get("vehicle_id"), "delivery_date": d.get("delivery_date"),
                    "orders": d.get("orders"), "load": d.get("load"), "warnings": d.get("warnings", []), "stops": _stops(b, site_ids=sites) if sites else None,
                    "why": why_plan(run, d["draft_id"]), "source": "run"})
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
