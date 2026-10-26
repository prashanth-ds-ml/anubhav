"""SQLite business simulator: build, reset and connect."""

import sqlite3
from pathlib import Path

from .seed import seed

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "business.db"


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reset(path: Path = DEFAULT_DB) -> Path:
    """Rebuild the database from schema + deterministic seed. Every scenario starts here."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        seed(conn)
    conn.close()
    return path
