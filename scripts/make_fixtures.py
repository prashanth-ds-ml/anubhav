"""Event-stream fixtures for the web app (contracts/api.md): one event per line, valid against
contracts/events.schema.json. No credits.

1. plain_plan.jsonl          a real saved Muse Spark Open run from the demo bundle (T01 with its lessons, Roman Telugu)
2. handoff_analyst.jsonl     Planner -> Analyst -> read-only query -> answer, in multi-agent mode
3. retry_tool_missing.jsonl  no tool fits (tool_missing) -> Tool Forge -> a query fails, is fixed, and answers (retry)

2 and 3 run the real loop, broker, sandbox and validator with a scripted model in place of Muse (labelled
"mock (scripted fixture)" in each agent_start); their SQL is what the agent wrote in the real run cd7dc7c3c0.

  uv run python scripts/make_fixtures.py
"""

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

from anubhav import events
from anubhav.agents import team
from anubhav.data.config import ROOT
from anubhav.muse import MockClient, mock_final, mock_tool_call
from anubhav.runtime.broker import Session
from anubhav.runtime.company import CompanyData

WORLD = ROOT / "data" / "worlds" / "full_seed20261104"
OUT = ROOT / "web" / "fixtures"
MODEL = "mock (scripted fixture)"
REQUEST = "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?"
BRIEF = ("In Hanamkonda, on which weekday do we make the most delivery stops? Count delivery stops by weekday over all "
         "past trips and return the counts and the busiest day.")
STOPS_SQL = ("SELECT CASE strftime('%w', sh.delivery_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN "
             "'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday' "
             "END AS weekday, COUNT(*) AS stops, COUNT(DISTINCT sh.delivery_date) AS distinct_days FROM trip_outcomes t "
             "JOIN shipments sh ON t.shipment_id = sh.shipment_id JOIN sites s ON t.site_id = s.site_id "
             "WHERE s.town = 'Hanamkonda' GROUP BY strftime('%w', sh.delivery_date) ORDER BY stops DESC")
WRONG_SQL = ("SELECT strftime('%w', t.delivery_date) AS wnum, COUNT(*) AS stops FROM trip_outcomes t "
             "JOIN sites s ON t.site_id = s.site_id WHERE s.town = 'Hanamkonda' GROUP BY wnum ORDER BY stops DESC")


def query(sql, purpose, cid):
    return mock_tool_call("run_query", {"sql": sql, "purpose": purpose}, call_id=cid)


def team_run(C, script):
    return team.run(C, Session("T01", "dispatcher", "fixture"), MockClient(script, model=MODEL), REQUEST)


def answer_from(rows):
    return lambda msgs, tools: mock_final(rows(msgs))


def busiest(msgs):
    res = json.loads(msgs[-1]["content"])["result"]
    top = res["rows"][0]
    return f"Hanamkonda: most delivery stops on {top[0]} ({top[1]} stops on {top[2]} days). Query: {STOPS_SQL}"


def relay(msgs):
    reply = json.loads(msgs[-1]["content"])["result"]["reply"]
    day = reply.split("on ")[1].split(" (")[0]
    return f"Hanamkonda lo manam ekkuva deliveries {day} roju chestham (records nunchi count chesamu)."


def main():
    if not WORLD.exists():
        sys.exit(f"no world at {WORLD}: run `uv run python -m anubhav.data.generate --full` first")
    schema = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))
    runs = {}
    plain = next(json.loads(x) for x in (ROOT / "demo" / "replay_runs.jsonl").read_text(encoding="utf-8").splitlines()
                 if x.strip() and json.loads(x)["run_id"] == "f2691258ee")
    runs["plain_plan"] = plain
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        C = CompanyData(WORLD, "T01", Path(tmp) / "rt")
        runs["handoff_analyst"] = team_run(C, [
            mock_tool_call("delegate", {"agent": "analyst", "brief": BRIEF}, call_id="d1"),
            mock_tool_call("describe_tables", {}, call_id="a1"),
            query(STOPS_SQL, "delivery stops by weekday in Hanamkonda", "a2"),
            answer_from(busiest),
            answer_from(relay)])
        runs["retry_tool_missing"] = team_run(C, [
            mock_tool_call("find_capability", {"need": "busiest weekday"}, call_id="f1"),
            mock_tool_call("delegate", {"agent": "tool_forge", "brief": BRIEF}, call_id="d1"),
            query(WRONG_SQL, "weekday stops Hanamkonda", "a1"),
            query(WRONG_SQL.replace("t.delivery_date", "t.date"), "weekday stops Hanamkonda", "a2"),
            query(STOPS_SQL, "weekday stops via shipments", "a3"),
            answer_from(busiest),
            answer_from(relay)])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, run in runs.items():
        ev = events.from_run(run)
        for e in ev:
            jsonschema.validate(e, schema)
        types = [e["type"] for e in ev]
        (OUT / f"{name}.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in ev), encoding="utf-8")
        print(f"{name}: {len(ev)} events, agents {sorted({e['agent_id'] for e in ev})}, "
              f"{', '.join(t for t in events.TYPES if t in types)}")
    must = {"handoff_analyst": {"handoff"}, "retry_tool_missing": {"handoff", "retry", "tool_missing"},
            "plain_plan": {"draft_created", "lesson_used"}}
    for name, need in must.items():
        got = {json.loads(x)["type"] for x in (OUT / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()}
        assert need <= got, (name, need - got)
    return 0


if __name__ == "__main__":
    sys.exit(main())
