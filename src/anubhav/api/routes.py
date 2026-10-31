"""Every endpoint in contracts/api.md, grouped as the UI groups them. A route translates HTTP to the service and back."""

import json
import time
from typing import Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .. import review as nightly
from ..agents import forge, registry
from ..harness import loop, practice
from ..harness.store import CATEGORIES, PatchError, diff
from ..learning import digest, miner, newtools as nt, pack, profile, report
from ..learning.store import describe
from ..runtime.broker import Broker, Session
from ..runtime.company import CompanyData
from ..runtime.query import sandbox
from ..service import knowledge, proof as proof_files, runs, stream, views
from ..service.session import AGENT_MODEL, COMPANIES, LIVE_CALLS_PER_DAY, LIVE_RUNS_PER_SESSION, MODELS, SUGGESTIONS, Workspace, harness_store
from ..ui import logs
from .deps import ApiError, Cid, LocalOnly, Ws, live

api = APIRouter(prefix="/api")
WAITING = {"CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED"}
ACTIVE = {"ACTIVE_POLICY", "ACTIVE_ADVISORY"}


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _run_or_404(run_id, ws):
    r = runs.find_run(run_id, ws)
    if not r:
        raise ApiError(404, "NOT_FOUND", f"no run {run_id}")
    return r


# ---------- meta and session
@api.get("/health")
def health():
    return {"ok": True}


@api.get("/session")
def session(ws: Workspace = Ws):
    keys = {name: ws.live_ready(key) for name, key in MODELS.items() if key}
    return {"public": ws.public, "default_mode": "replay", "default_team": True, "models": {k: {"available": not why, "reason": why} for k, why in keys.items()},
            "live_runs_left": ws.live_runs_left(), "caps": {"per_session": LIVE_RUNS_PER_SESSION, "per_day": LIVE_CALLS_PER_DAY}}


@api.get("/companies")
def companies(ws: Workspace = Ws):
    out = []
    for cid, name in COMPANIES.items():
        C = ws.company(cid)
        out.append({"company": cid, "name": name, "sites": len(C.sites), "vehicles": len(C.vehicles), "towns": len({s["town"] for s in C.sites.values()}),
                    "plan_date": C.today})
    return out


@api.get("/suggestions")
def suggestions(company: str = Cid, use_lessons: bool = True, ws: Workspace = Ws):
    saved = set(runs.replayable(ws, company, use_lessons))
    return [{"label": k, "request": v, "has_replay": k in saved} for k, v in SUGGESTIONS.items()]


@api.post("/session/reset-drafts")
def reset_drafts(company: str = Cid, ws: Workspace = Ws):
    ws.company(company).runtime.reset()
    ws.state.pop("conversation", None)
    return {"ok": True}


# ---------- dashboard
@api.get("/dashboard/orders")
def dash_orders(company: str = Cid, ws: Workspace = Ws):
    return views.orders(ws, company)


@api.get("/dashboard/fleet")
def dash_fleet(company: str = Cid, ws: Workspace = Ws):
    return views.fleet(ws, company)


@api.get("/dashboard/drafts")
def dash_drafts(company: str = Cid, run_id: str | None = None, ws: Workspace = Ws):
    if run_id:
        r = _run_or_404(run_id, ws)
        if r["company"] != company:
            raise ApiError(404, "NOT_FOUND", f"run {run_id} is not {company}'s")
        return {"drafts": views.drafts_of_run(ws, company, r), "source": "run"}
    return {"drafts": views.drafts_for(ws, company, [r for r in runs.recent_runs(100, ws) if r["company"] == company and r.get("drafts")]), "source": "live"}


@api.post("/dashboard/drafts/{draft_id}/cancel")
def dash_cancel(draft_id: str, company: str = Cid, ws: Workspace = Ws):
    b, _ = ws.broker(company, False)
    out = b.call("cancel_dispatch_draft", {"draft_id": draft_id})
    if not out["ok"]:
        raise ApiError(404 if out["error"]["code"] == "NOT_FOUND" else 409, out["error"]["code"], out["error"]["message"])
    return out["result"]


@api.get("/dashboard/company")
def dash_company(company: str = Cid, ws: Workspace = Ws):
    return views.company_profile(ws, company)


class OwnerProfile(Body):
    owner: dict[str, str]


@api.put("/dashboard/company/profile")
def dash_profile(body: OwnerProfile, company: str = Cid, ws: Workspace = Ws):
    unknown = set(body.owner) - set(profile.OWNER_FIELDS)
    if unknown:
        raise ApiError(422, "BAD_ARGS", f"unknown fields: {', '.join(sorted(unknown))}")
    profile.save(ws.store(), ws.company(company), "owner", body.owner)
    return views.company_profile(ws, company)


# ---------- chat
class Chat(Body):
    company: str = "T01"
    message: str = Field(min_length=1, max_length=2000)
    mode: Literal["replay", "live"] = "replay"
    model: Literal["open", "spark"] = AGENT_MODEL
    use_lessons: bool = True
    team: bool = True           # EXP-013: R1-R3 held, so by its pre-registered rule the team is the default


def _history(ws, key):
    """This visitor's earlier turns, from saved runs on the server: a client can't put words in the agent's mouth."""
    out = []
    for run_id in ws.state.get("conversation", {}).get(key, [])[-6:]:
        r = runs.find_run(run_id, ws)
        if r:
            out.append({"request": r["request"], "run": r})
    return out


def _remember(ws, key, run_id):
    ws.state.setdefault("conversation", {}).setdefault(key, []).append(run_id)


@api.post("/chat")
def chat(body: Chat, ws: Workspace = Ws):
    cid = Cid.dependency(body.company)
    key = f"{cid}:{body.use_lessons}:{body.team}"
    reason = None
    if body.mode == "live":
        client, reason = ws.live_client(body.model)
        if client:
            run_id = stream.start(ws, client, cid, body.message, body.use_lessons, _history(ws, key), body.team)
            _remember(ws, key, run_id)
            return {"run_id": run_id, "mode": "live"}
    r = runs.find_replay(ws, cid, body.message, body.use_lessons, team=body.team)
    if not r:
        extra = {"suggestions": runs.replayable(ws, cid, body.use_lessons)}
        raise ApiError(404, "NO_REPLAY", (f"{reason} " if reason else "") + "No saved run for this request and setting.", **extra)
    return {"run_id": r["run_id"], "mode": "replay", "replay_of": "team" if r.get("mode") == "team" else "single", **({"reason": reason} if reason else {})}


def _sse(event_type, seq, data):
    return (f"event: {event_type}\n" + (f"id: {seq}\n" if seq is not None else "")
            + f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n")


@api.get("/chat/stream")
def chat_stream(request: Request, run_id: str, after: int = -1, ws: Workspace = Ws, last_event_id: str | None = Header(None)):
    if last_event_id and last_event_id.lstrip("-").isdigit():
        after = int(last_event_id)
    info = stream.status(run_id)
    if info.get("sid") not in (None, ws.sid):
        raise ApiError(404, "NOT_FOUND", f"no run {run_id}")
    saved = None if info else _run_or_404(run_id, ws)
    pace = request.app.state.replay_pace

    def gen():
        if saved:
            for e in stream.replay_events(saved, after):
                yield _sse(e["type"], e["seq"], e)
                time.sleep(pace)
            yield _sse("end", None, {"run_id": run_id, "stop": saved.get("stop"), "mode": "replay"})
            return
        for e in stream.follow(run_id, after, heartbeat_s=15):
            yield ": keepalive\n\n" if e is None else _sse(e["type"], e["seq"], e)
        yield _sse("end", None, {"run_id": run_id, "stop": stream.status(run_id).get("stop"), "mode": "live"})
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api.get("/runs/{run_id}")
def run_detail(run_id: str, ws: Workspace = Ws):
    return _run_or_404(run_id, ws)


class Feedback(Body):
    rating: Literal[0, 1]
    category: str = "other"
    note: str = Field("", max_length=500)


@api.post("/runs/{run_id}/feedback")
def run_feedback(run_id: str, body: Feedback, ws: Workspace = Ws):
    if body.category not in {*CATEGORIES, "good"}:
        raise ApiError(422, "BAD_ARGS", f"category must be one of {', '.join(CATEGORIES)}")
    r = _run_or_404(run_id, ws)
    return {"feedback_id": harness_store().add_feedback(r["company"], r, body.rating, body.category, body.note)}


# ---------- agents
def _agent_row(a, H, sizes):
    return {"agent": a.agent_id, "name": a.name, "purpose": a.purpose, "status": a.status, "voice": a.voice, "model": a.model, "handles": list(a.handles),
            "version": H.active(a.agent_id)["version_id"], "versions_tried": len(H.versions(a.agent_id)) - 1, "knowledge_items": sizes.get(a.agent_id, 0)}


@api.get("/agents")
def agents(company: str = Cid, ws: Workspace = Ws):
    H, sizes = harness_store(), knowledge.sizes(ws, company)
    return [_agent_row(a, H, sizes) for a in registry.load().agents.values()]


@api.get("/agents/{agent_id}")
def agent_detail(agent_id: str, company: str = Cid, ws: Workspace = Ws):
    """One agent: its instructions, what it knows, every version with its test result, and the score at each version."""
    a = registry.load().get(agent_id)
    if not a:
        raise ApiError(404, "NOT_FOUND", f"no agent {agent_id}")
    H = harness_store()
    known = {"planner": ws.knowledge_for(company)[0]} | knowledge.for_team(ws, company)
    versions, curve = [], []
    for v in H.versions(agent_id):
        g = (v["probe"] or {}).get("gate") or {}
        versions.append({k: v[k] for k in ("version_id", "parent", "status", "created", "rationale", "decided_by", "decided", "note")}
                        | {"diff": diff(H.get(v["parent"])["surfaces"], v["surfaces"]) if v["parent"] else [], "test_passed": g.get("pass"), "test_reasons": g.get("reasons", [])})
        if v["probe"] and v["probe"].get("rows"):
            rows = v["probe"]["rows"]
            curve.append({"version": v["version_id"], **{f"{side}_{m}": sum(x[side][m] for x in rows) for side in ("base", "cand") for m in ("tool_errors", "tool_calls", "cost_usd")}})
    recent = [r for r in runs.recent_runs(500, ws) if r["company"] == company]
    return {**_agent_row(a, H, knowledge.sizes(ws, company)), "instructions": a.instructions, "limits": vars(a.limits), "active_surfaces": H.active(agent_id)["surfaces"],
            "knowledge": known.get(agent_id, []), "versions": versions, "paired_tests": curve, "scores": H.scores(agent_id),
            "totals": next((t for t in logs.agent_totals(recent) if t["agent"] == agent_id), None)}


# ---------- lessons
@api.get("/learning/lessons")
def lessons(company: str = Cid, state: str | None = None, ws: Workspace = Ws):
    C, S = ws.company(company), ws.store()
    return [dict(l, what=describe(l, C), events=S.events(l["lesson_id"])) for l in S.list(company, {state} if state else None)]


class LessonDecision(Body):
    decision: Literal["approve", "reject", "retire", "rollback"]
    effect: Literal["advisory", "policy"] = "advisory"
    verified: str = Field("", max_length=300)
    why: str = Field("", max_length=300)


@api.post("/learning/lessons/{lesson_id}/decide")
def lesson_decide(lesson_id: str, body: LessonDecision, company: str = Cid, ws: Workspace = Ws):
    S = ws.store()
    if not any(l["lesson_id"] == lesson_id for l in S.list(company)):
        raise ApiError(404, "NOT_FOUND", f"{company} has no lesson {lesson_id}")
    if body.decision == "approve":
        return S.approve(lesson_id, "reviewer", body.effect, body.verified)
    if body.decision == "rollback":
        return S.rollback(lesson_id, "reviewer")
    if not body.why.strip():
        raise ApiError(422, "BAD_ARGS", f"{body.decision} needs a reason")
    return (S.reject if body.decision == "reject" else S.retire)(lesson_id, "reviewer", body.why)


def _timeline(ws, company):
    S, H = ws.store(), harness_store()
    return logs.learning_events(company, S.events(company=company), {l["lesson_id"]: l for l in S.list(company)}, H.versions(), nt.tools(S, company))


@api.get("/learning/timeline")
def learning_timeline(company: str = Cid, agent: str | None = None, ws: Workspace = Ws):
    return [e for e in _timeline(ws, company) if not agent or e["agent"] == agent]


@api.post("/learning/mine", dependencies=[LocalOnly])
def mine(company: str = Cid, by: Literal["agent", "offline"] = "agent", ws: Workspace = Ws):
    """The Lesson Miner agent (Muse Spark Open), or the offline miner the measured results used (Muse Spark 1.3)."""
    if by == "agent":
        r = runs.mine_with_agent(ws, live(ws, AGENT_MODEL), company)
        made = [s["result"] for s in r["trace"] if s["type"] == "tool" and s["name"] == "propose_lesson" and s["ok"] and s["result"].get("lesson_id")]
        return {"new": [m["lesson_id"] for m in made], "cost_usd": r["cost_usd"], "run_id": r["run_id"], "stop": r["stop"]}
    client = live(ws, "spark")
    C = ws.company(company)
    F, d = digest.build(C)
    props, meta = miner.mine(client, C, d)
    return {"new": ws.store().add_proposals(company, F, props, meta), "cost_usd": meta["cost_usd"]}


# ---------- new tools
def _groups(ws, cid):
    C = ws.company(cid)
    sb = sandbox(C)
    known = {t["tool_id"].rsplit("-", 1)[-1] for t in nt.tools(ws.store(), cid)}
    return sb, [g for g in nt.groups(runs.recent_runs(500, ws), cid, sb) if g["key"][:8] not in known]


def _group_view(g):
    return {"key": g["key"], "template": g["template"], "requests": g["requests"], "uses": len(g["uses"]), "agents": sorted({u["agent"] for u in g["uses"]}),
            "params": g["uses"][0]["params"], "reached_threshold": len(g["requests"]) >= nt.MIN_USES, "threshold": nt.MIN_USES,
            "suggested_name": nt.suggest_name(g), "suggested_description": nt.describe(g)}


@api.get("/tools")
def tools(company: str = Cid, status: str | None = None, ws: Workspace = Ws):
    return nt.tools(ws.store(), company, status)


@api.get("/tools/candidates")
def tool_candidates(company: str = Cid, ws: Workspace = Ws):
    return [_group_view(g) for g in _groups(ws, company)[1]]


class ToolCheck(Body):
    name: str | None = Field(None, max_length=40)
    description: str | None = Field(None, max_length=300)


@api.post("/tools/candidates/{key}/check")
def tool_check(key: str, body: ToolCheck, company: str = Cid, ws: Workspace = Ws):
    """Run the promotion checks and record the result. A person may do this early (below the threshold); the checks are the same."""
    sb, groups = _groups(ws, company)
    g = next((x for x in groups if x["key"] == key), None)
    if not g:
        raise ApiError(404, "NOT_FOUND", f"no query group {key}")
    named = {"name": body.name, "description": body.description, "named_by": "person"} if body.name else None
    if not named:           # Tool Forge names it when a live model is allowed here; otherwise code does, for free
        client = None if ws.public or ws.live_ready(AGENT_MODEL) else ws.live_client(AGENT_MODEL)[0]
        named = forge.name_tool(client, ws.company(company), g, knowledge=knowledge.tool_forge([], ws.company(company), ws.store()))
    tid = nt.propose(ws.store(), company, g, nt.check(g, sb), named["name"], body.description or named["description"] or nt.describe(g))
    return {**next(t for t in nt.tools(ws.store(), company) if t["tool_id"] == tid), "named_by": named["named_by"]}


class ToolDecision(Body):
    approve: bool
    note: str = Field("", max_length=300)


@api.post("/tools/{tool_id}/decide")
def tool_decide(tool_id: str, body: ToolDecision, company: str = Cid, ws: Workspace = Ws):
    S = ws.store()
    if not any(t["tool_id"] == tool_id for t in nt.tools(S, company)):
        raise ApiError(404, "NOT_FOUND", f"{company} has no tool {tool_id}")
    nt.decide(S, tool_id, "owner", body.approve, body.note)
    return next(t for t in nt.tools(S, company) if t["tool_id"] == tool_id)


@api.post("/tools/{tool_id}/retire")
def tool_retire(tool_id: str, company: str = Cid, ws: Workspace = Ws):
    return tool_decide(tool_id, ToolDecision(approve=False, note="retired"), company, ws)


# ---------- tuning: Loop A (one harness for every visitor, so changes are local-only)
def _spec(agent):
    a = registry.load().get(agent)
    if not a:
        raise ApiError(404, "NOT_FOUND", f"no agent {agent}")
    return a


def _problems(ws, agent):
    recent = runs.recent_runs(60, ws)
    return {**loop.collect(recent, harness_store().feedback("new"), agent), "routing_evidence": logs.routing_stats(recent) if agent == "planner" else []}


@api.get("/harness")
def harness_view(agent: str = "planner"):
    _spec(agent)
    H = harness_store()
    return {"agent": agent, "active": H.active(agent), "versions": [dict(v, diff=diff(H.get(v["parent"])["surfaces"], v["surfaces"]) if v["parent"] else []) for v in H.versions(agent)],
            "feedback": H.feedback(), "categories": CATEGORIES}


@api.get("/harness/problems")
def harness_problems(agent: str = "planner", ws: Workspace = Ws):
    _spec(agent)
    return _problems(ws, agent)


@api.post("/harness/propose", dependencies=[LocalOnly])
def harness_propose(company: str = Cid, agent: str = "planner", ws: Workspace = Ws):
    spec = _spec(agent)
    H = harness_store()
    problems = _problems(ws, agent)
    if not (problems["feedback"] or problems["trace_issues"]):
        raise ApiError(409, "NOTHING_TO_FIX", f"no problems in {agent}'s recent runs or new feedback")
    client = live(ws, "spark")
    C = ws.company(company)
    b = Broker(C, Session(company), analysis=True, learned_tools=nt.tools(ws.store(), company, "active"))
    patch, meta = loop.propose(client, b, H.active(agent)["surfaces"], problems, "" if agent == "planner" else f"{spec.name}: {spec.purpose}")
    try:
        v = H.propose(patch, patch.get("rationale", ""), [t.name for t in b.list_tools()], C, agent)
    except PatchError as e:
        raise ApiError(422, "PATCH_REFUSED", str(e), patch=patch)
    return {"version": v, "cost_usd": meta["cost_usd"]}


@api.post("/harness/rollback", dependencies=[LocalOnly])
def harness_rollback(agent: str = "planner"):
    _spec(agent)
    H = harness_store()
    if not H.active(agent)["parent"]:
        raise ApiError(409, "NOTHING_TO_ROLL_BACK", "the active version is the baseline")
    return H.rollback("reviewer", agent)


@api.post("/harness/{version_id}/probe", dependencies=[LocalOnly])
def harness_probe(version_id: str, company: str = Cid, ws: Workspace = Ws):
    H = harness_store()
    v = H.get(version_id)
    if not v or v["status"] != "candidate":
        raise ApiError(404, "NOT_FOUND", f"no candidate {version_id}")
    new_fb = [f for f in H.feedback("new") if f["rating"] == 0]
    cases = [{"request": f["request"], "company": f["company"], "use_lessons": bool(f["use_lessons"]), "origin": f"feedback {f['feedback_id']}",
              "feedback_id": f["feedback_id"], "expects_draft": False} for f in new_fb[:3]]
    cases += [{"request": SUGGESTIONS["Roman Telugu"], "company": company, "use_lessons": False, "origin": "regression (golden path)", "expects_draft": True},
              {"request": SUGGESTIONS["Ambiguous"], "company": company, "use_lessons": False, "origin": "regression (ambiguity)", "expects_draft": False}]
    agent, judge = live(ws, AGENT_MODEL), live(ws, "spark")
    fb = {f["feedback_id"]: {"note": f["note"], "category": CATEGORIES.get(f["category"])} for f in new_fb}
    C = CompanyData(ws.world, company, ws.world / "runtime" / "probe")
    # dev questions with answers from the records: a change must not lose right answers to pass
    for q in practice.build_gaps(C, split="dev")[:2]:
        cases.append({"request": q["question"], "company": company, "use_lessons": False, "origin": "dev question", "expects_draft": False,
                      "score": lambda r, q=q: practice.score(q, r)["answer_ok"]})
    if v["agent"] == "planner":
        res = loop.probe(C, agent, judge, cases, H.get(v["parent"])["surfaces"], v["surfaces"], fb, ws.knowledge_for)
    else:           # another agent's change is only seen through the team, and may not harm the others
        res = loop.team_probe(C, agent, judge, cases, v["agent"], H.get(v["parent"])["surfaces"], v["surfaces"], fb, ws.knowledge_for, H.active_all())
    H.record_probe(version_id, res)
    return res


class VersionDecision(Body):
    approve: bool
    note: str = Field("", max_length=300)


@api.post("/harness/{version_id}/decide", dependencies=[LocalOnly])
def harness_decide(version_id: str, body: VersionDecision):
    H = harness_store()
    if not H.get(version_id):
        raise ApiError(404, "NOT_FOUND", f"no version {version_id}")
    H.decide(version_id, "reviewer", body.approve, body.note)
    if body.approve:
        H.mark_feedback([f["feedback_id"] for f in H.feedback("new") if f["rating"] == 0], "addressed")
    return H.get(version_id)


@api.get("/practice")
def practice_view():
    rows, groups = harness_store().practice(), {}
    for r in rows:
        groups.setdefault((r["round"], r["version_id"], r["split"]), []).append(r)
    return [{"round": k[0], "version": k[1], "split": k[2], "questions": len(rs), "answers_right": sum(r["answer_ok"] for r in rs) / len(rs),
             "fitting_tool": sum(r["right_tool"] for r in rs) / len(rs), "no_lookup": sum(not r["used_tool"] for r in rs) / len(rs),
             "tool_errors": sum(r["tool_errors"] for r in rs), "cost_usd": round(sum(r["cost_usd"] for r in rs), 3)} for k, rs in groups.items()]


@api.post("/practice", dependencies=[LocalOnly])
def practice_run(company: str = Cid, agent: str | None = None, ws: Workspace = Ws):
    """A practice set, by the single Planner, or by one agent of the team on its own kind of question; its score is kept."""
    H = harness_store()
    client = live(ws, AGENT_MODEL)
    C = ws.company(company)
    if agent is None:
        res = practice.run(C, client, practice.build(C, split="dev"), H.active()["surfaces"])
        H.add_practice(f"API-{company}", H.active()["version_id"], res)
        return practice.summary(res)
    _spec(agent)
    questions = practice.build_gaps(C, split="dev") if agent == "tool_forge" else practice.build(C, split="dev")
    res = practice.run_agent(C, client, questions, agent, H.active_all(), knowledge.for_team(ws, company), nt.tools(ws.store(), company, "active"))
    s = practice.summary(res)
    H.add_score(agent, H.active(agent)["version_id"], f"practice:dev:{company}", s["questions"], sum(x["answer_ok"] for x in res), 0,
                sum(x["tool_calls"] for x in res), s["tool_errors"], s["cost_usd"])
    return s


# ---------- sharing
class Publish(Body):
    sources: list[str] = Field(default_factory=lambda: ["T01", "T02"], max_length=4)
    target: str = "TNEW"
    accept_rules: bool = True


@api.get("/packs")
def packs(target: str = "TNEW", ws: Workspace = Ws):
    cid = Cid.dependency(target)
    imported = [l for l in ws.store().list(cid, ACTIVE) if l["source"].startswith("pack:")]
    return {"published": ws.state.get("packs", []), "received": [dict(l, what=describe(l, ws.company(cid))) for l in imported]}


@api.post("/packs/publish")
def packs_publish(body: Publish, ws: Workspace = Ws):
    S, dst = ws.store(), ws.company(Cid.dependency(body.target))
    done = []
    for src in body.sources:
        if src == body.target:
            continue
        source = ws.company(Cid.dependency(src))
        p = pack.publish(S, source, dst, approved_by=f"owner-{src}")
        ids = pack.import_pack(S, p, dst, accepted_by=f"owner-{body.target}", accept_policies=body.accept_rules)
        done.append({"pack": p["pack_id"], "from": src, "to": body.target, "items": len(p["items"]), "skipped": len(p["skipped"]),
                     "leaks": pack.leaks(p, source, dst), "imported": ids})
    ws.state.setdefault("packs", []).extend(done)
    return done


@api.post("/packs/revoke")
def packs_revoke(target: str = "TNEW", ws: Workspace = Ws):
    cid = Cid.dependency(target)
    S = ws.store()
    imported = [l for l in S.list(cid, ACTIVE) if l["source"].startswith("pack:")]
    ids = {p for l in imported for p in (l["gate"].get("confirmed_by") or [l["source"].split(":", 1)[1]])}
    for pid in ids:
        pack.revoke(S, pid, cid, "owner")
    return {"revoked": sorted(ids)}


# ---------- review, proof, ledger, logs
@api.post("/review/run")
def review_run(company: str = Cid, ws: Workspace = Ws):
    """Free without a model. Hosted it stays free: the paid part (lesson proposals, naming) needs a local run."""
    client = None if ws.public or ws.live_ready("spark") else ws.live_client("spark")[0]
    return nightly.review(ws.company(company), ws.store(), runs.recent_runs(500, ws), harness_store().feedback(), client, forge_client=client)


@api.get("/review/history")
def review_history(company: str = Cid, ws: Workspace = Ws):
    return nightly.reviews(ws.store(), company)


@api.get("/proof")
def proof():
    return proof_files.results()


@api.get("/proof/curve")
def proof_curve():
    """The whole system at each learning stage and each agent's score (EXP-014), or {"measured": false} until it has run."""
    return proof_files.curve()


@api.get("/compare")
def compare(request: str, company: str = Cid, ws: Workspace = Ws):
    """The same request before and after learning, from real saved runs: cold vs with lessons, and before vs after learned tools."""
    def view(r):
        return r and {"run_id": r["run_id"], "reply": r.get("reply"), "drafts": views.drafts(r), "tool_calls": views.team_parts(r)["tool_calls"], "cost_usd": r.get("cost_usd"),
                      "agents": views.team_parts(r)["agents"], "lessons_in_prompt": len(r.get("knowledge") or []), "learned_tools": r.get("learned_tools") or []}
    return {"request": request, "cold": view(runs.find_replay(ws, company, request, False, learned=False)), "with_lessons": view(runs.find_replay(ws, company, request, True, learned=False)),
            "with_learned_tools": view(next((r for r in [runs.find_replay(ws, company, request, False, learned=True)] if r and r.get("learned_tools")), None))}


@api.get("/ledger")
def ledger(company: str = Cid, agent: str | None = None, type: str | None = None, limit: int = 200, ws: Workspace = Ws):
    from ..events import from_run
    kinds = {"handoff", "draft_created", "validator_check", "lesson_used", "tool_missing"}
    out = []
    for r in runs.recent_runs(200, ws):
        if r["company"] != company:
            continue
        out += [e for e in from_run(r) if e["type"] in kinds and (not agent or e["agent_id"] == agent) and (not type or e["type"] == type)]
    if type in (None, "learning_event"):      # decisions come from the learning stores, in the same event shape
        out += [{"run_id": x["ref"], "seq": i, "agent_id": x["agent"], "agent_run_id": x["ref"], "caller": "learning", "depth": 0, "ts": x["ts"], "type": "learning_event", "payload": x}
                for i, x in enumerate(_timeline(ws, company)) if not agent or x["agent"] == agent]
    return sorted(out, key=lambda e: e["ts"] or "", reverse=True)[:min(limit, 1000)]


def _entry(e):
    return {k: v for k, v in e.items() if k != "raw"}


@api.get("/logs/events")
def log_events(company: str = Cid, stream_name: str | None = None, ws: Workspace = Ws):
    S, H = ws.store(), harness_store()
    rows = logs.events(company, runs.recent_runs(200, ws), S.events(company=company), {l["lesson_id"]: l for l in S.list(company)}, H.versions(), H.feedback(),
                       nt.tools(S, company), nightly.reviews(S, company))
    return [_entry(r) for r in rows if not stream_name or r["stream"] == stream_name]


@api.get("/logs/runs")
def log_runs(company: str | None = None, limit: int = 60, ws: Workspace = Ws):
    if company:
        Cid.dependency(company)
    rows = [r for r in runs.recent_runs(min(limit, 500), ws) if not company or r["company"] == company]
    return [{"run_id": r["run_id"], "saved_at": r.get("saved_at"), "label": r.get("label"), "company": r["company"], "model": r.get("model"), "request": r["request"],
             "mode": r.get("mode", "single"), **views.team_parts(r), "drafts": r.get("drafts", []), "stop": r.get("stop"), "cost_usd": r.get("cost_usd"),
             "issues": logs.run_issues(r)} for r in rows]


@api.get("/logs/runs/{run_id}")
def log_run(run_id: str, ws: Workspace = Ws):
    r = _run_or_404(run_id, ws)
    return {"run_id": run_id, "request": r["request"], "reply": r.get("reply"), "issues": logs.run_issues(r),
            "timeline": [{k: v for k, v in x.items() if k != "raw"} for x in logs.timeline(r, views.summarize)]}


@api.get("/logs/tools")
def log_tools(company: str | None = None, ws: Workspace = Ws):
    rows = [r for r in runs.recent_runs(500, ws) if not company or r["company"] == company]
    return {"usage": logs.tool_usage(rows), "missing": logs.missing_tools(rows)}


@api.get("/logs/routing")
def log_routing(company: str | None = None, ws: Workspace = Ws):
    return logs.routing_stats([r for r in runs.recent_runs(500, ws) if not company or r["company"] == company])


@api.get("/logs/agents")
def log_agents(company: str | None = None, ws: Workspace = Ws):
    return logs.agent_totals([r for r in runs.recent_runs(500, ws) if not company or r["company"] == company])


@api.get("/logs/models")
def log_models(company: str = Cid, ws: Workspace = Ws):
    return logs.model_roles(runs.recent_runs(500, ws), ws.store().list(company), harness_store().versions())


@api.get("/report/weekly")
def weekly(company: str = Cid, ws: Workspace = Ws):
    return {"company": company, "markdown": report.weekly(ws.store(), company, ws.company(company))}
