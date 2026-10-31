"""Is everything ready to record or go live? Lists the models each key can use (no model is called, so no tokens are
spent) and checks the data, saved replays and spend caps. Reports problems by name: keys are never printed."""

import json

from . import muse
from .agents import registry
from .data.config import ROOT
from .service import session

URLS = {"spark": muse.BASE_URL, "open": muse.BASETEN_URL}
WANT = {"spark": muse.DEFAULT_MODEL, "open": muse.OPEN_MODEL}


def _list_models(key_name):
    client = muse.MuseClient(WANT[key_name], muse.key_for(key_name), URLS[key_name])
    return [m.id for m in client._client.models.list().data]


def check_model(key_name, list_models=_list_models):
    label = f"{key_name}: {WANT[key_name]}"
    try:
        ids = list_models(key_name)
    except muse.MissingKeyError:
        return label, False, f"{muse.KEYS[key_name]} is not set"
    except Exception as e:      # only the type: a provider's message could echo request details
        return label, False, f"could not list models ({type(e).__name__})"
    return label, WANT[key_name] in ids, "available" if WANT[key_name] in ids else "this key can't use it"


def check_local(world=None, bundle=None):
    world = world or session.WORLD
    bundle = bundle or session.DEMO / "replay_runs.jsonl"
    out = [("demo world", (world / "manifest.json").exists(), str(world.name))]
    rows = [json.loads(x) for x in bundle.read_text(encoding="utf-8").splitlines() if x.strip()] if bundle.exists() else []
    out.append(("saved replays", bool(rows), f"{len(rows)} runs in the bundle"))
    saved = {r["request"].strip() for r in rows}
    missing = [k for k, v in session.SUGGESTIONS.items() if v.strip() not in saved]
    out.append(("every suggestion replays", not missing, "all" if not missing else "missing: " + ", ".join(missing)))
    roster = registry.load()
    out.append(("agent team", bool(roster.lead()), f"{len(roster.active())} active, lead {roster.lead().agent_id}"))
    out.append(("API contract", (ROOT / "contracts" / "api.md").exists() and (ROOT / "contracts" / "events.schema.json").exists(), "contracts/"))
    left = session.Workspace(world=world).live_runs_left()
    out.append(("live runs left today", left > 0, f"{left} (caps: {session.LIVE_RUNS_PER_SESSION} a session, {session.LIVE_CALLS_PER_DAY} a day)"))
    return out


def run(models=("spark", "open"), list_models=_list_models, world=None, bundle=None):
    return [check_model(m, list_models) for m in models] + check_local(world, bundle)
