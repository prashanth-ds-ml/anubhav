"""Read-only query sandbox (D-040). When no tool fits, the agent may answer with ONE SQL SELECT over an in-memory copy of
its own company's records. What it can reach and do is decided here, by code:
- only this company's canonical tables (CompanyData.t): never another company, the hidden truth, the runtime store
  (drafts, holds, audit) or any file;
- SELECT only: the connection is query_only and an authorizer denies everything except reading and plain functions
  (no ATTACH, PRAGMA, writes, temp tables or load_extension);
- a time limit (progress handler), a row limit and a length limit on the SQL;
- columns of free text written by people are found from the data (long, sentence-like text) and the result is marked
  untrusted when it read one: it is information, never an instruction.
The schema shown to the model is generated from the data, so nothing about the business is written here (D-034)."""

import json
import re
import sqlite3
import statistics
import threading
import time

MAX_SQL = 4000
MAX_ROWS = 200
TIMEOUT_S = 2.0
UNTRUSTED = "untrusted_text"

_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class QueryError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _type(values):
    vs = [v for v in values if v is not None]
    if vs and all(isinstance(v, bool) or isinstance(v, int) for v in vs):
        return "INTEGER"
    if vs and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vs):
        return "REAL"
    return "TEXT"


def _free_text(values):
    """People's free text: most values contain spaces and they are long. Measured, not listed."""
    vs = [v for v in values if isinstance(v, str) and v]
    if len(vs) < 3:
        return False
    return statistics.median(len(v) for v in vs) >= 25 and sum(" " in v for v in vs) >= 0.6 * len(vs)


def _one_shape(values):
    """Names or ids of one kind look alike ("Jangaon", "C0001"); a change log of mixed values ("22:00", "Tuesday",
    "night_only") does not. Shape = letters → a, digits → 9, runs collapsed."""
    shape = lambda v: re.sub(r"(a)a+|(9)9+", r"", re.sub(r"[^\W\d_]", "a", re.sub(r"\d", "9", v)))
    counts = {}
    for v in values:
        counts[shape(v)] = counts.get(shape(v), 0) + 1
    return max(counts.values()) >= 0.7 * len(values)


class Sandbox:
    """One company's records in memory. Build once per CompanyData; every query gets a fresh read-only cursor."""

    def __init__(self, C):
        self.company = C.company
        self.con = sqlite3.connect(":memory:", check_same_thread=False)
        self.tables, self.untrusted = {}, set()
        self.date_range = None
        self.entities, rank = {}, {}        # value -> "table.column" for columns of many distinct names/ids (towns, sites, vehicles…)
        for name, rows in sorted(C.t.items()):
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict) or not re.fullmatch(r"\w+", name):
                continue
            cols = list(dict.fromkeys(k for r in rows for k in r if re.fullmatch(r"\w+", k)))
            types = {c: _type([r.get(c) for r in rows]) for c in cols}
            self.con.execute(f'create table "{name}" ({", ".join(f"{chr(34)}{c}{chr(34)} {types[c]}" for c in cols)})')
            self.con.executemany(f'insert into "{name}" values ({",".join("?" * len(cols))})',
                                 [[json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                   for v in (r.get(c) for c in cols)] for r in rows])
            self.untrusted |= {(name, c) for c in cols if types[c] == "TEXT" and _free_text([r.get(c) for r in rows[:300]])}
            hint = {}
            for c in cols:
                if types[c] != "TEXT" or (name, c) in self.untrusted:
                    continue
                seen = {r[c] for r in rows if isinstance(r.get(c), str)}
                dated = bool(seen) and all(re.match(r"\d{4}-\d{2}-\d{2}", v) for v in seen)
                days = [v[:10] for v in seen if dated and v[:10] <= C.today]   # expiry dates in the future don't count
                if days:                                   # the period the records cover (for held-out dates)
                    lo, hi = min(days), max(days)
                    self.date_range = (min(lo, self.date_range[0]), max(hi, self.date_range[1])) if self.date_range else (lo, hi)
                if len(seen) > 8 and not dated and _one_shape(seen):
                    for v in seen:                 # a value in several tables belongs to the smallest (master) one
                        if len(v) <= 40 and (v not in rank or len(rows) < rank[v]):
                            rank[v], self.entities[v] = len(rows), f"{name}.{c}"
                if 1 < len(seen) <= 8 and len(rows) > 8:
                    hint[c] = f"in {sorted(seen)}"                          # a short list: show all its values
                elif (ex := next(iter(seen), None)) and len(ex) <= 24:
                    hint[c] = f"e.g. {ex!r}"                                # otherwise one example of the format
            self.tables[name] = {"columns": types, "rows": len(rows), "hint": hint}
        self.con.commit()
        self.con.execute("pragma query_only = on")
        self.lock = threading.Lock()          # the authorizer and time limit belong to one query at a time

    def schema(self):
        """table(rows): column TYPE plus its values (a short list) or an example, and the joins. All generated from
        the data, so the model can write one good query instead of exploring table by table."""
        def col(t, c, ty, m):
            return f"{c} {ty}" + (" [free text]" if (t, c) in self.untrusted else f" {m['hint'][c]}" if c in m["hint"] else "")
        lines = [f"{t}({m['rows']} rows): " + ", ".join(col(t, c, ty, m) for c, ty in m["columns"].items())
                 for t, m in self.tables.items()]
        return "\n".join(lines) + "\nJoins (same column name): " + "; ".join(self.joins())

    def joins(self):
        """Columns that link tables: an id-like column (name ends in _id or _no) found in more than one table."""
        where = {}
        for t, m in self.tables.items():
            for c in m["columns"]:
                if c.endswith(("_id", "_no")):
                    where.setdefault(c, []).append(t)
        return [f"{c}: {', '.join(ts)}" for c, ts in sorted(where.items()) if len(ts) > 1]

    def values(self, column_ref, limit=50):
        """Distinct values of one "table.column", for drawing held-out parameter values."""
        tbl, col = column_ref.split(".", 1)
        if tbl not in self.tables or col not in self.tables[tbl]["columns"]:
            return []
        with self.lock:
            return [v for (v,) in self.con.execute(f'select distinct "{col}" from "{tbl}" where "{col}" is not null limit {int(limit)}')]

    def run(self, sql, max_rows=MAX_ROWS, timeout_s=TIMEOUT_S, params=None):
        with self.lock:
            return self._run(sql, max_rows, timeout_s, params or {})

    def _run(self, sql, max_rows, timeout_s, params):
        sql = (sql or "").strip().rstrip(";").strip()
        if not sql:
            raise QueryError("BAD_ARGS", "empty query")
        if len(sql) > MAX_SQL:
            raise QueryError("BAD_ARGS", f"query longer than {MAX_SQL} characters")
        read = set()

        def authorize(action, a, b, db, trigger):
            if action == sqlite3.SQLITE_READ:       # a company table, or a name the query defined itself (WITH c AS …)
                if (a or "").lower().startswith("sqlite_"):
                    return sqlite3.SQLITE_DENY
                if a in self.tables:
                    read.add((a, b))
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_DENY if (b or "").lower() in _DENIED_FUNCTIONS else sqlite3.SQLITE_OK
            return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY

        deadline = time.perf_counter() + timeout_s
        self.con.set_authorizer(authorize)
        self.con.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
        try:
            cur = self.con.execute(sql, params)
            cols = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.OperationalError as e:
            msg = str(e)
            if "interrupted" in msg:
                raise QueryError("LIMIT", f"query took longer than {timeout_s:g} s; make it simpler or narrower")
            if "not authorized" in msg or "prohibited" in msg or "readonly" in msg:
                raise QueryError("FORBIDDEN", "only one read-only SELECT over the company's tables is allowed")
            raise QueryError("BAD_ARGS", f"SQL error: {msg}")
        except (sqlite3.Warning, sqlite3.ProgrammingError) as e:
            raise QueryError("BAD_ARGS", f"SQL error: {e}")
        except sqlite3.DatabaseError as e:
            raise QueryError("FORBIDDEN" if "authoriz" in str(e) or "prohibited" in str(e) else "BAD_ARGS", f"SQL error: {e}")
        finally:
            self.con.set_authorizer(None)
            self.con.set_progress_handler(None, 0)
        if not cols:
            raise QueryError("FORBIDDEN", "only a SELECT that returns rows is allowed")
        out = {"columns": cols, "rows": [list(r) for r in rows[:max_rows]], "row_count": min(len(rows), max_rows),
               "truncated": len(rows) > max_rows, "tables_read": sorted({t for t, _ in read})}
        if read & self.untrusted:
            out[UNTRUSTED] = sorted(f"{t}.{c}" for t, c in read & self.untrusted)
        return out


def sandbox(C):
    """The sandbox for this CompanyData, built on first use."""
    if getattr(C, "_sandbox", None) is None:
        C._sandbox = Sandbox(C)
    return C._sandbox
