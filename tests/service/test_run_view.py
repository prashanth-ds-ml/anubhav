"""The run view reads a run's own events: a failed call fixed by a later call to the same tool, and costs per agent."""
from anubhav.service.run_view import agents_of, fixes_of


def ev(seq, type_, agent="planner", run="r1", depth=0, caller=None, **payload):
    return {"seq": seq, "type": type_, "agent_id": agent, "agent_run_id": run, "depth": depth, "caller": caller, "payload": payload}


RUN = [
    ev(0, "agent_start", model="m"),
    ev(1, "tool_call", tool="describe_tables", arguments={}),
    ev(2, "tool_result", tool="describe_tables", ok=True, result="{}"),
    ev(3, "tool_call", tool="run_query", arguments={"sql": "select t.x"}),
    ev(4, "tool_result", tool="run_query", ok=False, error={"code": "BAD_ARGS", "message": "SQL error: no such column: x"}),
    ev(5, "tool_call", tool="delegate", arguments={"agent": "tool_forge"}),
    ev(6, "agent_start", agent="tool_forge", run="r2", depth=1, caller="planner", model="m"),
    ev(7, "tool_call", agent="tool_forge", run="r2", depth=1, caller="planner", tool="run_query", arguments={"sql": "select y"}),
    ev(8, "tool_result", agent="tool_forge", run="r2", depth=1, caller="planner", tool="run_query", ok=True, result="ok"),   # another agent: not a fix
    ev(9, "agent_done", agent="tool_forge", run="r2", depth=1, caller="planner", cost_usd=0.08, stop="answered"),
    ev(10, "tool_result", tool="delegate", ok=True, result="{}"),
    ev(11, "tool_call", tool="run_query", arguments={"sql": "select sh.x"}),
    ev(12, "tool_result", tool="run_query", ok=True, result="rows"),
    ev(13, "agent_done", cost_usd=0.11, stop="answered"),
]


def test_a_failure_pairs_with_the_same_agents_next_success_on_that_tool():
    (f,) = fixes_of(RUN)
    assert f["agent"] == "planner" and f["tool"] == "run_query"
    assert f["failed"]["step"] == 2 and f["failed"]["arguments"] == {"sql": "select t.x"} and "no such column" in f["failed"]["error"]["message"]
    assert f["fixed"]["step"] == 5 and f["fixed"]["arguments"] == {"sql": "select sh.x"} and f["fixed"]["result"] == "rows"


def test_a_failure_never_fixed_is_not_a_pair():
    assert fixes_of(RUN[:5]) == []


def test_each_agent_has_its_calls_errors_and_own_cost():
    planner, forge = agents_of(RUN)
    assert (planner["agent"], planner["tool_calls"], planner["tool_errors"]) == ("planner", 4, 1)
    assert (forge["agent"], forge["tool_calls"], forge["caller"]) == ("tool_forge", 1, "planner")
    assert planner["cost_usd"] == 0.11 and planner["own_cost_usd"] == 0.03 and forge["own_cost_usd"] == 0.08
