"""Reference answers for hand-written benchmark questions, computed over the same records the agent reads: the
canonical tables of runtime/query.py's sandbox, which have the same names and columns for every company. The raw
file layout differs by company, so reading it directly would need a second SQL dialect the agent never sees.
The sandbox's own checks apply: one read-only SELECT over this company's tables, nothing else. No model is called."""

import tempfile
from pathlib import Path

from anubhav.runtime.company import CompanyData
from anubhav.runtime.query import QueryError, Sandbox, sandbox

MAX_ROWS = 100_000      # a reference answer must never be cut short silently
TIMEOUT_S = 30.0

_cache: dict[tuple[str, str], Sandbox] = {}
_tmp = None


def reference_sandbox(world, company) -> Sandbox:
    """One sandbox per (world, company), built on first use. The runtime store goes to a temporary folder, so the
    world's own files are only read."""
    global _tmp
    key = (str(Path(world).resolve()), company)
    if key not in _cache:
        if _tmp is None:
            _tmp = tempfile.TemporaryDirectory(prefix="anubhav_ref_", ignore_cleanup_errors=True)
        _cache[key] = sandbox(CompanyData(Path(world), company, Path(_tmp.name) / f"{len(_cache)}"))
    return _cache[key]


def run_reference_sql(world, company, sql):
    """Rows (tuples) of one read-only SELECT over the company's sandbox tables. Raises QueryError otherwise."""
    out = reference_sandbox(world, company).run(sql, max_rows=MAX_ROWS, timeout_s=TIMEOUT_S)
    if out["truncated"]:
        raise QueryError("LIMIT", f"more than {MAX_ROWS} rows; a reference answer must be small")
    return [tuple(r) for r in out["rows"]]
