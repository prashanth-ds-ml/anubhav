"""Graph views: one agent run as a flow (question → tools → lessons used → decision)."""

import json


def _q(s, n=60):
    s = (s or "").replace('"', "'").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


TYPE_LABEL = {"sites_in_town": "Sites in a town", "towns_served": "Towns we serve", "trips_in_month": "Past deliveries in a month",
              "returned_at_site": "Returns at a site", "open_orders_town": "Open orders tomorrow",
              "orders_in_month": "Orders from a site in a month"}


def tool_map_dot(rows, title=""):
    """Question types (left) -> tools used (right). Line width = how often; green = answers right, orange = wrong."""
    by = {}
    for r in rows:
        tools = json.loads(r["tools"]) if isinstance(r["tools"], str) else r["tools"]
        t = by.setdefault(r["qtype"], {"n": 0, "ok": 0, "edges": {}})
        t["n"] += 1
        t["ok"] += int(r["answer_ok"])
        for tool in dict.fromkeys(tools) or ["(no tool: answered from memory)"]:
            e = t["edges"].setdefault(tool, {"n": 0, "ok": 0})
            e["n"] += 1
            e["ok"] += int(r["answer_ok"])
    L = ['digraph tools {', 'rankdir=TB; bgcolor="transparent"; nodesep=0.3; ranksep=1.2;',
         'node [fontname="Inter", fontsize=11, style="rounded,filled", shape=box];',
         f'labelloc=t; label="{_q(title, 80)}"; fontname="Inter"; fontsize=13;']
    tools = sorted({tool for t in by.values() for tool in t["edges"]})
    L.append('subgraph cluster_q { label="Kind of question"; color="#E2E5EA"; fontname="Inter";')
    for q, t in by.items():
        L.append(f'"q:{q}" [label="{TYPE_LABEL.get(q, q)}\\n{t["ok"]}/{t["n"]} right", fillcolor="#15181D", fontcolor="white"];')
    L.append('}')
    L.append('subgraph cluster_t { label="Tool it used"; color="#E2E5EA"; fontname="Inter";')
    for tool in tools:
        none = tool.startswith("(no tool")
        L.append(f'"t:{tool}" [label="{tool}", fillcolor="{"#FBE3E0" if none else "#E8F2F1"}", color="{"#A1281B" if none else "#0F7A74"}"];')
    L.append('}')
    for q, t in by.items():
        for tool, e in t["edges"].items():
            good = e["ok"] / e["n"] >= 0.8
            L.append(f'"q:{q}" -> "t:{tool}" [penwidth={1 + 2.5 * e["n"] / max(1, t["n"]):.1f}, '
                     f'color="{"#1E7B4F" if good else "#B4570B"}", label="{e["n"]}", fontsize=9];')
    L.append("}")
    return "\n".join(L)


def run_dot(r, C=None):
    """DOT source for one run. Green tool = ok, red = error; teal notes = approved lessons the reply cites."""
    L = ['digraph run {', 'rankdir=TB; nodesep=0.35; ranksep=0.35; bgcolor="transparent"; node [fontname="Inter", fontsize=11, style="rounded,filled"];',
         'edge [color="#8A939E", arrowsize=0.7];',
         f'q [label="{_q(r["request"], 48)}", shape=box, fillcolor="#15181D", fontcolor="white"];']
    prev = "q"
    steps = [s for s in r.get("trace", []) if s["type"] == "tool"]
    for i, s in enumerate(steps):
        ok = s["ok"]
        args = s.get("arguments")
        args = json.loads(args) if isinstance(args, str) else (args or {})
        arg = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
        label = f'{s["name"]}\\n{_q(arg, 34)}' if arg else s["name"]
        if not ok:
            label += f'\\n✗ {s["error"]["code"]}'
        L.append(f't{i} [label="{label}", shape=box, fillcolor="{"#E3F1EA" if ok else "#FBE3E0"}", color="{"#1E7B4F" if ok else "#A1281B"}"];')
        L.append(f"{prev} -> t{i};")
        prev = f"t{i}"
        if ok and s["name"] == "get_site_constraints":      # where learned knowledge entered the decision
            res = s.get("result") or {}
            for j, p in enumerate(res.get("approved_policies", [])):
                L.append(f'p{i}_{j} [label="Learned rule {p["id"]}\\n{_q(p["rule"], 30)}", shape=note, fillcolor="#0F7A74", fontcolor="white"];')
                L.append(f'p{i}_{j} -> t{i} [color="#0F7A74", style=dashed, label="learned"];')
            for j, a in enumerate(res.get("advisories", [])):
                L.append(f'a{i}_{j} [label="Learned advice {a["id"]}\\n{_q(a["text"], 30)}", shape=note, fillcolor="#E8F2F1", color="#0F7A74"];')
                L.append(f'a{i}_{j} -> t{i} [color="#0F7A74", style=dashed, label="learned"];')
            if not res.get("approved_policies") and not res.get("advisories"):
                L.append(f'n{i} [label="nothing recorded\\nabout this site", shape=note, fillcolor="#FFF4E5", color="#B4570B"];')
                L.append(f'n{i} -> t{i} [color="#B4570B", style=dashed];')
    drafts = [s for s in steps if s["name"] == "create_dispatch_draft" and s["ok"]]
    used = [k for k in r.get("knowledge", []) if "[" in k and k.rsplit("[", 1)[1].split()[-1].rstrip("]") in (r.get("reply") or "")]
    if drafts:
        d = drafts[-1]["result"]
        v = (C.vehicles.get(d["vehicle_id"], {}) if C else {})
        L.append(f'd [label="Draft {d["vehicle_id"]}\\n{v.get("length_ft", "?")} ft · {d["load"]["kg"]:,.0f} kg", shape=box, '
                 f'fillcolor="#0F7A74", fontcolor="white"];')
    else:
        L.append(f'd [label="{_q(r.get("reply"), 40) or "reply"}", shape=box, fillcolor="#EEF0F3"];')
    L.append(f"{prev} -> d;")
    for j, k in enumerate(used):
        text, lid = k.rsplit(" [", 1)
        L.append(f'k{j} [label="{_q(text, 44)}\\n{lid.rstrip("]")}", shape=note, fillcolor="#E8F2F1", color="#0F7A74"];')
        L.append(f'k{j} -> d [color="#0F7A74", style=dashed, label="used"];')
    L.append("}")
    return "\n".join(L)
