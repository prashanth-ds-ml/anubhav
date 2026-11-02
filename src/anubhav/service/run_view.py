"""One saved run, laid out for a person to inspect: every event, the work each agent did, and each mistake an agent
fixed by itself. Everything here is read from the run's own record; nothing is scored or judged."""
from __future__ import annotations

from .. import events as run_events


def _n(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def agents_of(evts: list[dict]) -> list[dict]:
    """One row per agent turn, in the order they started: calls, failed calls and cost. A teammate's cost is inside its
    caller's total, so `own_cost_usd` takes the teammates' totals back out."""
    rows: dict[str, dict] = {}
    for e in evts:
        r = rows.setdefault(e["agent_run_id"], {"agent_run_id": e["agent_run_id"], "agent": e["agent_id"], "depth": e["depth"],
                                                "caller": e.get("caller") if e["depth"] else None, "model": None, "tool_calls": 0,
                                                "tool_errors": 0, "cost_usd": 0.0, "stop": None})
        p = e["payload"]
        if e["type"] == "agent_start":
            r["model"] = p.get("model")
        elif e["type"] == "tool_call":
            r["tool_calls"] += 1
        elif e["type"] == "tool_result" and not p.get("ok"):
            r["tool_errors"] += 1
        elif e["type"] == "agent_done":
            r["cost_usd"], r["stop"] = _n(p.get("cost_usd")), p.get("stop")
    out = list(rows.values())
    for r in out:
        kids = sum(k["cost_usd"] for k in out if k["caller"] == r["agent"] and k["depth"] == r["depth"] + 1)   # `caller` names the calling agent
        r["own_cost_usd"] = round(max(r["cost_usd"] - kids, 0.0), 5)
    return out


def fixes_of(evts: list[dict]) -> list[dict]:
    """A failed tool call, and the later call by the same agent turn to the same tool that worked: the agent read the
    error and fixed it itself. Each failure pairs with the first success after it; `step` counts tool calls in the run."""
    calls, step_of = [], {}
    for e in evts:
        if e["type"] == "tool_call":
            calls.append(e)
            step_of[e["seq"]] = len(calls)

    def call_before(res):        # the call this result answers: the latest earlier call to the same tool by the same turn
        for c in reversed(calls):
            if c["seq"] < res["seq"] and c["agent_run_id"] == res["agent_run_id"] and c["payload"].get("tool") == res["payload"].get("tool"):
                return c
        return None

    results = [e for e in evts if e["type"] == "tool_result"]
    out = []
    for i, bad in enumerate(results):
        if bad["payload"].get("ok"):
            continue
        good = next((r for r in results[i + 1:] if r["agent_run_id"] == bad["agent_run_id"] and r["payload"].get("tool") == bad["payload"].get("tool")
                     and r["payload"].get("ok")), None)
        cb, cg = call_before(bad), good and call_before(good)
        if not (good and cb and cg):
            continue
        out.append({"agent": bad["agent_id"], "tool": bad["payload"].get("tool"),
                    "failed": {"seq": bad["seq"], "step": step_of[cb["seq"]], "arguments": cb["payload"].get("arguments"), "error": bad["payload"].get("error")},
                    "fixed": {"seq": good["seq"], "step": step_of[cg["seq"]], "arguments": cg["payload"].get("arguments"), "result": good["payload"].get("result")}})
    return out


def run_view(run: dict) -> dict:
    evts = run_events.from_run(run)
    return {"run_id": run["run_id"], "label": run.get("label"), "request": run.get("request"), "reply": run.get("reply"), "model": run.get("model"),
            "saved_at": run.get("saved_at"), "mode": run.get("mode", "single"), "cost_usd": run.get("cost_usd"), "latency_s": run.get("latency_s"),
            "events": evts, "agents": agents_of(evts), "fixes": fixes_of(evts)}


def counts(run: dict) -> dict:
    """For the runs list: failed tool calls, and how many of them the agent fixed itself."""
    evts = run_events.from_run(run)
    return {"mistakes": sum(1 for e in evts if e["type"] == "tool_result" and not e["payload"].get("ok")), "fixed": len(fixes_of(evts))}
