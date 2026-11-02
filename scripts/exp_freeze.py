"""Freeze an experiment's files by hash before its first model call, and refuse to run if one has changed since (D-044).

The agent, the tools, the checks, the scoring and the model client are frozen for every experiment that uses this, plus the
experiment's own script. The hashes are written to artifacts/benchmark/<tag>_frozen.json and committed with the pre-registration.
"""

import hashlib
import json
import sys

from anubhav.data.config import ROOT

CORE = ["configs/agents.yaml", "src/anubhav/agent/graph.py", "src/anubhav/agents/team.py", "src/anubhav/agents/forge.py",
        "src/anubhav/agents/registry.py", "src/anubhav/runtime/broker.py", "src/anubhav/runtime/safety.py", "src/anubhav/muse.py",
        "src/anubhav/eval/bench.py", "src/anubhav/harness/practice.py", "src/anubhav/learning/newtools.py", "src/anubhav/learning/gate.py",
        "src/anubhav/learning/pack.py", "src/anubhav/service/knowledge.py"]


def hashes(script: str) -> dict:
    return {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] for f in [script, *CORE]}


def path(tag: str):
    return ROOT / "artifacts" / "benchmark" / f"{tag}_frozen.json"


def freeze(tag: str, script: str) -> dict:
    h = hashes(script)
    path(tag).write_text(json.dumps(h, indent=1) + "\n", encoding="utf-8")
    return h


def check(tag: str, script: str) -> None:
    """Exit unless every frozen file is unchanged."""
    p = path(tag)
    if not p.exists():
        sys.exit(f"refusing to run: {p.name} is missing; pre-register and freeze first")
    frozen = json.loads(p.read_text(encoding="utf-8"))
    changed = [f for f, h in hashes(script).items() if frozen.get(f) != h]
    if changed:
        sys.exit(f"refusing to run: frozen files changed: {changed}")
