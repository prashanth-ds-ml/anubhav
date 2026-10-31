import json
import sqlite3

import altair as alt
import streamlit as st

from anubhav import trace
from anubhav.data.config import ROOT

st.title("Proof & audit")
st.caption("Every experiment was pre-registered and its files frozen by hash before any model call. "
           "Tests run on worlds the system had never seen (fresh seeds).")

bench = sorted((ROOT / "artifacts" / "benchmark").glob("exp011_*.json"))
if bench:
    d = json.loads(bench[-1].read_text(encoding="utf-8"))
    S = d["summary"]
    st.subheader("Final benchmark: does learning make plans safer and more correct?")
    st.caption(f"EXP-011 · unseen world {d['world']} · same model (Muse Spark Open), same 38 cases, one run each · {bench[-1].name}")
    with st.container(horizontal=True):
        for label, before, after in (("T01 with its lessons", "T01:B", "T01:C"), ("T02 with its lessons", "T02:B", "T02:C"),
                                     ("New company + pack", "TNEW:B", "TNEW:E")):
            st.metric(label, f"{S[after]['ok']} correct", f"from {S[before]['ok']} cold", delta_color="off", border=True)
        st.metric("Unsafe drafts with learning", sum(S[k]["unsafe"] for k in ("T01:C", "T02:C", "TNEW:E")),
                  f"cold: {sum(S[k]['unsafe'] for k in ('T01:B', 'T02:B', 'TNEW:B'))}", delta_color="off", border=True)

    names = {"A": "cold, no note search", "B": "cold + raw-note search", "C": "+ its approved lessons", "E": "+ partner pack"}
    fams = {"site_access": "Limited gate", "alias": "Nicknames", "real_capacity": "Real capacity",
            "control": "Ordinary orders", "look_alike": "Look-alike site"}
    rows = []
    for key, v in S.items():
        company, arm = key.split(":")
        for f, frac in v["by_family"].items():
            ok, n = map(int, frac.split("/"))
            rows.append({"Company": company, "Arm": names[arm], "Case family": fams[f], "Correct": ok / n, "Cases": frac})
    chart = alt.Chart(alt.Data(values=rows)).mark_bar().encode(
        x=alt.X("Correct:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("Arm:N", title=None, sort=list(names.values())),
        color=alt.Color("Arm:N", sort=list(names.values()), legend=None),
        row=alt.Row("Case family:N", title=None, sort=list(fams.values())),
        column=alt.Column("Company:N", title=None),
        tooltip=["Company:N", "Arm:N", "Case family:N", "Cases:N"],
    ).properties(width=170, height=alt.Step(14))
    st.altair_chart(chart)
    st.caption("Pre-registered bars, both met: lessons beat raw-note search by +55 points on unwritten knowledge "
               "(bar +25) with 0 unsafe drafts; the new company gains +67 points from the pack (bar +25) with 0 leaks. "
               "Not improved: real capacity (the agent refused to overload the truck but didn't offer another one).")

rep = sorted((ROOT / "artifacts" / "benchmark").glob("exp011r_2*.json"))
rep = [p for p in rep if not p.name.endswith("_rows.json")]
if rep:
    d = json.loads(rep[-1].read_text(encoding="utf-8"))
    st.subheader("The same benchmark, 3 times, on the version you are using (EXP-011R)")
    st.caption(f"Pre-registered before any model call · {len(d['rows'])} runs · {rep[-1].name}")
    st.dataframe([{"repeat": i + 1, "lessons (C)": r["lessons_C"], "raw notes (B)": r["raw_notes_B"],
                   "gain, points": r["lessons_gain_pts"], "unsafe with lessons": r["C_unsafe"],
                   "new company + pack (E)": r["pack_E"], "new company cold (B)": r["cold_B"]} for i, r in enumerate(d["repeats"])],
                 hide_index=True, alt="EXP-011R: each repeat's results",
                 column_config={k: st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)
                                for k in ("lessons (C)", "raw notes (B)", "new company + pack (E)", "new company cold (B)")})
    p = d["pooled"]
    st.caption(f"Pooled: lessons {p['lessons_C']:.0%} vs raw notes {p['raw_notes_B']:.0%} (+{p['lessons_gain_pts']:.0f} points); "
               f"new company {p['cold_B']:.0%} → {p['pack_E']:.0%}. Replicated (bar met pooled and in ≥ 2 of 3 repeats): "
               f"lessons {'yes' if d['replicated']['lessons'] else 'no'}, sharing {'yes' if d['replicated']['transfer'] else 'no'}. "
               "Still not improved: real truck capacity (0/6 with lessons).")

nt12 = sorted((ROOT / "artifacts" / "benchmark").glob("exp012b_2*.json"))
nt12 = [p for p in nt12 if not p.name.endswith("_rows.json")]
if nt12:
    d = json.loads(nt12[-1].read_text(encoding="utf-8"))
    st.subheader("Tools it made itself (EXP-012 → EXP-012b)")
    a = d["arms"]
    with st.container(horizontal=True):
        st.metric("Learned tools used", d["decision"]["learned_tool_used_in"], "was 0/16 with case-specific names", delta_color="off", border=True)
        st.metric("Answers right", f"{a['T']['right']}/{a['T']['n']}", f"{a['Q']['right']}/{a['Q']['n']} without them", delta_color="off", border=True)
        st.metric("Tool calls per question", a["T"]["mean_tool_calls"], f"{a['Q']['mean_tool_calls']} without them", delta_color="off", border=True)
        st.metric("Cost per question", f"${a['T']['mean_cost']:.3f}", f"${a['Q']['mean_cost']:.3f} without them", delta_color="off", border=True)
    st.caption("16 held-out questions on an unseen world. Pre-registered bar: 30% fewer tool calls, not met (20%). "
               "EXP-012 failed both its rules first; EXP-012b changed one thing (general tool names). Both are in the experiments log.")

t13 = [p for p in sorted((ROOT / "artifacts" / "benchmark").glob("exp013_2*.json"))]
if t13:
    d = json.loads(t13[-1].read_text(encoding="utf-8"))["decision"]
    st.subheader("One planner or a team? (EXP-013)")
    with st.container(horizontal=True):
        for label, k in (("Single Planner", "S"), ("Team", "M0"), ("Team after one learning round", "M1")):
            st.metric(label, f"{d[k]['ok']}/{d[k]['n']} right", f"${d[k]['mean_cost']:.3f} a case · {d[k]['unsafe']} unsafe", delta_color="off", border=True)
    st.caption("54 cases, one repeat, pre-registered. The team met its bars (no unsafe drafts, within 5 points, within 1.5× the cost), but it is not "
               "more accurate than one planner, and it costs about a third more. The learning round's routing gain "
               f"(+{d['R4_routing_gain_pts']} points) missed its bar (+15), and answers did not improve.")

st.subheader("Does it learn the right things?")
st.caption("Mining precision and recall against the generator's hidden rules (never shown to the system).")
mining = []
for name, label in (("exp009_*.json", "EXP-009 · unseen world 4111"), ("exp009b_*.json", "EXP-009b · unseen world 5279")):
    f = sorted((ROOT / "artifacts" / "learning").glob(name))
    if f:
        p = json.loads(f[-1].read_text(encoding="utf-8"))["primary_fresh_world"]["pooled"]
        mining.append((label, p))
if mining:
    with st.container(horizontal=True):
        for label, p in mining:
            st.metric(label, f"precision {p['precision']:.0%}", f"recall {p['recall']:.0%} · traps let in: {len(p['traps_admitted'])}",
                      delta_color="off", border=True)
    st.caption("The bar is 85% precision. EXP-009 missed it: registration numbers were mistaken for nicknames. "
               "One generic fix (a nickname can't be something already in master data) and a second unseen world: met. "
               "Every lesson still needs a reviewer before it's used.")

st.subheader("Every run is traced")
idx = ROOT / "data" / "traces" / "index.sqlite"
if idx.exists():
    con = sqlite3.connect(idx)
    rows = [dict(zip(["run_id", "saved_at", "label", "company", "model", "request", "cost_usd"], r)) for r in
            con.execute("select run_id, saved_at, label, company, model, request, cost_usd from runs order by saved_at desc limit 60")]
    con.close()
    sel = st.dataframe(rows, hide_index=True, on_select="rerun", selection_mode="single-row", alt="Saved agent runs")
    if sel.selection.rows:
        st.code("\n".join(trace.replay(rows[sel.selection.rows[0]]["run_id"])), language=None, wrap_lines=True)
else:
    st.caption("No local traces on this deployment. Saved runs replay on the Workbench.")
