"""Load the world config, hash it, and hand out independent random substreams."""

import hashlib
import json
import random
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
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
