"""The Data tab: a company's records as the agents see them, page by page. Read-only, over the same query sandbox the
agents use (runtime/query.py), so judges see exactly the tables and columns the agents query.

Table and column names in every SELECT come from the sandbox's own schema, never from the request; values (dates,
offset, limit) are bound parameters. Titles and the order below are for people reading the page; any other canonical
table is listed after them with a title made from its name."""

import re

from ..runtime.query import QueryError

PAGE = 50
MAX_PAGE = 100
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

# What a judge most wants to see first, with a plain title and the date the filter uses.
FIRST = {
    "orders": ("Orders", "delivery_date"),
    "order_items": ("Order lines (cases per product)", None),
    "shipments": ("Trips", "delivery_date"),
    "trip_outcomes": ("Trip outcomes (delivered, partial, returned)", "arrived_at"),
    "trip_events": ("Trip events and delays", "ts"),
    "vehicles": ("Vehicles", None),
    "sites": ("Sites (customers and godowns)", None),
    "driver_notes": ("Driver notes", "ts"),
    "planner_messages": ("Planner messages", "ts"),
    "products": ("Products", None),
}


class DataError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _dated(sb, today, table, cols):
    """The first text column whose values are all dates up to today (an expiry date in the future isn't a record's date)."""
    for c, ty in cols.items():
        if ty != "TEXT" or (table, c) in sb.untrusted:
            continue
        n, ok, hi = sb.run(f'select count("{c}"), sum("{c}" glob \'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*\'), max(substr("{c}", 1, 10)) from "{table}"')["rows"][0]
        if n and ok == n and hi <= today:
            return c
    return None


def tables(sb, today):
    """Every canonical table: name, title, rows, the date column (or None) and the dates it spans. Built once per sandbox."""
    if getattr(sb, "_data_tables", None) is None:
        order = [t for t in FIRST if t in sb.tables] + sorted(t for t in sb.tables if t not in FIRST)
        out = []
        for t in order:
            cols = sb.tables[t]["columns"]
            title, dc = FIRST.get(t, (t.replace("_", " ").capitalize(), None))
            if t not in FIRST:
                dc = _dated(sb, today, t, cols)
            lo = hi = None
            if dc in cols:
                lo, hi = sb.run(f'select min(substr("{dc}", 1, 10)), max(substr("{dc}", 1, 10)) from "{t}" where "{dc}" <= :end',
                                params={"end": today + "~"})["rows"][0]
            else:
                dc = None
            out.append({"table": t, "title": title, "rows": sb.tables[t]["rows"], "date_column": dc, "date_min": lo, "date_max": hi,
                        "columns": len(cols)})
        sb._data_tables = out
    return sb._data_tables


def rows(sb, today, table, date_from=None, date_to=None, offset=0, limit=PAGE):
    meta = next((m for m in tables(sb, today) if m["table"] == table), None)
    if meta is None:
        raise DataError(404, "NOT_FOUND", f"no table {table!r}; tables: {', '.join(m['table'] for m in tables(sb, today))}")
    for d in (date_from, date_to):
        if d is not None and not DAY.fullmatch(d):
            raise DataError(422, "BAD_DATE", "dates are YYYY-MM-DD")
    dc = meta["date_column"]
    if (date_from or date_to) and not dc:
        raise DataError(422, "NO_DATE", f"{table} has no date to filter on")
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    cols = list(sb.tables[table]["columns"])            # names from the schema only
    where, params = [], {"lim": limit, "off": offset}
    if date_from:
        where.append(f'substr("{dc}", 1, 10) >= :date_from')
        params["date_from"] = date_from
    if date_to:
        where.append(f'substr("{dc}", 1, 10) <= :date_to')
        params["date_to"] = date_to
    cond = f" where {' and '.join(where)}" if where else ""
    order = f' order by "{dc}" desc, rowid' if dc else " order by rowid"
    try:
        total = sb.run(f'select count(*) from "{table}"{cond}', params=params)["rows"][0][0]
        page = sb.run(f'select {", ".join(chr(34) + c + chr(34) for c in cols)} from "{table}"{cond}{order} limit :lim offset :off',
                      max_rows=limit, params=params)
    except QueryError as e:
        raise DataError(500, "QUERY_FAILED", e.message)
    nxt = offset + len(page["rows"])
    return {"table": table, "title": meta["title"], "date_column": dc, "date_from": date_from, "date_to": date_to,
            "columns": [{"name": c, "type": sb.tables[table]["columns"][c], "free_text": (table, c) in sb.untrusted} for c in cols],
            "rows": page["rows"], "total": total, "offset": offset, "limit": limit, "next_offset": nxt if nxt < total else None}
