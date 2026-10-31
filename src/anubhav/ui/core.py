"""The Streamlit side of the demo: this browser session's workspace, and the names the pages call. All the logic is in
service/ (no framework), which FastAPI uses too. Pages stay thin."""

import uuid

import streamlit as st

from .. import muse
from ..data.config import ROOT
from ..service import runs
from ..service.session import (COMPANIES, DEMO, EXP008, LIVE_CALLS_PER_DAY, LIVE_RUNS_PER_SESSION, MODELS, PUBLIC, SUGGESTIONS,
                               WORLD, Workspace, shared_company)
from ..service.session import ensure_world as _ensure_world
from ..service.session import harness_store as _harness_store
from ..service.views import args_of, drafts, lessons_used, summarize, tool_steps  # noqa: F401  (the pages' names)

__all__ = ["ROOT", "DEMO", "EXP008", "LIVE_CALLS_PER_DAY", "LIVE_RUNS_PER_SESSION", "COMPANIES", "MODELS", "SUGGESTIONS", "muse"]


def _sid():
    """This browser session's id. Locally the demo shares one store (it persists); hosted, every visitor gets their own."""
    return st.session_state.setdefault("sid", uuid.uuid4().hex[:12]) if PUBLIC else "shared"


def workspace() -> Workspace:
    return Workspace(_sid(), PUBLIC, st.session_state, WORLD)


@st.cache_resource
def ensure_world():
    return _ensure_world(WORLD)


def _company(cid: str):
    return shared_company(cid, WORLD)


def company(cid: str):
    return workspace().company(cid)


def store():
    return workspace().store()


def load_exp008_lessons():
    return workspace().load_exp008_lessons()


def clear_lessons():
    workspace().clear_lessons()


def harness_store():
    return _harness_store()


def active_harness():
    return harness_store().active()["surfaces"]


def knowledge_for(cid):
    return workspace().knowledge_for(cid)


def recent_runs(limit=60):
    return runs.recent_runs(limit)


def broker(cid: str, use_lessons: bool, role="dispatcher", user="demo"):
    return workspace().broker(cid, use_lessons, role, user)


def live_ready(model_key):
    return workspace().live_ready(model_key)


def live_client(model_key):
    return workspace().live_client(model_key)


def run_live(cid, request, model_key, use_lessons, history=()):
    return runs.run_live(workspace(), cid, request, model_key, use_lessons, history)


def about(cid):
    return workspace().about(cid)


def has_learned_tools(cid):
    return workspace().has_learned_tools(cid)


def find_replay(cid, request, use_lessons, learned=None):
    return runs.find_replay(workspace(), cid, request, use_lessons, learned)


def replayable(cid, use_lessons):
    return runs.replayable(workspace(), cid, use_lessons)
