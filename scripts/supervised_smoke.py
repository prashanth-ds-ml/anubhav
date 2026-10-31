"""D-047 on a real model: does Muse Spark 1.3 ask, resume, take a sign-off and act on a rejection's notes? Not a benchmark:
a few requests to see the behaviour. Meta credits only, stops at BUDGET. Its traces stay in their own folder, so they can't
replace the saved demo replays. Writes artifacts/smoke_supervised.json.
  uv run python scripts/supervised_smoke.py
"""

import json
import sys

from anubhav import muse, trace
from anubhav.data.config import ROOT
from anubhav.service import runs
from anubhav.service.session import SUGGESTIONS, WORLD, Workspace

BUDGET = 1.50       # no new request starts past this; one team request is capped at $0.40
OUT = ROOT / "artifacts" / "smoke_supervised.json"


def summary(r):
    return {"run_id": r["run_id"], "request": r["request"][:120], "stop": r["stop"], "reply": r["reply"][:300], "drafts": r["drafts"], "cost_usd": r["cost_usd"],
            "tools": [s["name"] for s in r["trace"] if s["type"] == "tool"], "reply_refusals": sum(s["type"] == "reply_refused" for s in r["trace"]),
            "handoff_rule": (r.get("handoff") or {}).get("rule"), "reply_check_ok": r["reply_check"]["ok"], "resumed_from": r.get("resumed_from")}


def main():
    traces = ROOT / "data" / "traces_smoke"
    traces.mkdir(parents=True, exist_ok=True)
    trace.TRACE_DIR = traces
    trace.save.__defaults__ = (traces, "smoke")
    ws = Workspace(sid="smoke", public=True, world=WORLD)
    ws.company("T01").runtime.reset()
    client = muse.client("spark")
    out, spent = {"model": client.model, "scenarios": {}}, 0.0

    def ask(request, use_lessons=True, resume=None):
        nonlocal spent
        if spent >= BUDGET:
            raise SystemExit(f"budget reached (${spent:.2f})")
        r = runs.run_with(ws, client, "T01", request, use_lessons, team=True, resume=resume)
        spent += r["cost_usd"] + sum(c["cost_usd"] for c in r.get("children", []))
        return r

    def resume_of(r):
        from anubhav.service import checkpoints
        return {"run_id": r["run_id"], "state": checkpoints.get(r["run_id"], ws.sid)["state"]}

    # 1. an ambiguous request: does it ask, and does it carry on after the answer?
    first = ask(SUGGESTIONS["Ambiguous"])
    steps = [summary(first)]
    if first["stop"] == "needs_person":
        site = next(s["name"] for s in ws.company("T01").sites.values() if s["town"] == "Warangal")
        steps.append(summary(ask(f"{site}. Draft only.", resume=resume_of(first))))
    out["scenarios"]["ask_and_resume"] = steps

    # 2. a plan, signed off
    ws.company("T01").runtime.reset()
    plan = ask(SUGGESTIONS["English"])
    decided = []
    for d in plan["drafts"][:1]:
        ok, errors = runs.decide_draft(ws, "T01", d, "approve")
        decided.append({"draft": d, "ok": ok, "errors": errors, "status": ws.company("T01").runtime.draft(d)["status"]})
    out["scenarios"]["approve"] = {"run": summary(plan), "decided": decided}

    # 3. a plan, rejected with notes: does the agent act on them?
    ws.company("T01").runtime.reset()
    plan = ask(SUGGESTIONS["English"])
    step = {"run": summary(plan)}
    if plan["drafts"]:
        d = plan["drafts"][0]
        was = ws.company("T01").runtime.draft(d)["vehicle_id"]
        runs.decide_draft(ws, "T01", d, "reject", "Don't use this vehicle, it is needed elsewhere.")
        again = ask(f"The planner rejected draft {d}, and its vehicle hold is released. Their notes: Don't use this vehicle, it is needed elsewhere.\n"
                       "Make a new draft that fixes this, or ask them if it can't be fixed.", resume=resume_of(plan))
        new = [ws.company("T01").runtime.draft(x)["vehicle_id"] for x in again["drafts"]]
        step.update(revised=summary(again), old_vehicle=was, new_vehicles=new, followed_notes=bool(new) and was not in new)
    out["scenarios"]["reject_with_notes"] = step

    ws.company("T01").runtime.reset()
    out["total_usd"] = round(spent, 4)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
