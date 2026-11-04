"""EXP-022: EXP-021 again after its fix: approving an enforced rule now cancels the open drafts it forbids (service/fresh.py,
the lesson-decide route). Same protocol, bars and cap as EXP-021. A mini benchmark, pre-registered in
docs/trackers/experiments.md with these files frozen by hash before any model call.

The story (scenario S0, the demo video): a visitor starts from nothing, asks for tomorrow's Jangaon load in Roman Telugu,
lets Muse Spark 1.3 learn from the records, approves the gate rule the evidence gate holds, and asks again. EXP-020 checks
the team on a benchmark world; this checks the product on the hosted demo's own world (history through today), through
the same HTTP API the browser uses, in public mode with a fresh visitor each repeat. 3 repeats.

Pre-registered bars:
  B1 the Lakshmi Agencies gate rule (a site-access limit of 22 ft or less at that site) is proposed AND held by the
     evidence gate in at least 2 of 3 repeats
  B2 in every repeat where it was approved, the second plan drafts no truck longer than the rule allows (0 violations),
     and drafts one in at least 2 of 3 repeats overall
  B3 no run ends in a model error
Also reported, no bar: the truck the first plan chose, whether the second reply names the rule, cost and time.
Budget cap $3 (Meta). Results are reported whichever way they go.

  uv run python scripts/exp022_demo_story_fixed.py --freeze
  uv run python scripts/exp022_demo_story_fixed.py
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

STATE = Path(tempfile.mkdtemp(prefix="exp022_state_"))
os.environ.update({"ANUBHAV_PUBLIC": "1", "ANUBHAV_START_FRESH": "1", "ANUBHAV_WORLD_END": "today", "ANUBHAV_STATE_DIR": str(STATE)})

from fastapi.testclient import TestClient  # noqa: E402

from anubhav.api.app import create_app  # noqa: E402
from anubhav.data.config import ROOT  # noqa: E402
from anubhav.runtime.company import CompanyData  # noqa: E402
from anubhav.trace import walk  # noqa: E402

OUT = ROOT / "artifacts" / "benchmark"
TAG = "exp022"
FROZEN = OUT / f"{TAG}_frozen.json"
BUDGET_USD = 3.0
REPEATS = 3
REQUEST = "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku."     # the S0 / video request
FILES = ["scripts/exp022_demo_story_fixed.py", "configs/agents.yaml", "src/anubhav/api/routes.py", "src/anubhav/service/fresh.py",
         "src/anubhav/service/runs.py", "src/anubhav/service/stream.py", "src/anubhav/service/session.py", "src/anubhav/learning/miner.py",
         "src/anubhav/learning/gate.py", "src/anubhav/agent/graph.py", "src/anubhav/agents/team.py", "src/anubhav/runtime/broker.py"]


def hashes():
    return {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] for f in FILES}


def drafted_trucks(r):
    """Vehicle ids this run drafted (single and batch drafts), from its tool calls that succeeded."""
    out = []
    for p in walk(r):
        for s in p["trace"]:
            if s["type"] != "tool" or not s.get("ok") or s["name"] not in ("create_dispatch_draft", "create_dispatch_drafts"):
                continue
            args = json.loads(s["arguments"]) if isinstance(s["arguments"], str) else s["arguments"]
            items = args.get("items") or args.get("drafts") or [args]
            out += [i["vehicle_id"] for i in items if isinstance(i, dict) and i.get("vehicle_id")]
    return out


def ask(c, headers):
    t0 = time.time()
    res = c.post("/api/chat", json={"company": "T01", "message": REQUEST, "mode": "live", "model": "spark", "use_lessons": True, "team": True},
                 headers=headers)
    res.raise_for_status()
    body = res.json()
    if body.get("mode") != "live":
        raise SystemExit(f"not a live run: {body}")
    run_id = body["run_id"]
    while time.time() - t0 < 600:
        r = c.get(f"/api/runs/{run_id}", headers=headers)
        if r.status_code == 200 and r.json().get("stop") is not None and "reply" in r.json():
            return r.json(), round(time.time() - t0, 1)
        time.sleep(3)
    raise SystemExit(f"run {run_id} did not finish in 10 minutes")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        FROZEN.write_text(json.dumps({"hashes": hashes(), "repeats": REPEATS, "budget_usd": BUDGET_USD, "request": REQUEST,
                                      "frozen_at": datetime.now().isoformat(timespec="seconds")}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(FROZEN.read_text(encoding="utf-8"))
        return 0
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    changed = [f for f, h in hashes().items() if frozen["hashes"].get(f) != h]
    if changed:
        raise SystemExit(f"refusing to run: frozen files changed: {changed}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    app = create_app(public=True, start_fresh=True, replay_pace=0)
    C = CompanyData(app.state.world, "T01", Path(tempfile.mkdtemp()))
    length = lambda v: C.vehicles[v]["length_ft"]
    print(f"world {app.state.world.name}, state {STATE}", flush=True)
    rows, spent = [], 0.0
    with TestClient(app) as c:
        for rep in range(REPEATS):
            h = {"X-Anubhav-Visitor": uuid.uuid4().hex[:12]}      # the server accepts only 12 hex characters
            c.post("/api/fresh/mode?company=T01&mode=fresh", headers=h).raise_for_status()
            c.post("/api/fresh/reset?company=T01", headers=h).raise_for_status()
            first, t1 = ask(c, h)
            learned = c.post("/api/fresh/learn?company=T01&model=spark", headers=h)
            learned.raise_for_status()
            learned = learned.json()
            lessons = c.get("/api/learning/lessons?company=T01", headers=h).json()
            gate = [l for l in lessons if l["kind"] == "site_access" and (l.get("params") or {}).get("max_length_ft") is not None
                    and C.sites.get(l["params"].get("site_id"), {}).get("name") == "Lakshmi Agencies"]
            held = [l for l in gate if l["state"] == "CANDIDATE"]
            approved = None
            if held:
                approved = held[0]
                c.post(f"/api/learning/lessons/{approved['lesson_id']}/decide?company=T01",
                       json={"decision": "approve", "effect": "policy", "verified": "EXP-022: the gate held it"}, headers=h).raise_for_status()
            second, t2 = ask(c, h)
            limit = approved["params"]["max_length_ft"] if approved else None
            t_first, t_second = drafted_trucks(first), drafted_trucks(second)
            row = {"repeat": rep + 1, "visitor": h["X-Anubhav-Visitor"],
                   "first": {"run_id": first["run_id"], "trucks": t_first, "lengths": [length(v) for v in t_first], "stop": first["stop"],
                             "cost_usd": first["cost_usd"], "seconds": t1, "reply": first["reply"][:400]},
                   "learn": {"counts": learned.get("counts"), "cost_usd": learned.get("cost_usd"), "gate_rule_proposed": bool(gate),
                             "gate_rule_held": bool(held), "rule": approved and {"lesson_id": approved["lesson_id"], "params": approved["params"], "display": approved.get("display")}},
                   "second": {"run_id": second["run_id"], "trucks": t_second, "lengths": [length(v) for v in t_second], "stop": second["stop"],
                              "cost_usd": second["cost_usd"], "seconds": t2, "reply": second["reply"][:600],
                              "violations": [v for v in t_second if limit is not None and length(v) > limit],
                              "names_rule": bool(approved) and (approved["lesson_id"] in second["reply"] or f"{limit} ft" in second["reply"] or f"{limit}ft" in second["reply"])}}
            rows.append(row)
            spent += first["cost_usd"] + (learned.get("cost_usd") or 0) + second["cost_usd"]
            print(json.dumps({k: row[k] for k in ("repeat",)} | {"first_lengths": row["first"]["lengths"], "held": row["learn"]["gate_rule_held"],
                              "second_lengths": row["second"]["lengths"], "violations": row["second"]["violations"], "spent": round(spent, 3)}), flush=True)
            if spent >= BUDGET_USD:
                print(f"cap of ${BUDGET_USD} reached: results are partial", flush=True)
                break
    held_n = sum(r["learn"]["gate_rule_held"] for r in rows)
    decision = {"repeats": len(rows), "gate_rule_held": held_n,
                "B1_rule_found_and_held": held_n >= 2,
                "B2_no_violation_and_drafts": all(not r["second"]["violations"] for r in rows) and sum(bool(r["second"]["trucks"]) for r in rows) >= 2,
                "B3_no_model_error": all(r["first"]["stop"] != "error" and r["second"]["stop"] != "error" for r in rows),
                "first_plan_lengths": [r["first"]["lengths"] for r in rows], "second_plan_lengths": [r["second"]["lengths"] for r in rows],
                "second_names_rule": sum(r["second"]["names_rule"] for r in rows), "cost_usd": round(spent, 3)}
    decision["met"] = decision["B1_rule_found_and_held"] and decision["B2_no_violation_and_drafts"] and decision["B3_no_model_error"]
    p = OUT / f"{TAG}_{stamp}.json"
    p.write_text(json.dumps({"world": app.state.world.name, "frozen": frozen, "decision": decision, "rows": rows}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(decision, indent=1))
    print("saved", p.relative_to(ROOT), "total $", round(spent, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
