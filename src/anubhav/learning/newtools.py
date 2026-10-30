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


def _signature(params):
    return tuple(sorted({(p["name"], p["kind"], p["column"]) for p in params}))


def _result(sb, tpl, values):
    from ..runtime.query import QueryError
    try:
        return sb.run(tpl, params=values)
    except QueryError:
        return None


def equivalent(a, b):
    """Two results answer the same thing when they have the same number of rows and share a numeric column with the
    same values (a count, a percentage…), whatever the labels, extra columns or column order. Results with no
    numbers must be identical."""
    if a is None or b is None or a["row_count"] != b["row_count"]:
        return False
    def numeric(r):
        cols = list(zip(*r["rows"])) if r["rows"] else []
        return {tuple(sorted(c)) for c in cols if c and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in c)
                and len(set(c)) > 1 or (len(c) == 1 and isinstance(c[0], (int, float)))}
    na, nb = numeric(a), numeric(b)
    if na or nb:
        return bool(na & nb)
    return sorted(map(tuple, a["rows"]), key=repr) == sorted(map(tuple, b["rows"]), key=repr)


def same_tool(a, b, sb):
    """Two queries are the same tool when they take the same parameters and give equivalent answers for the same
    inputs: the values each was used with, plus held-out values. The model rarely writes the same SQL text twice."""
    if _signature(a["uses"][0]["params"]) != _signature(b["uses"][0]["params"]):
        return False
    probes = [{p["name"]: p["value"] for p in u["params"]} for u in (a["uses"][0], b["uses"][0])]
    probes += held_out_values(a, sb, 3)
    found = False
    for v in probes:
        x, y = _result(sb, a["template"], v), _result(sb, b["template"], v)
        if not equivalent(x, y):
            return False
        found = found or bool(x["row_count"])
    return found


def groups(runs, company, sb):
    """Every query the agent wrote, grouped: queries that give equivalent answers for the same inputs are one group,
    whatever their SQL text. Each group keeps the plainest wording (ASCII labels first, then the most used)."""
    exact = {}
    for u in uses_in(runs, company, sb):
        g = exact.setdefault(u["key"], {"key": u["key"], "template": u["template"], "uses": []})
        g["uses"].append(u)
    merged = []
    for g in sorted(exact.values(), key=lambda g: -len(g["uses"])):
        home = next((m for m in merged if same_tool(m, g, sb)), None)
        if home:
            home["uses"] += g["uses"]
            home.setdefault("variants", []).append(g["template"])
        else:
            merged.append(g)
    for g in merged:
        if g.get("variants"):
            pool = [g["template"], *g["variants"]]
            count = {tp: sum(u["template"] == tp for u in g["uses"]) for tp in pool}
            g["template"] = min(pool, key=lambda tp: (not tp.isascii(), -count[tp]))
        g["requests"] = sorted({u["request"] for u in g["uses"]})
    return sorted(merged, key=lambda g: (-len(g["requests"]), -len(g["uses"])))


def candidates(runs, company, sb, marked=()):
    """Groups needed for >= MIN_USES different requests, or marked by a person (by key)."""
    return [g for g in groups(runs, company, sb) if len(g["requests"]) >= MIN_USES or g["key"] in marked]


def _outputs(tpl):
    """The names a query gives its first columns (SELECT … AS name), to say what the tool returns."""
    head = re.split(r"\bfrom\b", re.sub(r"\s+", " ", tpl), 1, flags=re.I)[0]
    return [a.lower() for a in re.findall(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)", head, re.I)]


def _inputs(g):
    names = [p["name"] for p in g["uses"][0]["params"]]
    dates = [n for n in names if n.startswith("date")]
    rest = [n for n in names if not n.startswith("date")]
    return rest + (["dates"] if len(dates) > 1 else dates)


def suggest_name(g):
    """A general name: what the query returns, by what it takes (never a value it was built from), e.g.
    total_returned_cases_by_town_and_dates. A person can edit it before approving."""
    outs = _outputs(g["template"])
    what = "_".join(outs[:2]) if outs else "rows"
    name = f"{what}_by_{'_and_'.join(_inputs(g))}" if _inputs(g) else what
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "_", name.lower()))[:40].strip("_")


def describe(g):
    """What the tool returns and takes, with one example request whose values are replaced by the input names."""
    u = g["uses"][0]
    example = u["request"]
    for p in u["params"]:
        example = re.sub(re.escape(p["value"]), f"<{p['name']}>", example, flags=re.I)
    outs = ", ".join(_outputs(g["template"])[:4]) or "rows"
    ins = ", ".join(f"{p['name']} ({'YYYY-MM-DD' if p['kind'] == 'date' else p['column'].split('.')[1]})" for p in u["params"])
    return (f"Returns {outs} for any {ins}. Learned from {len(g.get('requests') or [1])} requests, e.g. \"{example[:90]}\"")[:300]


def free_name(store, company, name):
    """name, or name_2, name_3… if a candidate or active tool already has it (for automated proposals)."""
    taken = {x["name"] for x in tools(store, company) if x["status"] in ("candidate", "active")}
    base, i = name[:37], 1
    while name in taken:
        i += 1
        name = f"{base}_{i}"
    return name


def specific_words(g, text):
    """Values the tool was built from that leaked into its name or description (they make it look one-off)."""
    vals = {p["value"].lower() for u in g["uses"] for p in u["params"]}
    return sorted(v for v in vals if v and v in (text or "").lower())


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
            ok = orig["rows"] == new["rows"] or equivalent(orig, new)
        except QueryError as e:
            ok, orig = False, {"row_count": 0}
            reasons.append(f"original values: {e.message}")
        same.append({"request": u["request"], "rows": orig.get("row_count", 0), "same": ok})
    if not all(x["same"] for x in same):
        reasons.append("with the original values it does not give the original answers")
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
    if specific_words(g, name):
        raise ValueError(f"the name mentions {', '.join(specific_words(g, name))}: name what the tool does for any value")
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
