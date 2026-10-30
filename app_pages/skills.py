import json

import streamlit as st

from anubhav.harness import practice
from anubhav.ui import core, graphs

H = core.harness_store()
cid = st.session_state.company
st.title("Skills: how well it uses its tools")
st.caption("The agent practises on questions generated from the company's own records (stops in a month, returns at a "
           "site, sites in a town, open orders…), in Roman Telugu, Telugu and English. Answers are checked against the "
           "records. Mistakes drive tool-use patches (Tuning); held-out questions with other towns and sites show whether "
           "a patch really helps.")

rows = H.practice()
with st.container(horizontal=True, vertical_alignment="center"):
    off = core.live_ready("open")
    if st.button("Practice now (active version)", icon=":material/fitness_center:", type="primary", disabled=bool(off), help=off):
        client, off = core.live_client("open")
        if client:
            C = core.company(cid)
            qs = practice.build(C, split="dev")
            with st.spinner(f"Answering {len(qs)} practice questions with Muse Spark Open…"):
                res = practice.run(C, client, qs, core.active_harness())
            H.add_practice(f"UI-{cid}", H.active()["version_id"], res)
            st.rerun()
    st.caption(off or f"~${0.02 * 19:.2f} for one practice set on {cid}.")

if not rows:
    st.info("No practice yet.", icon=":material/fitness_center:")
    st.stop()

# ---------- per version and split
groups = {}
for r in rows:
    groups.setdefault((r["round"], r["version_id"], r["split"]), []).append(r)
table = []
for (rnd, ver, split), rs in groups.items():
    n = len(rs)
    table.append({"round": rnd, "version": ver, "questions": f"{split} ({n})",
                  "answers right": sum(r["answer_ok"] for r in rs) / n, "fitting tool": sum(r["right_tool"] for r in rs) / n,
                  "answered without lookup": sum(not r["used_tool"] for r in rs) / n,
                  "tool errors": sum(r["tool_errors"] for r in rs), "cost $": round(sum(r["cost_usd"] for r in rs), 3)})
st.subheader("Which tool it used for which kind of question")
st.caption("Lines go from each kind of question to the tools the agent called. Thicker = used more often. "
           "Green = answers matched the records, orange = they didn't. Red tool box = it answered without looking anything up.")
labels = {k: f"{k[0]} · {k[1]} · {k[2]} ({len(v)} questions)" for k, v in groups.items()}
keys = list(groups)
c1, c2 = st.columns(2)
left_k = c1.selectbox("Before", keys, index=0, format_func=labels.get, key="tm_left")
right_k = c2.selectbox("After", keys, index=len(keys) - 1, format_func=labels.get, key="tm_right")
g1, g2 = st.columns(2)
with g1:
    st.graphviz_chart(graphs.tool_map_dot(groups[left_k], f"{left_k[1]} · {left_k[2]}"), width="stretch",
                      alt="Question types linked to the tools the agent used, before")
with g2:
    st.graphviz_chart(graphs.tool_map_dot(groups[right_k], f"{right_k[1]} · {right_k[2]}"), width="stretch",
                      alt="Question types linked to the tools the agent used, after")

st.subheader("Results by version")
st.dataframe(table, hide_index=True, alt="Practice results by harness version", column_config={
    "answers right": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
    "fitting tool": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
    "answered without lookup": st.column_config.NumberColumn(format="percent")})

# ---------- before / after on the latest held-out comparison
held = [k for k in groups if k[2] == "held_out"]
rounds = sorted({k[0] for k in held})
if rounds:
    rnd = rounds[-1]
    vers = [k for k in held if k[0] == rnd]
    if len(vers) >= 2:
        (_, vb, _), (_, vc, _) = sorted(vers, key=lambda k: k[1])
        base, cand = groups[(rnd, vb, "held_out")], groups[(rnd, vc, "held_out")]
        st.subheader(f"Held-out questions: {vb} vs {vc}")
        with st.container(horizontal=True):
            for label, rs in ((vb, base), (vc, cand)):
                st.metric(f"{label}: answers right", f"{sum(r['answer_ok'] for r in rs)}/{len(rs)}", border=True)
                st.metric(f"{label}: no lookup", sum(not r["used_tool"] for r in rs), border=True)
        cmp = [{"question": a["question"], "lang": a["lang"], f"{vb} tools": ", ".join(json.loads(a["tools"])) or "none",
                f"{vb} right": bool(a["answer_ok"]), f"{vc} tools": ", ".join(json.loads(b["tools"])) or "none",
                f"{vc} right": bool(b["answer_ok"])} for a, b in zip(base, cand)]
        sel = st.dataframe(cmp, hide_index=True, on_select="rerun", selection_mode="single-row",
                           alt="Each held-out question before and after the patch")
        if sel.selection.rows:
            i = sel.selection.rows[0]
            a, b = st.columns(2)
            a.markdown(f"**{vb}** · {cmp[i][f'{vb} tools']}")
            a.markdown(base[i]["reply"])
            b.markdown(f"**{vc}** · {cmp[i][f'{vc} tools']}")
            b.markdown(cand[i]["reply"])
