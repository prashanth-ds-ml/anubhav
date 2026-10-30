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
    L = ['digraph run {', 'rankdir=TB; size="3.4,6"; nodesep=0.15; ranksep=0.18; bgcolor="transparent";',
         'node [fontname="Inter", fontsize=9, style="rounded,filled", height=0.25, margin="0.08,0.03"];',
         'edge [color="#8A939E", arrowsize=0.5];',
         f'q [label="{_q(r["request"], 34)}", shape=box, fillcolor="#15181D", fontcolor="white"];']
    prev = "q"
    steps = [s for s in r.get("trace", []) if s["type"] == "tool"]
    for i, s in enumerate(steps):
        ok = s["ok"]
        args = s.get("arguments")
        args = json.loads(args) if isinstance(args, str) else (args or {})
        arg = ", ".join(str(v) for v in list(args.values())[:1])
        label = f'{s["name"]} · {_q(arg, 18)}' if arg else s["name"]
        if not ok:
            label += f'\\n✗ {s["error"]["code"]}'
        L.append(f't{i} [label="{label}", shape=box, fillcolor="{"#E3F1EA" if ok else "#FBE3E0"}", color="{"#1E7B4F" if ok else "#A1281B"}"];')
        L.append(f"{prev} -> t{i};")
        prev = f"t{i}"
        if ok and s["name"] == "plan_board":                 # learned rules arrive for every site of the day at once
            res = s.get("result") or {}
            learned = [(x["name"], r) for x in res.get("sites", []) for r in x.get("approved_rules", []) + x.get("advice", [])]
            for j, (site, rule) in enumerate(learned[:4]):
                L.append(f'b{i}_{j} [label="Learned · {_q(site, 22)}\\n{_q(rule, 30)}", shape=note, fillcolor="#E8F2F1", color="#0F7A74"];')
                L.append(f'b{i}_{j} -> t{i} [color="#0F7A74", style=dashed, label="learned"];')
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
    batch = [x for s in steps if s["name"] == "create_dispatch_drafts" and s["ok"] for x in s["result"]["results"] if x["ok"]]
    used = [k for k in r.get("knowledge", []) if "[" in k and k.rsplit("[", 1)[1].split()[-1].rstrip("]") in (r.get("reply") or "")]
    if batch:
        kg = sum(x["load"]["kg"] for x in batch)
        L.append(f'd [label="{len(batch)} drafts\\n{", ".join(x["vehicle_id"] for x in batch[:6])} · {kg:,.0f} kg", shape=box, '
                 f'fillcolor="#0F7A74", fontcolor="white"];')
    elif drafts:
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
