"""Running a request and finding saved runs: replay matching, the live run (single Planner or team), recent runs."""

import json

from .. import muse, trace
from ..agent import graph
from ..agents import team as team_mode
from ..runtime.broker import Session
from ..runtime.company import LIVE_DRAFT
from . import checkpoints
from . import knowledge as agent_knowledge
from .session import DEMO, SUGGESTIONS, Workspace, harness_store


DEMO_RUNS = DEMO / "replay_runs.jsonl"


def trace_files():
    return sorted(trace.TRACE_DIR.glob("*.jsonl"), reverse=True) + ([DEMO_RUNS] if DEMO_RUNS.exists() else [])


def visible(r, ws=None, path=None):
    """Hosted, a visitor sees the saved demo runs and their own live runs, never another visitor's. Local traces made
    without a visitor (development runs on the host's own machine) are not demo runs, so a visitor doesn't see them."""
    return not (ws and ws.public) or path == DEMO_RUNS or (r.get("visitor") is not None and r.get("visitor") == ws.sid)


def fresh_since(ws):
    """When this "Fresh start" workspace was started or reset, or None when it is the "After learning" one."""
    return ws.state.get("fresh_since") if ws is not None and ws.public and any(ws.state.get("fresh", {}).values()) else None


def in_workspace(r, ws, path):
    """In a "Fresh start" workspace the lists and counts hold only this visitor's runs since it was started or reset;
    the recorded runs belong to the "After learning" workspace. A recorded run can still be replayed by id."""
    since = fresh_since(ws)
    return since is None or (path != DEMO_RUNS and (r.get("saved_at") or "") >= since)


def since_start(rows, ws, key="ts"):
    """Shared records (agent versions, feedback) in a "Fresh start" workspace: only those made since it started."""
    since = fresh_since(ws)
    return list(rows) if since is None else [x for x in rows if (x.get(key) or "") >= since]


def own_pairs(ws, cid, limit=3):
    """This workspace's own before-and-after pairs, newest first: a run of a request without lessons, and a later run of
    the same request with at least one approved lesson in its prompt. Recorded runs and continued runs don't count."""
    rows = [r for r in recent_runs(500, ws) if r["company"] == cid and not r.get("recorded") and not r.get("resumed_from")
            and not str(r.get("label", "")).endswith(":mine") and (r.get("request") or "").strip()]
    rows = sorted(reversed(rows), key=lambda r: r.get("saved_at") or "")      # oldest first; same second keeps saving order
    pairs, used = [], set()
    for i in range(len(rows) - 1, -1, -1):
        after, req = rows[i], rows[i]["request"].strip()
        if not after.get("knowledge") or req in used:
            continue
        before = next((r for r in reversed(rows[:i]) if r["request"].strip() == req and not r.get("knowledge")), None)
        if before:
            used.add(req)
            pairs.append((before, after))
            if len(pairs) >= limit:
                break
    return pairs


def recent_runs(limit=60, ws=None):
    rows = []
    for p in trace_files():
        rows += [{**r, "recorded": p == DEMO_RUNS} for r in (json.loads(x) for x in reversed(p.read_text(encoding="utf-8").splitlines()) if x.strip())
                 if visible(r, ws, p) and in_workspace(r, ws, p)]
        if len(rows) >= limit:
            break
    return rows[:limit]


def find_run(run_id, ws=None):
    """A saved run by id: local traces, then the demo bundle."""
    for p in trace_files():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r["run_id"] == run_id and visible(r, ws, p):     # a demo run also has a local copy where it was recorded
                    return r
    return None


def find_replay(ws: Workspace, cid, request, use_lessons, learned=None, team=False):
    """The newest saved real run with the same company, request and knowledge setting (local traces, then the demo
    bundle). A run made the same way is preferred: same learned tools first, then single Planner or team."""
    learned = ws.has_learned_tools(cid) if learned is None else learned
    best, rank = None, -1
    for p in trace_files():
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            if r["company"] == cid and r["request"].strip() == request.strip() and bool(r.get("knowledge")) == use_lessons and visible(r, ws, p):
                same_tools, same_mode = bool(r.get("learned_tools")) == learned, (r.get("mode") == "team") == team
                score = 2 * same_tools + same_mode
                if score == 3:
                    return r
                if score > rank:
                    best, rank = r, score
    return best


def replayable(ws: Workspace, cid, use_lessons):
    return [label for label, req in SUGGESTIONS.items() if find_replay(ws, cid, req, use_lessons, learned=False)
            or find_replay(ws, cid, req, use_lessons, learned=True)]


def history_turns(history):
    """The last few exchanges, so follow-ups make sense."""
    turns = []
    for h in list(history)[-6:]:
        turns += [{"role": "user", "content": h["request"]}, {"role": "assistant", "content": h["run"]["reply"]}]
    return turns


def run_with(ws: Workspace, client, cid, request, use_lessons, history=(), team=False, harness=None, hooks=None, run_id=None, resume=None):
    """One request with a given model client, saved with its events. Single Planner, or the team (D-044). The caller has
    already passed the spend guard. `resume` ({run_id, state} of an earlier run) continues it, with `request` as the person's
    reply. These runs are supervised: their checks stop for a person (agent/graph.py)."""
    state = None
    if resume:          # a draft cancelled or rejected since is no longer this run's to re-check
        state = {**resume["state"], "drafts": [d for d in resume["state"]["drafts"]
                                               if (row := ws.company(cid).runtime.draft(d)) and row["status"] in LIVE_DRAFT]}
    harness = harness_store().active()["surfaces"] if harness is None else harness
    turns = history_turns(history)
    label = f"ui:{cid}:{'lessons' if use_lessons else 'cold'}" + (":team" if team else "")
    if team:
        knowledge, policies, advisories, lessons, learned = ws.broker_args(cid, use_lessons)
        r = team_mode.run(ws.company(cid), Session(cid, "dispatcher", "demo"), client, request, knowledge=knowledge,
                          harness=harness, about=ws.about(cid), history=turns, policies=policies, advisories=advisories,
                          lessons=lessons, learned_tools=learned, hooks=hooks, run_id=run_id, harnesses=harness_store().active_all(),
                          knowledge_by_agent=agent_knowledge.for_team(ws, cid), lesson_store=ws.store(), supervised=True, resume=state)
        r["learned_tools"] = [t["name"] for t in learned]
    else:
        b, knowledge = ws.broker(cid, use_lessons)
        r = graph.run(b, client, request, knowledge=knowledge, harness=harness, history=turns, about=ws.about(cid), hooks=hooks, run_id=run_id, supervised=True, resume=state)
        r["learned_tools"] = [t.name for t in b.list_tools() if t.category == "learned_tools"]
    if ws.public:
        r["visitor"] = ws.sid
    if resume:
        r["resumed_from"] = resume["run_id"]
    state = r.pop("checkpoint")
    checkpoints.save(r, state, ws.sid, use_lessons, team)
    trace.save(r, label=label)
    return r


def decide_draft(ws: Workspace, cid, draft_id, decision, notes=""):
    """A person signs a plan off, or rejects it. Approving re-checks it first, because things may have changed since it
    was made. Returns (ok, errors); neither one dispatches anything."""
    from ..agent.graph import _Without
    from ..runtime.safety import validate_draft
    b, _ = ws.broker(cid, True)
    row = b.C.runtime.draft(draft_id)
    if decision == "approve" and row and row["status"] == "draft":
        v = validate_draft(_Without(b.C, draft_id), json.loads(row["order_ids"]), row["vehicle_id"], row["delivery_date"], b.policies, b.advisories)
        if not v.ok:
            return False, v.errors
    if not b.C.runtime.decide(draft_id, decision, notes, "reviewer"):
        return False, [f"this plan is {row['status']}"]
    return True, []


def mine_with_agent(ws: Workspace, client, cid):
    """The Lesson Miner on its own: reads the records and proposes through the evidence gate; a person still approves."""
    knowledge = agent_knowledge.for_team(ws, cid)
    r = team_mode.run(ws.company(cid), Session(cid, "dispatcher", "demo"), client, team_mode.MINE_BRIEF, lead_agent="lesson_miner", analysis=True,
                      lesson_store=ws.store(), knowledge_by_agent=knowledge, harnesses=harness_store().active_all())
    if ws.public:
        r["visitor"] = ws.sid
    trace.save(r, label=f"ui:{cid}:mine")
    return r


def run_live(ws: Workspace, cid, request, model_key, use_lessons, history=(), team=False):
    client, blocked = ws.live_client(model_key)
    if blocked:
        raise muse.MissingKeyError(blocked)
    return run_with(ws, client, cid, request, use_lessons, history, team)
