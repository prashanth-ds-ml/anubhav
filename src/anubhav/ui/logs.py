"""The activity log: one timeline of what the agent did and what it learned, built only from what is already recorded
(run traces, the lesson store's events, the harness store). Plain functions, so the page stays thin and tests need
no Streamlit."""

import json

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
    refused = [s for s in r.get("trace", []) if s["type"] == "tool" and not s["ok"]]
    if refused:
        out.append(f"{len(refused)} refused")
    if r.get("stop") in ("limit", "error"):
        out.append(f"stopped: {r['stop']}")
    rc = r.get("reply_check")
    if rc and not rc["ok"]:
        out.append("reply check failed")
    return ", ".join(out)


def events(company, runs=(), lesson_events=(), lessons=None, versions=(), feedback=(), new_tools=(), reviews=()):
    """Every recorded event for one company, newest first: {ts, stream, what, who, detail, ref, raw}."""
    lessons = lessons or {}
    out = []
    for r in runs:
        if r.get("company") != company:
            continue
        n = sum(1 for s in r.get("trace", []) if s["type"] == "tool")
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
