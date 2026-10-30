"""New tools from the agent's own queries (D-040). When no tool fits, the agent writes one read-only query
(runtime/query.py). A query it needed again for another request is a candidate tool: code turns its values into
parameters, checks it, and a person approves it. Then the broker offers it like any other tool.

Everything here is code; the model only wrote the original queries.
- template(): string literals that are dates, or values of the company's own name/id columns (towns, sites,
  vehicles…), become named parameters. Short code lists (a status, a weekday number) and formats stay as written.
- candidates(): from run traces, the same template used for different requests (>= MIN_USES), or one a person marks.
- check(): (1) with the original values it returns exactly the original rows; (2) it runs, within the limits, on
  held-out values drawn from the same columns or other months; (3) it is still one read-only SELECT (the sandbox).
- The tool is private to the company, never travels in a pack, and can be retired."""

import hashlib
import json
import re
from datetime import date, datetime

MIN_USES = 2
HELD_OUT = 5
STRING = re.compile(r"'((?:[^']|'')*)'")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _norm(sql):
    return re.sub(r"\s+", " ", sql.strip().rstrip(";")).lower()


def template(sql, sb):
    """(template_sql, params) where params = [{name, value, kind, column}]. kind: date | entity."""
    params, names = [], {}

    def name_for(base):
        names[base] = names.get(base, 0) + 1
        return base if names[base] == 1 else f"{base}_{names[base]}"

    src = sql.strip().rstrip(";")

    def compared(m):
        """The literal is a value the query filters on (after = < > IN BETWEEN … AND LIKE, or a function argument),
        not a label it prints (after THEN / ELSE / AS)."""
        before = src[:m.start()].rstrip()
        tok = re.search(r"(<=|>=|<>|!=|==|=|<|>|\(|,|\w+)$", before)
        tok = tok.group(1).lower() if tok else ""
        if tok == "and":
            return bool(re.search(r"between\s+(:\w+|'[^']*'|\S+)\s*$", before[:-3].rstrip(), re.I))
        return tok in {"=", "==", "<", ">", "<=", ">=", "<>", "!=", "like", "between", "in", "(", ","}

    def repl(m):
        v = m.group(1).replace("''", "'")
        if not compared(m):
            return m.group(0)
        if DATE.fullmatch(v):
            kind, column, base = "date", None, "date"
        elif v in sb.entities:
            kind, column = "entity", sb.entities[v]
            base = column.split(".")[1]
        else:
            return m.group(0)                      # a code or a format: part of the query, not a parameter
        p = {"name": name_for(base), "value": v, "kind": kind, "column": column}
        params.append(p)
        return f":{p['name']}"

    tpl = STRING.sub(repl, src)
    dates = [p for p in params if p["kind"] == "date"]
    if len(dates) == 2 and dates[0]["value"] <= dates[1]["value"]:      # a range reads better as from / to
        for p, new in zip(dates, ("date_from", "date_to")):
            tpl = re.sub(rf":{p['name']}\b", f":{new}", tpl)
            p["name"] = new
    return tpl, params


def key(tpl):
    return hashlib.sha256(_norm(tpl).encode()).hexdigest()[:12]


def uses_in(runs, company, sb):
    """Every successful run_query in these runs, as (template, params, request, purpose, sql, run_id)."""
    out = []
    for r in runs:
        if r.get("company") != company:
            continue
        for s in r.get("trace", []):
            if s.get("type") != "tool" or s.get("name") != "run_query" or not s.get("ok"):
                continue
            a = s["arguments"]
            a = json.loads(a) if isinstance(a, str) else (a or {})
            if not a.get("sql") or not (s.get("result") or {}).get("row_count"):
                continue                           # a query that found nothing is not worth a tool
            tpl, params = template(a["sql"], sb)
            if not params:
                continue                           # nothing to vary: an answer, not a tool
            out.append({"template": tpl, "key": key(tpl), "params": params, "request": r.get("request", ""),
                        "purpose": a.get("purpose", ""), "sql": a["sql"], "run_id": r.get("run_id")})
    return out


def candidates(runs, company, sb, marked=()):
    """Templates used for >= MIN_USES different requests, or marked by a person (by key)."""
    groups = {}
    for u in uses_in(runs, company, sb):
        g = groups.setdefault(u["key"], {"key": u["key"], "template": u["template"], "uses": []})
        g["uses"].append(u)
    out = []
    for g in groups.values():
        g["requests"] = sorted({u["request"] for u in g["uses"]})
        if len(g["requests"]) >= MIN_USES or g["key"] in marked:
            out.append(g)
    return sorted(out, key=lambda g: -len(g["uses"]))


def suggest_name(g):
    """A tool name from the agent's own stated purpose (a person can edit it before approving)."""
    words = re.findall(r"[a-z]+", (g["uses"][0]["purpose"] or g["uses"][0]["request"]).lower())
    stop = {"the", "a", "an", "of", "for", "in", "on", "by", "to", "and", "what", "which", "how", "is", "are", "our", "we"}
    words = [w for w in words if w not in stop][:5] or ["query"]
    return "_".join(words)[:40]


def _shift(d, months=0, days=0):
    from datetime import timedelta
    base = date.fromisoformat(d)
    y, m = divmod(base.month - 1 + months, 12)
    try:
        base = base.replace(year=base.year + y, month=m + 1)
    except ValueError:
        base = base.replace(year=base.year + y, month=m + 1, day=28)
    return (base + timedelta(days=days)).isoformat()


SHIFTS = [(-1, 0), (1, 0), (0, -7), (0, 7), (0, -14), (0, 14), (-2, 0), (2, 0), (0, -21), (0, 21)]


def held_out_values(g, sb, n=HELD_OUT):
    """n parameter sets the original queries never used: other values of the same columns, and the dates moved by
    whole months or weeks (a range keeps its length), staying inside the period the records cover."""
    first = {p["name"]: p for p in g["uses"][0]["params"]}
    used = {(p["name"], p["value"]) for u in g["uses"] for p in u["params"]}
    lo, hi = sb.date_range or ("0000-01-01", "9999-12-31")
    pools = {nm: [v for v in sb.values(p["column"], 200) if (nm, v) not in used]
             for nm, p in first.items() if p["kind"] == "entity"}
    sets = []
    for i in range(4 * n):
        mo, dy = SHIFTS[i % len(SHIFTS)]
        s = {}
        for nm, p in first.items():
            if p["kind"] == "date":
                s[nm] = _shift(p["value"], mo, dy)
            elif pools.get(nm):
                s[nm] = pools[nm][(i * 7) % len(pools[nm])]
            else:
                s = None
                break
        if s and all(lo <= v <= hi for nm, v in s.items() if first[nm]["kind"] == "date") and s not in sets                 and any(s[nm] != first[nm]["value"] for nm in s):
            sets.append(s)
        if len(sets) == n:
            break
    return sets


def check(g, sb):
    """The promotion checks. Returns {"pass", "same_rows", "held_out", "reasons"}."""
    from ..runtime.query import QueryError
    reasons, same = [], []
    for u in g["uses"]:
        try:
            orig = sb.run(u["sql"])
            new = sb.run(g["template"], params={p["name"]: p["value"] for p in u["params"]})
            ok = orig["rows"] == new["rows"]
        except QueryError as e:
            ok, orig = False, {"row_count": 0}
            reasons.append(f"original values: {e.message}")
        same.append({"request": u["request"], "rows": orig.get("row_count", 0), "same": ok})
    if not all(x["same"] for x in same):
        reasons.append("with the original values it does not return the original rows")
    held = []
    for s in held_out_values(g, sb):
        try:
            r = sb.run(g["template"], params=s)
            held.append({"values": s, "ok": True, "rows": r["row_count"]})
        except QueryError as e:
            held.append({"values": s, "ok": False, "error": e.message})
    if len(held) < 3:
        reasons.append("not enough held-out values to test it")
    elif not all(h["ok"] for h in held):
        reasons.append("fails on held-out values")
    elif sum(h["rows"] > 0 for h in held) < (len(held) + 1) // 2:
        reasons.append("finds nothing for most held-out values: it only fits the original case")
    return {"pass": not reasons, "same_rows": same, "held_out": held, "reasons": reasons}


# ---------- the store: one table in the company's lesson store (per visitor when hosted)
def _con(store):
    con = store._con()
    con.execute("create table if not exists tools (tool_id text primary key, company text, name text, description text, "
                "template text, params text, status text, checks text, source text, created text, decided_by text, "
                "decided text, note text)")
    return con


def _row(r):
    return dict(r) | {k: json.loads(r[k]) if r[k] else None for k in ("params", "checks", "source")}


def tools(store, company, status=None):
    with _con(store) as con:
        rows = con.execute("select * from tools where company = ? order by created", (company,)).fetchall()
    return [_row(r) for r in rows if status is None or r["status"] in ({status} if isinstance(status, str) else status)]


def propose(store, company, g, checks, name, description):
    """Record a candidate with its check results. Nothing is offered to the agent until a person approves."""
    name = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")[:40] or "query"
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", name):
        raise ValueError("a tool name is 3–40 lowercase letters, digits or _ and starts with a letter")
    if any(t["name"] == name and t["status"] in ("candidate", "active") for t in tools(store, company)):
        raise ValueError(f"a tool named {name} already exists")
    params = [{k: p[k] for k in ("name", "kind", "column")} | {"example": p["value"]} for p in g["uses"][0]["params"]]
    tid = f"NT-{company}-{g['key'][:8]}"
    with _con(store) as con:
        con.execute("insert or replace into tools values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tid, company, name, description[:300], g["template"], json.dumps(params, ensure_ascii=False),
                     "candidate", json.dumps(checks, ensure_ascii=False, default=str),
                     json.dumps([{"run_id": u["run_id"], "request": u["request"]} for u in g["uses"]], ensure_ascii=False),
                     datetime.now().isoformat(timespec="seconds"), None, None, ""))
    return tid


def decide(store, tool_id, by, approve, note=""):
    """A person approves (only if the checks passed) or rejects a candidate; or retires an active tool."""
    if not by:
        raise PermissionError("a person must approve or reject a tool")
    with _con(store) as con:
        r = con.execute("select * from tools where tool_id = ?", (tool_id,)).fetchone()
        if not r:
            raise ValueError(f"no tool {tool_id}")
        cur = _row(r)
        if approve and cur["status"] != "candidate":
            raise ValueError(f"{tool_id} is {cur['status']}, not a candidate")
        if approve and not (cur["checks"] or {}).get("pass"):
            raise PermissionError("a tool whose checks failed cannot be approved")
        status = "active" if approve else ("retired" if cur["status"] == "active" else "rejected")
        con.execute("update tools set status = ?, decided_by = ?, decided = ?, note = ? where tool_id = ?",
                    (status, by, datetime.now().isoformat(timespec="seconds"), note, tool_id))
    return status
