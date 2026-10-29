"""Shared helpers for the Streamlit demo: one place that loads company data, the lesson store and saved traces,
runs the agent (live or replay), and turns a trace into something a person can read. Pages stay thin."""

import json
import shutil
from pathlib import Path

import streamlit as st

from .. import muse, trace
from ..agent import graph
from ..data.config import ROOT
from ..harness.store import HarnessStore
from ..learning.store import LessonStore
from ..runtime.broker import Broker, Session
from ..runtime.company import CompanyData

WORLD = ROOT / "data" / "worlds" / "full_seed20261104"
EXP008 = sorted((ROOT / "artifacts" / "learning").glob("exp008_*_rep0.sqlite"))
COMPANIES = {"T01": "Sri Kakatiya Logistics", "T02": "Ramappa Carriers", "T03": "Deccan Freight Services",
             "TNEW": "Bhadrakali Transport Co (new)"}
MODELS = {"Replay (free)": None, "Muse Spark Open": "open", "Muse Spark 1.3": "spark"}
SUGGESTIONS = {
    "Roman Telugu": "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku.",
    "Telugu": "రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు. డిస్పాచ్ కన్ఫర్మ్ చేయకు.",
    "English": "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only, don't dispatch.",
    "Mixed": "Jangaon Lakshmi order ki suitable vehicle choose chesi draft create cheyyi, confirm cheyyaku.",
    "Nickname": "Pedda godown load ki bandi pettu.",
    "Ambiguous": "Warangal load ki bandi pettu.",
}


@st.cache_resource(max_entries=8)
def company(cid: str) -> CompanyData:
    return CompanyData(WORLD, cid, WORLD / "runtime" / "ui")


@st.cache_resource
def store() -> LessonStore:
    return LessonStore(WORLD / "learning" / "demo.sqlite")


def load_exp008_lessons():
    """Copy the EXP-008 lesson store (mined by Muse, approved by the fixed review rule) into the demo store."""
    if not EXP008:
        return False
    st.cache_resource.clear()
    shutil.copy(EXP008[-1], WORLD / "learning" / "demo.sqlite")
    return True


def clear_lessons():
    st.cache_resource.clear()
    p = WORLD / "learning" / "demo.sqlite"
    if p.exists():
        p.unlink()


@st.cache_resource
def harness_store() -> HarnessStore:
    """One harness for every client: how the agent works is shared; what it knows stays per company."""
    return HarnessStore(ROOT / "data" / "harness" / "harness.sqlite")


def active_harness():
    return harness_store().active()["surfaces"]


def knowledge_for(cid):
    return store().active_for(cid, company(cid))


def recent_runs(limit=60):
    rows = []
    for p in sorted(trace.TRACE_DIR.glob("*.jsonl"), reverse=True):
        rows += [json.loads(x) for x in reversed(p.read_text(encoding="utf-8").splitlines())]
        if len(rows) >= limit:
            break
    return rows[:limit]


def broker(cid: str, use_lessons: bool, role="dispatcher", user="demo"):
    C = company(cid)
    knowledge, policies, advisories = store().active_for(cid, C) if use_lessons else ([], [], [])
    return Broker(C, Session(cid, role, user), policies, advisories), knowledge


def run_live(cid, request, model_key, use_lessons, history=()):
    b, knowledge = broker(cid, use_lessons)
    turns = []
    for h in list(history)[-6:]:                 # the last few exchanges, so follow-ups make sense
        turns += [{"role": "user", "content": h["request"]}, {"role": "assistant", "content": h["run"]["reply"]}]
    r = graph.run(b, muse.client(model_key), request, knowledge=knowledge, harness=active_harness(), history=turns)
    trace.save(r, label=f"ui:{cid}:{'lessons' if use_lessons else 'cold'}")
    return r


def find_replay(cid, request, use_lessons):
    """The newest saved real run with the same company, request and knowledge setting."""
    for p in sorted(trace.TRACE_DIR.glob("*.jsonl"), reverse=True):
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            r = json.loads(line)
            if r["company"] == cid and r["request"].strip() == request.strip() and bool(r.get("knowledge")) == use_lessons:
                return r
    return None


def replayable(cid, use_lessons):
    return [label for label, req in SUGGESTIONS.items() if find_replay(cid, req, use_lessons)]


def tool_steps(r):
    return [s for s in r["trace"] if s["type"] == "tool"]


def args_of(step):
    a = step["arguments"]
    return json.loads(a) if isinstance(a, str) else (a or {})


def summarize(step):
    """One readable line per tool result."""
    if not step["ok"]:
        return f"✗ {step['error']['code']}: {step['error']['message'][:120]}"
    res = step.get("result") or {}
    name = step["name"]
    if name == "find_site":
        m = res.get("matches", [])
        return ", ".join(f"{x['name']} ({x['town']})" for x in m[:3]) or "no match"
    if name == "list_open_orders":
        return f"{len(res.get('orders', []))} open orders"
    if name == "list_vehicles":
        return f"{len(res.get('vehicles', []))} vehicles"
    if name == "get_site_constraints":
        extra = ""
        if res.get("approved_policies"):
            extra = " · approved rule: " + "; ".join(p["rule"] for p in res["approved_policies"])
        if res.get("advisories"):
            extra += " · advice: " + "; ".join(a["text"] for a in res["advisories"])
        return f"site master: {res.get('recorded_in_site_master')}{extra}"
    if name == "create_dispatch_draft":
        return f"draft {res.get('draft_id')} · {res.get('vehicle_id')} · {res.get('load', {}).get('kg')} kg"
    if name == "check_vehicle_availability":
        return "free" if res.get("available") else f"not free ({res.get('status')}, held={res.get('held_by_draft')})"
    if name == "get_route_info":
        return f"{res.get('road_km_from_depot')} km · ~{res.get('drive_minutes')} min"
    return json.dumps(res, ensure_ascii=False, default=str)[:140]


def drafts(r):
    """Drafts created in a run, read from its trace (works for live runs and replays alike)."""
    out = []
    for s in tool_steps(r):
        if s["name"] == "create_dispatch_draft" and s["ok"]:
            out.append(s["result"])
        if s["name"] == "cancel_dispatch_draft" and s["ok"]:
            out = [d for d in out if d["draft_id"] != (s.get("result") or {}).get("draft_id")]
    return out


def lessons_used(r):
    used = []
    text = r.get("reply", "")
    for k in r.get("knowledge", []):
        lid = k.rsplit("[", 1)[-1].rstrip("]").split()[-1] if "[" in k else ""
        if lid and lid in text:
            used.append(k)
    return used
