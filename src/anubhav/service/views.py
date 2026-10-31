"""Read models: a saved run turned into something a person can read. No framework, works for live runs and replays."""

import json


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
