"""Is everything ready to record or go live? Lists the models each key can use (no model is called, so no tokens are
spent) and checks the data, saved replays and spend caps. Reports problems by name: keys are never printed."""

import json
import re

from . import muse
from .agents import registry
from .data.config import ROOT
from .service import session

URLS = {"spark": muse.BASE_URL, "open": muse.BASETEN_URL}
WANT = {"spark": muse.DEFAULT_MODEL, "open": muse.OPEN_MODEL}
LEDGER = ROOT / "docs" / "trackers" / "cost_ledger.md"
RESERVE = {"Meta Model API": 50.0, "Baseten": 30.0}     # kept for the demo and the judges (D-048); our own use is on Meta only
OURS = {"Meta Model API"}


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


def check_credits(ledger=LEDGER, reserve=RESERVE):
    """Credit left against what's kept for the demo, from our own ledger (the billing pages are the real figure)."""
    text = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
    out = []
    for name, floor in reserve.items():
        m = re.search(rf"^\| {re.escape(name)} \|[^|]*\|[^|]*\| ~?([\d.]+) \|", text, re.M)
        if not m:
            out.append((f"credit: {name}", False, "not found in the ledger"))
            continue
        left = float(m.group(1))
        free = f", ~${max(left - floor, 0):.2f} free for our own runs" if name in OURS else ", none for our own runs"
        out.append((f"credit: {name}", left >= floor, f"~${left:.2f} left, keep ${floor:.2f} for the demo and judges{free}"))
    return out


def run(models=("spark", "open"), list_models=_list_models, world=None, bundle=None):
    return [check_model(m, list_models) for m in models] + check_local(world, bundle) + check_credits()


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Check everything before recording or going live. Lists models only: no tokens are spent.")
    ap.add_argument("--replay-only", action="store_true", help="skip the model keys (a host with none)")
    a = ap.parse_args(argv)
    rows = run(models=() if a.replay_only else ("spark", "open"))
    for name, ok, detail in rows:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    return 0 if all(ok for _, ok, _ in rows) else 1
