"""Typed events (D-044, design v1 §4.5): one stream per request that says which agent acted, what it called, what came
back, where it retried, when no tool fitted, who handed what to whom, which lessons and checks were involved, and which
drafts were made. Built from a saved run (live or replay, single-Planner or team), stored in SQLite, read the same way
by the live stream and the history. The schema is contracts/events.schema.json.

An event is {run_id, seq, agent_id, caller, depth, ts, type, payload}; run_id is the request's (the lead agent's) id."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .data.config import ROOT

PATH = ROOT / "data" / "events.sqlite"
TYPES = ("agent_start", "tool_call", "tool_result", "retry", "tool_missing", "handoff", "lesson_used",
         "validator_check", "draft_created", "agent_done", "learning_event")
DRAFT_TOOLS = ("create_dispatch_draft", "create_dispatch_drafts", "check_load")
LESSON_KEYS = ("approved_policies", "advisories", "approved_rules", "advice")


def _short(x, n=600):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


def _lessons_in(result):
    """Approved lessons a tool result carried (site rules and advice), found anywhere in it."""
    found = []
    if isinstance(result, dict):
        for k, v in result.items():
            if k in LESSON_KEYS and v:
                found += v if isinstance(v, list) else [v]
            else:
                found += _lessons_in(v)
    elif isinstance(result, list):
        for v in result:
            found += _lessons_in(v)
    return found


class Emitter:
    """Turns agent steps into events, in order. Live, the agent loop calls it as each step happens (`sink` gets every
    event at once); afterwards from_run() walks a saved run through the same code, so both give the same stream."""

    def __init__(self, run_id, ts=None, sink=None):
        self.run_id, self.ts, self.sink = run_id, ts, sink
        self.events, self.stack = [], []

    def emit(self, type_, payload):
        c = self.stack[-1]
        e = {"run_id": self.run_id, "seq": len(self.events), "agent_id": c["agent_id"], "agent_run_id": c["agent_run_id"],
             "caller": c["caller"], "depth": c["depth"], "ts": self.ts, "type": type_, "payload": payload}
        self.events.append(e)
        if self.sink:
            self.sink(e)

    def agent_start(self, agent_id, agent_run_id, request, model, lessons):
        caller = self.stack[-1]["agent_id"] if self.stack else "person"
        self.stack.append({"agent_id": agent_id or "planner", "agent_run_id": agent_run_id, "caller": caller, "depth": len(self.stack)})
        self.emit("agent_start", {"request": request, "model": model, "lessons_in_prompt": lessons})

    def tool_call(self, name, args, attempt=1):
        args = json.loads(args) if isinstance(args, str) and args.strip().startswith("{") else args
        if 1 < attempt <= 3:            # a refused fourth attempt shows as its RETRY_LIMIT result
            self.emit("retry", {"tool": name, "attempt": attempt, "of": 3})
        self.emit("tool_call", {"tool": name, "arguments": args})

    def handoff(self, to, brief):
        self.emit("handoff", {"from": self.stack[-1]["agent_id"], "to": to, "brief": brief})

    def tool_result(self, s):
        res = s.get("result") or {}
        name = s["name"]
        self.emit("tool_result", {"tool": name, "ok": s["ok"], **({"result": _short(res)} if s["ok"] else {"error": s.get("error")})})
        if name == "find_capability" and s["ok"] and res.get("tool_missing"):
            self.emit("tool_missing", {"need": res.get("need"), "next_step": res.get("next_step")})
        if s["ok"]:
            lessons = _lessons_in(res)
            if lessons:
                self.emit("lesson_used", {"tool": name, "lessons": lessons[:10]})
        if name == "propose_lesson" and s["ok"] and res.get("lesson_id"):
            self.emit("learning_event", {"kind": "lesson", "agent": self.stack[-1]["agent_id"], "decision": "proposed", "ref": res["lesson_id"],
                                         "state": res.get("state"), "note": res.get("gate")})
        if name not in DRAFT_TOOLS:
            return
        if not s["ok"]:
            self.emit("validator_check", {"tool": name, "pass": False, "error": s.get("error")})
        elif name == "check_load":
            self.emit("validator_check", {"tool": name, "pass": bool(res.get("all_ok")), "checked": len(res.get("checked", []))})
        else:
            for d in [res] if name == "create_dispatch_draft" else res.get("results", []):
                if d.get("draft_id"):
                    self.emit("validator_check", {"tool": name, "pass": True, "draft_id": d["draft_id"]})
                    self.emit("draft_created", {"draft_id": d["draft_id"], "vehicle_id": d.get("vehicle_id"),
                                                "orders": d.get("orders"), "load": d.get("load")})
                else:
                    self.emit("validator_check", {"tool": name, "pass": False, "error": d.get("error") or d.get("errors")})

    def finish(self, s):
        for c in s.get("draft_checks", []):
            self.emit("validator_check", {"tool": "final_recheck", "pass": c["still_valid"], "draft_id": c["draft_id"], "errors": c["errors"]})

    def agent_done(self, r):
        self.emit("agent_done", {"reply": r.get("reply", ""), "stop": r.get("stop"), "cost_usd": r.get("cost_usd"),
                                 "tool_calls": r.get("tool_calls"), "drafts": r.get("drafts", []), "reply_check": r.get("reply_check")})
        self.stack.pop()


def from_run(run: dict) -> list[dict]:
    """All events of one request: the lead's run and, nested in place, each teammate run it delegated to."""
    children = {c["run_id"]: c for c in run.get("children", [])}
    em = Emitter(run["run_id"], run.get("saved_at"))

    def walk(r):
        em.agent_start(r.get("agent_id"), r["run_id"], r["request"], r.get("model"), len(r.get("knowledge") or []))
        for s in r["trace"]:
            if s["type"] == "tool":
                em.tool_call(s["name"], s.get("arguments"), s.get("attempt", 1))
                res = s.get("result") or {}
                if s["name"] == "delegate" and s["ok"]:
                    args = s.get("arguments")
                    args = json.loads(args) if isinstance(args, str) else (args or {})
                    em.handoff(res.get("agent"), args.get("brief", ""))
                    if res.get("run_id") in children:
                        walk(children[res["run_id"]])
                em.tool_result(s)
            elif s["type"] == "finish":
                em.finish(s)
        em.agent_done(r)

    walk(run)
    return em.events


class EventStore:
    def __init__(self, path: Path = PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.execute("create table if not exists events (run_id text, seq int, agent_id text, agent_run_id text, "
                        "caller text, depth int, ts text, type text, payload text, primary key (run_id, seq))")

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.path)        # closed every time (Windows keeps open files locked)
        try:
            with con:
                yield con
        finally:
            con.close()

    def save(self, events):
        with self._con() as con:
            con.executemany("insert or replace into events values (?,?,?,?,?,?,?,?,?)",
                            [(e["run_id"], e["seq"], e["agent_id"], e["agent_run_id"], e["caller"], e["depth"], e["ts"],
                              e["type"], json.dumps(e["payload"], ensure_ascii=False, default=str)) for e in events])

    def add_run(self, run):
        ev = from_run(run)
        self.save(ev)
        return ev

    def load(self, run_id, after=-1):
        """A request's events in order; `after` lets a reconnecting stream fetch only what it missed."""
        cols = ("run_id", "seq", "agent_id", "agent_run_id", "caller", "depth", "ts", "type", "payload")
        with self._con() as con:
            rows = con.execute("select * from events where run_id = ? and seq > ? order by seq", (run_id, after)).fetchall()
        return [dict(zip(cols, r[:-1]), payload=json.loads(r[-1])) for r in rows]

    def runs(self):
        with self._con() as con:
            return [r[0] for r in con.execute("select distinct run_id from events order by rowid desc")]
