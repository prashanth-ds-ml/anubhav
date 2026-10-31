"""The activity log: one timeline of what the agent did and what it learned, built only from what is already recorded
(run traces, the lesson store's events, the harness store). Plain functions, so the page stays thin and tests need
no Streamlit."""

import json
from collections import Counter

from ..trace import walk

STREAMS = {"run": "Agent runs", "lesson": "Business facts (Loop B)", "harness": "Tool use (Loop A)",
           "tool": "New tools", "review": "Nightly reviews", "feedback": "Feedback"}


def _args(a):
    try:
        return json.loads(a) if isinstance(a, str) else (a or {})
    except ValueError:
        return {"raw": a}


def _short(x, n=160):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n - 1] + "…"


def timeline(r, summarize=None):
    """A run as plan → act → observe rows, then the code checks. kind: plan | act | observe | refused | check | error.
    summarize(step) may give a readable one-line result; the raw step is kept on every row."""
    rows = []
    children = {c["run_id"]: c for c in r.get("children", [])}
    for s in r.get("trace", []):
        t = s["type"]
        if t == "model":
            if s.get("content"):
                rows.append({"turn": s["turn"], "kind": "plan" if s.get("tool_calls") else "answer",
                             "text": _short(s["content"], 400), "raw": s})
            elif s.get("tool_calls"):
                rows.append({"turn": s["turn"], "kind": "plan",
                             "text": "decides to call " + ", ".join(c["name"] for c in s["tool_calls"]), "raw": s})
        elif t == "tool":
            rows.append({"turn": None, "kind": "act", "text": f"{s['name']}({_short(_args(s['arguments']), 200)})", "raw": s})
            if s["ok"]:
                rows.append({"turn": None, "kind": "observe",
                             "text": summarize(s) if summarize else _short(s.get("result")), "raw": s.get("result")})
            else:
                rows.append({"turn": None, "kind": "refused", "text": f"{s['error']['code']}: {s['error']['message']}",
                             "raw": s["error"]})
            child = children.get((s.get("result") or {}).get("run_id")) if s["name"] == "delegate" else None
            if child:                       # the teammate's own steps, in place
                rows += [{**x, "agent": x.get("agent") or child.get("agent_id")} for x in timeline(child, summarize)]
        elif t == "model_error":
            rows.append({"turn": s.get("turn"), "kind": "error", "text": s["error"], "raw": s})
        elif t == "finish":
            for d in s.get("draft_checks", []):
                rows.append({"turn": None, "kind": "check", "text": f"draft {d['draft_id']} re-checked: "
                             + ("still valid" if d["still_valid"] else "NO LONGER VALID: " + "; ".join(e["message"] for e in d["errors"])),
                             "raw": d, "ok": d["still_valid"]})
            rc = s.get("reply_check")
            if rc:
                bad = rc["unknown_ids"] + rc["claims"]
                rows.append({"turn": None, "kind": "check", "ok": rc["ok"], "raw": rc,
                             "text": "reply checked: every id came from this run, no dispatch claimed" if rc["ok"]
                             else "reply check FAILED: " + ", ".join(bad)})
    return rows


def run_issues(r):
    """What a reviewer should look at in a run (shown on the log row)."""
    out = []
    refused = [s for part in walk(r) for s in part.get("trace", []) if s["type"] == "tool" and not s["ok"]]
    if refused:
        out.append(f"{len(refused)} refused")
    if r.get("stop") in ("limit", "error"):
        out.append(f"stopped: {r['stop']}")
    rc = r.get("reply_check")
    if rc and not rc["ok"]:
        out.append("reply check failed")
    return ", ".join(out)


def tool_usage(runs):
    """Which agent used which tool, how often and how it went, from every run and teammate run."""
    seen = Counter()
    failed = Counter()
    last = {}
    for top in runs:
        for r in walk(top):
            for s in r.get("trace", []):
                if s.get("type") != "tool":
                    continue
                k = (r.get("agent_id") or "planner", s["name"])
                seen[k] += 1
                failed[k] += not s["ok"]
                last[k] = max(last.get(k, ""), top.get("saved_at") or "")
    return [{"agent": a, "tool": t, "calls": n, "failed": failed[(a, t)], "last_used": last[(a, t)]}
            for (a, t), n in seen.most_common()]


def missing_tools(runs):
    """What agents needed and no tool or teammate fitted, most asked first, with the requests behind it."""
    needs = {}
    for top in runs:
        for r in walk(top):
            for s in r.get("trace", []):
                res = s.get("result") if s.get("type") == "tool" and s.get("ok") else None
                if res and res.get("tool_missing"):
                    n = needs.setdefault(res["need"], {"need": res["need"], "times": 0, "requests": []})
                    n["times"] += 1
                    if top.get("request") not in n["requests"]:
                        n["requests"].append(top.get("request"))
    return sorted(needs.values(), key=lambda x: -x["times"])


def routing_stats(runs):
    """Who handled which kind of task and how it went: the evidence for routing hints. A task's kind is the tool
    categories its steps used, so it comes from the runs, not from a word list."""
    from ..runtime.broker import ANALYSIS, REGISTRY
    category = {t.name: t.category for t in REGISTRY + ANALYSIS}
    rows = {}
    for top in runs:
        for r in walk(top):
            steps = [s for s in r.get("trace", []) if s.get("type") == "tool"]
            kinds = sorted({category.get(s["name"], "learned_tools") for s in steps if category.get(s["name"]) != "system" and s["name"] != "delegate"})
            if not kinds or (s := next((x for x in steps if x["name"] in ("delegate", "find_capability", "sequence_stops")), None)) and not [x for x in steps if x["name"] not in ("delegate", "find_capability", "sequence_stops")]:
                continue
            k = ("+".join(kinds), r.get("agent_id") or "planner")
            row = rows.setdefault(k, {"task_kind": k[0], "handled_by": k[1], "requests": 0, "answered": 0, "tool_errors": 0, "tool_calls": 0, "cost_usd": 0.0})
            row["requests"] += 1
            row["answered"] += r.get("stop") == "answered"
            row["tool_errors"] += sum(not s["ok"] for s in steps)
            row["tool_calls"] += len(steps)
            row["cost_usd"] = round(row["cost_usd"] + (r.get("cost_usd") or 0), 5)
    return sorted(rows.values(), key=lambda x: -x["requests"])


def learning_events(company, lesson_events=(), lessons=None, versions=(), new_tools=()):
    """Every learning decision for one company, newest first: what was proposed, tested, approved or refused, for which
    agent. Read from the stores that already record them, so nothing can show here that didn't happen."""
    lessons = lessons or {}
    out = []
    for e in lesson_events:
        if e.get("company") == company:
            les = lessons.get(e["lesson_id"], {})
            out.append({"ts": e["ts"], "kind": "lesson", "agent": "lesson_miner", "decision": e["action"], "ref": e["lesson_id"], "by": e.get("actor"),
                        "what": les.get("claim") or les.get("kind") or "", "state": e.get("to_state"), "note": e.get("note") or ""})
    for v in versions:
        if v.get("parent") is None:
            continue
        agent = v.get("agent") or "planner"
        out.append({"ts": v.get("created", ""), "kind": "patch", "agent": agent, "decision": "proposed", "ref": v["version_id"], "by": "Muse (proposer)",
                    "what": v.get("rationale") or "", "state": "candidate", "note": ""})
        if v.get("probe"):
            g = v["probe"].get("gate") or {}
            out.append({"ts": v.get("decided") or v.get("created", ""), "kind": "patch", "agent": agent, "decision": "tested", "ref": v["version_id"], "by": "code (paired test)",
                        "what": v.get("rationale") or "", "state": "passed" if g.get("pass") else "failed", "note": "; ".join(map(str, g.get("reasons", [])))})
        if v.get("decided"):
            out.append({"ts": v["decided"], "kind": "patch", "agent": agent, "decision": v["status"], "ref": v["version_id"], "by": v.get("decided_by"),
                        "what": v.get("rationale") or "", "state": v["status"], "note": v.get("note") or ""})
    for t in new_tools:
        if t.get("company") == company:
            c = t.get("checks") or {}
            out.append({"ts": t["created"], "kind": "tool", "agent": "tool_forge", "decision": "checked", "ref": t["tool_id"], "by": "code (promotion checks)",
                        "what": t["name"], "state": "passed" if c.get("pass") else "failed", "note": "; ".join(c.get("reasons", []))})
            if t.get("decided"):
                out.append({"ts": t["decided"], "kind": "tool", "agent": "tool_forge", "decision": t["status"], "ref": t["tool_id"], "by": t.get("decided_by"),
                            "what": t["name"], "state": t["status"], "note": t.get("note") or ""})
    return sorted(out, key=lambda x: x["ts"] or "", reverse=True)


def events(company, runs=(), lesson_events=(), lessons=None, versions=(), feedback=(), new_tools=(), reviews=()):
    """Every recorded event for one company, newest first: {ts, stream, what, who, detail, ref, raw}."""
    lessons = lessons or {}
    out = []
    for r in runs:
        if r.get("company") != company:
            continue
        n = sum(1 for part in walk(r) for s in part.get("trace", []) if s["type"] == "tool")
        out.append({"ts": r.get("saved_at", ""), "stream": "run", "what": _short(r.get("request", ""), 90),
                    "who": f"agent ({r.get('model', '?').split('/')[-1]})",
                    "detail": f"{n} tool calls · {len(r.get('drafts', []))} drafts · ${r.get('cost_usd', 0):.3f}"
                              + (f" · {i}" if (i := run_issues(r)) else "") + (" · with lessons" if r.get("knowledge") else ""),
                    "ref": r.get("run_id"), "raw": r})
    for e in lesson_events:
        if e.get("company") != company:
            continue
        les = lessons.get(e["lesson_id"], {})
        g = les.get("gate") or {}
        move = f"{e.get('from_state') or '—'} → {e.get('to_state') or '—'}"
        out.append({"ts": e["ts"], "stream": "lesson", "what": f"{e['action']}: {les.get('claim') or les.get('kind') or e['lesson_id']}"[:120],
                    "who": e.get("actor") or "", "detail": f"{e['lesson_id']} · {move}"
                    + (f" · gate: {g.get('verdict')} ({g.get('support', 0)} for, {g.get('counter', 0)} against)" if g and e["action"] in ("propose", "proposed", "add") else "")
                    + (f" · {e['note']}" if e.get("note") else ""), "ref": e["lesson_id"], "raw": {"event": e, "lesson": les}})
    for v in versions:
        if v.get("version_id") == "h-000":
            continue
        out.append({"ts": v.get("created", ""), "stream": "harness", "what": f"patch {v['version_id']} proposed",
                    "who": "Muse (proposer)", "detail": _short(v.get("rationale") or "", 140), "ref": v["version_id"], "raw": v})
        if v.get("probe"):
            g = v["probe"].get("gate") or {}
            out.append({"ts": v.get("created", ""), "stream": "harness", "what": f"patch {v['version_id']} tested old vs new",
                        "who": "code (paired test)", "ref": v["version_id"], "raw": v["probe"],
                        "detail": ("passed" if g.get("pass") else "failed: " + "; ".join(map(str, g.get("reasons", []))))[:160]})
        if v.get("decided"):
            out.append({"ts": v["decided"], "stream": "harness", "what": f"patch {v['version_id']} {v['status']}",
                        "who": v.get("decided_by") or "", "detail": _short(v.get("note") or "", 140), "ref": v["version_id"], "raw": v})
    for f in feedback:
        if f.get("company") != company:
            continue
        out.append({"ts": f["ts"], "stream": "feedback", "what": ("👍 " if f["rating"] == 1 else "👎 ") + _short(f.get("request", ""), 80),
                    "who": f.get("source", "tester"), "detail": f"{f.get('category')}: {_short(f.get('note') or '', 120)} · {f.get('status')}",
                    "ref": f.get("run_id"), "raw": f})
    for nt in new_tools:
        if nt.get("company") != company:
            continue
        c = nt.get("checks") or {}
        out.append({"ts": nt["created"], "stream": "tool", "what": f"query checked as a tool: {nt['name']}",
                    "who": "code (promotion checks)", "ref": nt["tool_id"], "raw": nt,
                    "detail": ("passed" if c.get("pass") else "failed: " + "; ".join(c.get("reasons", [])))[:160]
                              + f" · from {len(nt.get('source') or [])} queries"})
        if nt.get("decided"):
            out.append({"ts": nt["decided"], "stream": "tool", "what": f"tool {nt['name']} {nt['status']}",
                        "who": nt.get("decided_by") or "", "detail": nt.get("note") or nt.get("description", "")[:140],
                        "ref": nt["tool_id"], "raw": nt})
    for rv in reviews:
        rep = rv["report"]
        out.append({"ts": rv["ts"], "stream": "review", "what": f"reviewed {rep['runs']} runs and {rep['feedback']} feedback",
                    "who": rv.get("actor", ""), "ref": None, "raw": rep,
                    "detail": f"tool use: {len(rep['tool_use']['issues'])} issues · new tools: {len(rep['new_tools']['candidates'])} "
                              f"candidates · facts: {len(rep['facts'].get('proposed', []))} lessons proposed"})
    order = {id(x): i for i, x in enumerate(out)}       # same time: the later step (e.g. tested after proposed) first
    return sorted(out, key=lambda x: (x["ts"] or "", order[id(x)]), reverse=True)


def model_roles(runs=(), lessons=(), versions=()):
    """Which Meta model did what here, counted from the records (runs, mined lessons, proposed patches)."""
    agent = [r for r in runs if "open" in str(r.get("model", ""))]
    other_runs = [r for r in runs if r not in agent]
    mined = [l for l in lessons if (l.get("miner") or {}).get("model")]
    patches = [v for v in versions if v.get("version_id") != "h-000"]
    return [
        {"model": "Muse Spark Open", "access": "open weights · Baseten", "role": "the agent: plans, calls tools, answers in Telugu / Roman Telugu / English",
         "count": f"{len(agent)} runs · ${sum(r.get('cost_usd', 0) for r in agent):.2f}"},
        {"model": "Muse Spark 1.3", "access": "Meta Model API", "role": "proposes lessons from the records and tool-use patches; code checks every proposal",
         "count": f"{len(mined)} lesson{'s' * (len(mined) != 1)} · {len(patches)} patch{'es' * (len(patches) != 1)}" + (f" · {len(other_runs)} agent runs" if other_runs else "")},
        {"model": "Muse Voice Transcribe", "access": "Meta Model API", "role": "turns a spoken Telugu / Roman Telugu request into text the planner can correct",
         "count": "on the Workbench microphone"},
    ]
