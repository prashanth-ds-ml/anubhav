"""What each agent knows, kept apart (design v1 §4.3), all counted from what is already recorded: no model involved.
Planner: approved lessons. Analyst: query shapes that worked, with values removed. Tool Forge: names a person approved or
rejected. Lesson Miner: how the evidence gate and reviewers treated earlier proposals."""

from collections import Counter

from ..learning import newtools as nt
from ..runtime.query import sandbox
from . import runs as run_store

MAX_ITEMS = 6


def analyst(ws, cid):
    """Read-only query shapes that answered 2+ different requests. Hints, not rules: the sandbox still checks every query."""
    groups = nt.groups(run_store.recent_runs(500, ws), cid, sandbox(ws.company(cid)))
    return [f"A query shape that answered {len(g['requests'])} requests: {g['template'][:400]}" for g in groups if len(g["requests"]) >= 2][:MAX_ITEMS]


def tool_forge(ws, cid):
    out = []
    for t in nt.tools(ws.store(), cid):
        if t["status"] in ("active", "retired"):
            out.append(f"A person approved the tool name {t['name']}.")
        elif t["status"] == "rejected":
            out.append(f"A person rejected the tool name {t['name']}" + (f": {t['note'][:120]}" if t.get("note") else "."))
    return out[-MAX_ITEMS:]


def lesson_miner(ws, cid):
    lessons = ws.store().list(cid)
    if not lessons:
        return []
    states = Counter(l["state"] for l in lessons)
    out = ["Earlier proposals here: " + ", ".join(f"{n} {s}" for s, n in states.most_common()) + "."]
    out += [f"Refused or rejected ({l['kind']}): {l['gate']['reason'][:160]}" for l in lessons if l["state"] in ("REJECTED", "NEEDS_EVIDENCE")][:MAX_ITEMS - 1]
    return out


BUILDERS = {"analyst": analyst, "tool_forge": tool_forge, "lesson_miner": lesson_miner}


def for_team(ws, cid):
    return {agent: fn(ws, cid) for agent, fn in BUILDERS.items()}


def sizes(ws, cid):
    """How many items each agent knows, for the roster."""
    return {"planner": len(ws.knowledge_for(cid)[0]), **{agent: len(items) for agent, items in for_team(ws, cid).items()}}
