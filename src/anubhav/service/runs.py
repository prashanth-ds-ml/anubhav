"""Running a request and finding saved runs: replay matching, the live run (single Planner or team), recent runs."""

import json

from .. import muse, trace
from ..agent import graph
from ..agents import team as team_mode
from ..runtime.broker import Session
from . import knowledge as agent_knowledge
from .session import DEMO, SUGGESTIONS, Workspace, harness_store


def trace_files():
    return sorted(trace.TRACE_DIR.glob("*.jsonl"), reverse=True) + ([DEMO / "replay_runs.jsonl"] if (DEMO / "replay_runs.jsonl").exists() else [])


def visible(r, ws=None):
    """Hosted, a visitor sees the saved demo runs and their own live runs, never another visitor's."""
    return not (ws and ws.public) or r.get("visitor") in (None, ws.sid)


def recent_runs(limit=60, ws=None):
    rows = []
    for p in trace_files():
        rows += [r for r in (json.loads(x) for x in reversed(p.read_text(encoding="utf-8").splitlines()) if x.strip()) if visible(r, ws)]
        if len(rows) >= limit:
            break
    return rows[:limit]


def find_run(run_id, ws=None):
    """A saved run by id: local traces, then the demo bundle."""
    for p in trace_files():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r["run_id"] == run_id:
                    return r if visible(r, ws) else None
    return None


def find_replay(ws: Workspace, cid, request, use_lessons, learned=None):
    """The newest saved real run with the same company, request and knowledge setting (local traces, then the demo
    bundle). If the visitor has approved learned tools (or not), a run made the same way is preferred."""
    learned = ws.has_learned_tools(cid) if learned is None else learned
    fallback = None
    for p in trace_files():
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            if r["company"] == cid and r["request"].strip() == request.strip() and bool(r.get("knowledge")) == use_lessons and visible(r, ws):
                if bool(r.get("learned_tools")) == learned:
                    return r
                fallback = fallback or r
    return fallback


def replayable(ws: Workspace, cid, use_lessons):
    return [label for label, req in SUGGESTIONS.items() if find_replay(ws, cid, req, use_lessons, learned=False)
            or find_replay(ws, cid, req, use_lessons, learned=True)]


def history_turns(history):
    """The last few exchanges, so follow-ups make sense."""
    turns = []
    for h in list(history)[-6:]:
        turns += [{"role": "user", "content": h["request"]}, {"role": "assistant", "content": h["run"]["reply"]}]
    return turns


def run_with(ws: Workspace, client, cid, request, use_lessons, history=(), team=False, harness=None, hooks=None, run_id=None):
    """One request with a given model client, saved with its events. Single Planner, or the team (D-044). The caller has
    already passed the spend guard."""
    harness = harness_store().active()["surfaces"] if harness is None else harness
    turns = history_turns(history)
    label = f"ui:{cid}:{'lessons' if use_lessons else 'cold'}" + (":team" if team else "")
    if team:
        knowledge, policies, advisories, lessons, learned = ws.broker_args(cid, use_lessons)
        r = team_mode.run(ws.company(cid), Session(cid, "dispatcher", "demo"), client, request, knowledge=knowledge,
                          harness=harness, about=ws.about(cid), history=turns, policies=policies, advisories=advisories,
                          lessons=lessons, learned_tools=learned, hooks=hooks, run_id=run_id, harnesses=harness_store().active_all(),
                          knowledge_by_agent=agent_knowledge.for_team(ws, cid), lesson_store=ws.store())
        r["learned_tools"] = [t["name"] for t in learned]
    else:
        b, knowledge = ws.broker(cid, use_lessons)
        r = graph.run(b, client, request, knowledge=knowledge, harness=harness, history=turns, about=ws.about(cid), hooks=hooks, run_id=run_id)
        r["learned_tools"] = [t.name for t in b.list_tools() if t.category == "learned_tools"]
    if ws.public:
        r["visitor"] = ws.sid
    trace.save(r, label=label)
    return r


def run_live(ws: Workspace, cid, request, model_key, use_lessons, history=(), team=False):
    client, blocked = ws.live_client(model_key)
    if blocked:
        raise muse.MissingKeyError(blocked)
    return run_with(ws, client, cid, request, use_lessons, history, team)
