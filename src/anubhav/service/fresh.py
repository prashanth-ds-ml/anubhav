"""Start from nothing (final demo plan, Nov 3): a visitor empties their own lessons, tools and drafts, asks a question,
lets Muse Spark 1.3 learn from the company's records, approves what the evidence gate passed, and asks again.

Only this visitor's workspace changes. The agents' versions are shared and read-only here (changing them stays local).
The lessons a visitor mines are theirs; the measured results used the EXP-008/009b lessons, and the app says so."""

from __future__ import annotations

from ..learning import digest, miner, newtools
from ..learning.store import describe
from ..agents import registry

MINES_PER_VISIT = 1          # live mining on a public host, per company; each also counts as one live run


def display(les, C) -> str:
    """A lesson in full, for people: the godown by name, its kind of site and town, the truck by type and size. The
    agent never reads this (it reads store.describe, the wording every result was measured with)."""
    p, k = les.get("params") or {}, les.get("kind")
    site = C.sites.get(p.get("site_id") or (p.get("target_id") if p.get("target_kind") == "site" else "") or "", {})
    where = (f"{site['name']} ({site.get('type', 'site').replace('_', ' ')}, {site.get('town')} · site {site['site_id']})" if site else "")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def truck(vid):
        v = C.vehicles.get(vid or "", {})
        return f"{vid}, the {v['length_ft']} ft {v['class']} truck ({int(v['payload_kg']):,} kg)" if v else f"vehicle {vid}"

    def hour(h):
        try:
            h = int(h)
        except (TypeError, ValueError):
            return str(h)
        return f"{12 if h % 12 == 0 else h % 12} {'am' if h < 12 else 'pm'}"

    if k == "site_access" and where:
        return f"{where}: no truck longer than {p.get('max_length_ft')} ft gets in"
    if k == "night_only" and where:
        return f"{where}: receives only at night, {hour(p.get('from_hour'))} to {hour(p.get('to_hour'))}"
    if k == "receiving_hours" and where:
        return f"{where}: does not receive after {hour(p.get('until_hour'))}"
    if k == "weekly_off" and (where or p.get("town")):
        return f"{where or p.get('town')}: closed every {days[int(p.get('weekday', 0)) % 7]}"
    if k == "alias":
        phrase = f"“{p.get('phrase')}”"
        if p.get("target_kind") == "site" and where:
            return f"{phrase} means {where}"
        if p.get("target_kind") == "vehicle":
            return f"{phrase} means {truck(p.get('target_id'))}"
        return f"{phrase} means trucks from {p.get('target_id')}"
    if k == "real_capacity":
        v = C.vehicles.get(p.get("vehicle_id") or "", {})
        paper = f" (paper payload {int(v['payload_kg']):,} kg)" if v else ""
        return f"{p.get('vehicle_id')}{paper} safely carries at most {int(p.get('max_kg') or 0):,} kg"
    return describe(les, C)


def lesson_view(les, C) -> dict:
    return {"lesson_id": les["lesson_id"], "kind": les["kind"], "state": les["state"], "display": display(les, C), "what": describe(les, C),
            "reason": (les.get("gate") or {}).get("reason", ""), "enforceable": (les.get("gate") or {}).get("enforceable"),
            "valid_from": les.get("valid_from"), "valid_to": les.get("valid_to")}


def status(ws, cid) -> dict:
    """What this visitor's workspace has learned right now, and the agents' versions."""
    from .session import harness_store
    S = ws.store()
    rows = S.list(cid)
    H = harness_store()
    agents = {a.agent_id: H.active(a.agent_id)["version_id"] for a in registry.load().agents.values()}
    as_number = lambda v: int(v.rsplit("-", 1)[-1]) + 1 if v and v.rsplit("-", 1)[-1].isdigit() else 1
    return {"fresh": bool(ws.state.get("fresh", {}).get(cid)),
            # rejected, expired and retired entries are kept for the record but are not something it knows
            "lessons": sum(r["state"] not in ("REJECTED", "EXPIRED", "RETIRED") for r in rows), "active_lessons": sum(r["state"].startswith("ACTIVE") for r in rows),
            "waiting_lessons": sum(r["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED") for r in rows),
            "tools": len(newtools.tools(S, cid, "active")), "agent_versions": {a: as_number(v) for a, v in agents.items()},
            "mined_here": bool(ws.state.get("mined", {}).get(cid)), "mines_left": mines_left(ws, cid)}


def _set(ws, mode) -> None:
    from .session import COMPANIES
    ws.state["mode"] = mode
    ws.state["fresh"] = {c: mode == "fresh" for c in COMPANIES}
    if mode == "fresh" and not ws.state.get("fresh_since"):
        ws.state["fresh_since"] = _now()


def start_all(ws) -> None:
    """A new visitor on the hosted demo opens on Fresh start: its own empty lesson store, no tools, no drafts."""
    _set(ws, "fresh")
    ws.store()
    _remember(ws)


def set_mode(ws, cid, mode) -> dict:
    """Switch the active workspace. Nothing is emptied or reloaded: each keeps its lessons, tools, drafts and runs."""
    _set(ws, "fresh" if mode == "fresh" else "learned")
    ws.store()
    _remember(ws)
    return status(ws, cid)


def reset(ws, cid) -> dict:
    """Empty Fresh start (its lessons, tools, drafts, conversation and runs list) and make it the active workspace.
    After learning is not touched."""
    from .session import COMPANIES
    _set(ws, "fresh")
    ws.store()
    ws.clear_lessons()
    for c in COMPANIES:
        ws.company(c).runtime.reset()
    (ws.state.get("conversation") or {}).pop("fresh", None)
    ws.state["fresh_since"] = _now()                       # runs before this leave the Fresh start lists
    _remember(ws)
    return status(ws, cid)


def _now():
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _mark(ws):
    from .session import state_root
    return state_root(ws.world) / "learning" / "sessions" / f"{ws.sid}.mode.json"


def _remember(ws) -> None:
    """Keep the workspace's mode beside its lesson store, so a server restart doesn't turn a "Fresh start" workspace
    into "After learning" with its lessons emptied (the in-memory state is lost on a restart; the files are not)."""
    import json
    if not ws.public:
        return
    try:
        _mark(ws).parent.mkdir(parents=True, exist_ok=True)
        _mark(ws).write_text(json.dumps({"mode": ws.mode, "fresh_since": ws.state.get("fresh_since")}), encoding="utf-8")
    except OSError:
        pass


def recall(ws) -> None:
    """A visitor whose files are on disk but whose state this server lost: bring back the saved mode."""
    import json
    try:
        saved = json.loads(_mark(ws).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if saved.get("fresh_since"):
        ws.state["fresh_since"] = saved["fresh_since"]
    mode = saved.get("mode") or ("fresh" if any((saved.get("fresh") or {}).values()) else "learned")
    _set(ws, mode)


def start_fresh(ws, cid) -> dict:
    """Start from nothing (scenario S0): Fresh start, emptied. The records and After learning are untouched."""
    return reset(ws, cid)


def restore(ws, cid) -> dict:
    """Switch to After learning: the lessons the recorded runs and the measured results used, plus anything done there."""
    return set_mode(ws, cid, "learned")


def records(ws, cid) -> dict:
    """Stage 1, no model: what the miner will read, counted from the company's own records."""
    C = ws.company(cid)
    t = C.t
    days = sorted({(r.get("arrived_at") or "")[:10] for r in t.get("trip_outcomes", []) if r.get("arrived_at")})
    langs = {}
    for n in t.get("driver_notes", []):
        langs[n.get("lang", "?")] = langs.get(n.get("lang", "?"), 0) + 1
    return {"trips": len(t.get("shipments", [])), "stops": len(t.get("trip_outcomes", [])), "drivers_notes": len(t.get("driver_notes", [])),
            "notes_by_language": langs, "planner_messages": len(t.get("planner_messages", [])), "sites": len(C.sites), "vehicles": len(C.vehicles),
            "from": days[0] if days else None, "to": days[-1] if days else None, "days": len(days)}


def mines_left(ws, cid) -> int | None:
    if not ws.public:
        return None
    return max(0, MINES_PER_VISIT - int(ws.state.get("mined", {}).get(cid, 0)))


def learn(ws, cid, model="spark") -> tuple[dict | None, str | None]:
    """Stage 2: the chosen model (Muse Spark 1.3 by default) reads the digest and proposes rules; the evidence gate checks each against the full
    records. Returns (result, None) or (None, why not). Counts as one live run, and once per visit when hosted."""
    if ws.public and mines_left(ws, cid) == 0:
        return None, "This visit has already learned from the records once. Start fresh again in a new visit, or run it locally."
    client, blocked = ws.live_client(model)
    if blocked:
        return None, blocked
    C = ws.company(cid)
    F, d = digest.build(C)
    props, meta = miner.mine(client, C, d)
    ids = ws.store().add_proposals(cid, F, props, meta)
    ws.state.setdefault("mined", {})[cid] = int(ws.state.get("mined", {}).get(cid, 0)) + 1
    rows = [ws.store().get(i) for i in ids]
    order = {"CANDIDATE": 0, "NEEDS_EVIDENCE": 1, "CHALLENGED": 2, "EXPIRED": 3, "REJECTED": 4}
    rows.sort(key=lambda r: order.get(r["state"], 9))
    return {"model": meta.get("model"), "cost_usd": round(meta.get("cost_usd", 0), 4), "latency_s": meta.get("latency_s"),
            "lessons": [lesson_view(r, C) for r in rows],
            "counts": {s: sum(r["state"] == s for r in rows) for s in ("CANDIDATE", "NEEDS_EVIDENCE", "REJECTED", "EXPIRED")}}, None
