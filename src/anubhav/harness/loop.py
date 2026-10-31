"""Loop A: find where the agent used its tools or answered badly, let Muse propose one bounded harness patch,
test old vs new on the same requests, and only then let a person activate it.

Signals come from the agent's own traces (no human needed) and from tester feedback. The pass/fail gate is code;
the 'did it address the feedback' judgement is a separate Muse call shown as a diagnostic."""

import json
import re
from collections import Counter

from ..agent import graph
from ..runtime.broker import Broker, Session
from ..trace import walk
from .store import CATEGORIES

# ---------- 1. signals from traces (the agent's own experience)


def trace_issues(r):
    steps = [s for s in r.get("trace", []) if s["type"] == "tool"]
    out = []
    for s in steps:
        if not s["ok"]:
            code = s["error"]["code"]
            out.append({"kind": "tool_error", "tool": s["name"], "detail": f"{code}: {s['error']['message'][:120]}"})
    seen = Counter((s["name"], json.dumps(s.get("arguments"), sort_keys=True, default=str)) for s in steps)
    out += [{"kind": "repeated_call", "tool": n, "detail": f"called {c} times with the same arguments"}
            for (n, _), c in seen.items() if c > 1]
    if len(steps) > 8:
        out.append({"kind": "many_calls", "tool": None, "detail": f"{len(steps)} tool calls for one request"})
    if r.get("stop") == "limit":
        out.append({"kind": "limit_hit", "tool": None, "detail": "stopped at the step limit"})
    return out


def collect(runs, feedback, agent=None):
    """Group problems so the proposer sees patterns, with a few concrete examples each. With `agent`, only that
    agent's own steps count (feedback is on the reply, so it belongs to the lead)."""
    issues = Counter()
    examples = {}
    for r in (part for top in runs for part in walk(top)):
        if agent and (r.get("agent_id") or "planner") != agent:
            continue
        for i in trace_issues(r):
            k = (i["kind"], i["tool"])
            issues[k] += 1
            examples.setdefault(k, []).append({"request": r["request"], "detail": i["detail"]})
    return {"trace_issues": [{"kind": k, "tool": t, "count": n, "examples": examples[(k, t)][:3]}
                             for (k, t), n in issues.most_common(8)],
            "feedback": [{"id": f["feedback_id"], "category": CATEGORIES.get(f["category"], f["category"]),
                          "note": f["note"], "request": f["request"], "reply": (f["reply"] or "")[:700]}
                         for f in feedback if f["rating"] == 0 and agent in (None, "planner")][:8]}


# ---------- 2. Muse proposes one bounded patch

PROPOSE = """You improve how an AI dispatch agent works, not what it knows. The agent plans truck dispatch for a
transport company using tools; it answers planners in Roman Telugu, Telugu or English.

You may change ONLY these surfaces (one change per proposal):
- response_guidelines: short rules about how to answer (what to include, what to leave out, tone, grounding)
- tool_hints: one short hint appended to ONE tool's description (when/how to use it, argument tips, order)
- glossary: a language note (how planners say something, preferred words)
- routing_hints: which teammate or tool handled a kind of task well, only if the problems show evidence for it
Never put business facts (site names, towns, vehicles, vendors, rules about specific places) in a patch: those are
learned separately. Never weaken safety, permissions or validation.

Current harness:
{current}

Tools available:
{tools}

Problems seen (from the agent's own traces, and from a native-speaker tester):
{problems}

Propose the single change most likely to fix the most important problem without hurting anything else.
Reply with JSON only:
{{"surface": "response_guidelines|tool_hints|glossary|routing_hints", "op": "add|replace|remove", "tool": "<tool name if tool_hints>",
  "old": "<existing line if replace/remove>", "text": "<the new line>", "rationale": "<why>", "addresses": ["<feedback ids or issue kinds>"]}}"""


def propose(client, broker, current, problems, about_agent=""):
    tools = "\n".join(f"- {t.name}: {t.description}" for t in broker.list_tools())
    prompt = PROPOSE.format(current=json.dumps(current, ensure_ascii=False, indent=1), tools=tools,
                            problems=json.dumps(problems, ensure_ascii=False, indent=1))
    if about_agent:
        prompt = f"The change is for one agent of the team only: {about_agent}\n\n{prompt}"
    r = client.chat([{"role": "user", "content": prompt}], None, temperature=0)
    m = re.search(r"\{.*\}", r.content or "", re.S)
    patch = json.loads(m.group(0)) if m else {}
    return patch, {"cost_usd": r.cost_usd, "model": r.model}


# ---------- 3. paired test: same requests, old vs new harness


def run_case(C, client, case, surfaces, knowledge_for, runtime_reset=True):
    if runtime_reset:
        C.runtime.reset()
    knowledge, policies, advisories = knowledge_for(case["company"]) if case.get("use_lessons") else ([], [], [])
    b = Broker(C, Session(case["company"], "dispatcher", "harness-probe"), policies, advisories)
    return graph.run(b, client, case["request"], knowledge=knowledge, harness=surfaces)


def measure(r, C):
    parts = list(walk(r))
    steps = [s for p in parts for s in p["trace"] if s["type"] == "tool"]
    drafts = [s["result"] for s in steps if s["name"] == "create_dispatch_draft" and s["ok"]]
    errors = Counter()
    for p in parts:
        errors[p.get("agent_id") or "planner"] += sum(s["type"] == "tool" and not s["ok"] for s in p["trace"])
    return {"tool_calls": len(steps), "tool_errors": sum(not s["ok"] for s in steps), "errors_by_agent": dict(errors),
            "drafts": [(d["vehicle_id"], C.vehicles.get(d["vehicle_id"], {}).get("length_ft")) for d in drafts],
            "reply_chars": len(r["reply"] or ""), "cost_usd": r["cost_usd"], "stop": r["stop"]}


JUDGE = """A native-speaker tester gave this feedback on an AI agent's reply: "{note}" (category: {category}).
Here is a NEW reply to a similar request. Does the new reply address the feedback? Facts must still come from the data.
Request: {request}
New reply: {reply}
Answer JSON only: {{"addresses": true|false, "reason": "<short>"}}"""


def judge(client, fb, request, reply):
    r = client.chat([{"role": "user", "content": JUDGE.format(note=fb["note"], category=fb["category"], request=request,
                                                                reply=reply[:1500])}], None, temperature=0)
    m = re.search(r"\{.*\}", r.content or "", re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        out = {}
    return {"addresses": bool(out.get("addresses")), "reason": out.get("reason", ""), "cost_usd": r.cost_usd}


def gate(rows, judged, max_cost_ratio=1.3, agent=None):
    """Code decides: no lost drafts, no new tool errors, cost within limit, and the feedback is addressed more often.
    With `agent`, a change may not raise the errors of any other agent either, even if the total looks better."""
    lost = [x["request"] for x in rows if x["base"]["drafts"] and not x["cand"]["drafts"] and x["expects_draft"]]
    worse_errors = [x["request"] for x in rows if x["cand"]["tool_errors"] > x["base"]["tool_errors"]]
    bc, cc = sum(x["base"]["cost_usd"] for x in rows), sum(x["cand"]["cost_usd"] for x in rows)
    base_ok = sum(j["base"]["addresses"] for j in judged)
    cand_ok = sum(j["cand"]["addresses"] for j in judged)
    improves = (cand_ok > base_ok) if judged else (sum(x["cand"]["tool_errors"] for x in rows) < sum(x["base"]["tool_errors"] for x in rows))
    reasons = []
    if lost:
        reasons.append(f"lost drafts on {len(lost)} request(s)")
    if worse_errors:
        reasons.append(f"more tool errors on {len(worse_errors)} request(s)")
    if bc and cc > max_cost_ratio * bc:
        reasons.append(f"cost +{(cc / bc - 1):.0%}")
    if not improves:
        reasons.append("no measurable improvement on the problem")
    if agent:
        total = lambda side, who: sum(x[side]["errors_by_agent"].get(who, 0) for x in rows)
        others = {w for x in rows for side in ("base", "cand") for w in x[side]["errors_by_agent"]} - {agent}
        for who in sorted(others):
            if total("cand", who) > total("base", who):
                reasons.append(f"harms {who}: its tool errors went from {total('base', who)} to {total('cand', who)}")
    return {"pass": not reasons, "reasons": reasons, "feedback_addressed": {"base": base_ok, "cand": cand_ok, "of": len(judged)},
            "cost": {"base": round(bc, 4), "cand": round(cc, 4)}}


def probe(C, client, judge_client, cases, base, cand, feedback_by_id, knowledge_for):
    rows, judged = [], []
    for case in cases:
        rb = run_case(C, client, case, base, knowledge_for)
        rc = run_case(C, client, case, cand, knowledge_for)
        row = {"request": case["request"], "origin": case["origin"], "expects_draft": case.get("expects_draft", False),
               "base": measure(rb, C), "cand": measure(rc, C), "base_reply": rb["reply"], "cand_reply": rc["reply"],
               "base_run": rb["run_id"], "cand_run": rc["run_id"]}
        fb = feedback_by_id.get(case.get("feedback_id"))
        if fb:
            judged.append({"request": case["request"], "base": judge(judge_client, fb, case["request"], rb["reply"]),
                           "cand": judge(judge_client, fb, case["request"], rc["reply"])})
        rows.append(row)
    return {"rows": rows, "judged": judged, "gate": gate(rows, judged)}


def team_probe(C, client, judge_client, cases, agent, base, cand, feedback_by_id, knowledge_for, others=None):
    """The paired test for one agent's change: the same requests through the whole team, old vs new. `others` keeps every
    other agent on its active version, and the gate blocks a change that harms any of them."""
    from ..agents import team

    def one(case, surfaces):
        C.runtime.reset()
        knowledge, policies, advisories = knowledge_for(case["company"]) if case.get("use_lessons") else ([], [], [])
        by_agent = {**(others or {}), agent: surfaces}
        return team.run(C, Session(case["company"], "dispatcher", "harness-probe"), client, case["request"], knowledge=knowledge,
                        harness=by_agent.get("planner"), harnesses=by_agent, policies=policies, advisories=advisories)
    rows, judged = [], []
    for case in cases:
        rb, rc = one(case, base), one(case, cand)
        rows.append({"request": case["request"], "origin": case["origin"], "expects_draft": case.get("expects_draft", False),
                     "base": measure(rb, C), "cand": measure(rc, C), "base_reply": rb["reply"], "cand_reply": rc["reply"],
                     "base_run": rb["run_id"], "cand_run": rc["run_id"]})
        fb = feedback_by_id.get(case.get("feedback_id"))
        if fb:
            judged.append({"request": case["request"], "base": judge(judge_client, fb, case["request"], rb["reply"]),
                           "cand": judge(judge_client, fb, case["request"], rc["reply"])})
    return {"kind": "team", "agent": agent, "rows": rows, "judged": judged, "gate": gate(rows, judged, agent=agent)}
