"""Load the world config, hash it, and hand out independent random substreams."""

import os
import hashlib
import json
import random
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("ANUBHAV_HOME") or Path(__file__).resolve().parents[3])    # configs/ and data/ live here, not in the package


def _state_dir():
    """Where state that must outlive a redeploy is written (runs, visitors' workspaces and drafts, spend counters,
    agent versions): ANUBHAV_STATE_DIR, e.g. a Hugging Face Space's persistent disk at /data. Unset, or not writable
    (storage not enabled yet), everything stays where it always was."""
    p = os.environ.get("ANUBHAV_STATE_DIR")
    if not p:
        return None
    try:
        Path(p).mkdir(parents=True, exist_ok=True)
        probe = Path(p) / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return Path(p)
    except OSError as e:
        import logging
        logging.getLogger("anubhav").warning("ANUBHAV_STATE_DIR=%s is not writable (%s); keeping state in the image", p, e)
        return None


STATE = _state_dir()        # None: state lives under data/ and the world folder, as before
DEFAULT_CONFIG = ROOT / "configs" / "world_v1.yaml"
SUBSTREAMS = ("geography", "demand", "resources", "disruptions", "people", "notes", "benchmark")


def load(path=DEFAULT_CONFIG, **overrides):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg.update(overrides)
    return cfg


def config_hash(cfg) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()


def rng(cfg, stream: str, *keys) -> random.Random:
    """A random generator for one substream (and optional sub-keys such as a company and a day).
    Streams never share state, so changing how notes are written can't change which trips happen."""
    if stream not in SUBSTREAMS:
        raise ValueError(f"unknown substream {stream}")
    return random.Random(":".join(str(k) for k in (cfg["master_seed"], stream, *keys)))


def as_date(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x))
