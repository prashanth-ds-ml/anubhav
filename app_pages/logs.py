import json

import streamlit as st

from anubhav.ui import core, logs

cid = st.session_state.company
st.title("Logs: what the agent did and learned")
st.caption("One timeline, built only from what is recorded: every agent run (each step it planned, each tool it called, "
           "what came back, the code checks at the end), every lesson proposed, checked and reviewed, every tool-use "
           "patch and its test, and every piece of feedback. Nothing here is written by the model about itself.")

S = core.store()
H = core.harness_store()
lessons = {l["lesson_id"]: l for l in S.list(cid)}
rows = logs.events(cid, runs=core.recent_runs(200), lesson_events=S.events(company=cid), lessons=lessons,
                   versions=H.versions(), feedback=H.feedback())

st.markdown("**Meta models at work**")
with st.container(horizontal=True):
    for m in logs.model_roles(core.recent_runs(500), S.list(cid), H.versions()):
        with st.container(border=True):
            st.markdown(f"**{m['model']}** · :gray[{m['access']}]")
            st.caption(m["role"])
            st.markdown(f":blue-badge[{m['count']}]")

with st.container(horizontal=True):
    for key, label in logs.STREAMS.items():
        st.metric(label, sum(r["stream"] == key for r in rows), border=True)

streams = st.pills("Show", list(logs.STREAMS), format_func=logs.STREAMS.get, selection_mode="multi",
                   default=list(logs.STREAMS), key="log_streams")
shown = [r for r in rows if r["stream"] in (streams or [])]
if not shown:
    st.info(f"Nothing recorded yet for {cid}. Ask something on the Workbench, or load lessons in the sidebar.",
            icon=":material/history:")
    st.stop()

ICON = {"run": "🤖", "lesson": "📘", "harness": "🔧", "feedback": "💬"}
sel = st.dataframe([{"when": r["ts"].replace("T", " ")[:16], "": ICON[r["stream"]], "stream": logs.STREAMS[r["stream"]],
                     "what": r["what"], "who": r["who"], "detail": r["detail"]} for r in shown],
                   hide_index=True, on_select="rerun", selection_mode="single-row", key="log_table",
                   column_config={"": st.column_config.TextColumn(width="small"), "what": st.column_config.TextColumn(width="large")},
                   alt="Everything the agent did and learned, newest first")

# nothing selected: open the newest run that called tools, so the timeline shows something
pick = shown[sel.selection.rows[0]] if sel.selection.rows else next(
    (r for r in shown if r["stream"] == "run" and any(s["type"] == "tool" for s in r["raw"]["trace"])), None)
if not pick:
    st.caption("Select a row to see its details.")
    st.stop()

st.subheader(f"{ICON[pick['stream']]} {pick['what']}")
st.caption(f"{pick['ts'].replace('T', ' ')} · {pick['who']} · {pick['detail']}")
if pick["stream"] == "run":
    r = pick["raw"]
    st.markdown(f"**Request:** {r['request']}")
    KIND = {"plan": (":material/psychology:", "blue", "Plan"), "answer": (":material/chat:", "blue", "Answer"),
            "act": (":material/build:", "gray", "Act"), "observe": (":material/visibility:", "green", "Observe"),
            "refused": (":material/block:", "red", "Refused"), "error": (":material/cloud_off:", "red", "Model error"),
            "check": (":material/fact_check:", "violet", "Code check")}
    for i, row in enumerate(logs.timeline(r, core.summarize)):
        icon, color, label = KIND[row["kind"]]
        if row["kind"] == "check" and not row.get("ok", True):
            color = "red"
        with st.container(horizontal=True, vertical_alignment="top", gap="small"):
            st.badge(label, icon=icon, color=color, width=110)
            with st.expander(row["text"], expanded=False):
                st.json(row["raw"], expanded=1)
    st.markdown(f"**Reply** ({r.get('stop')}, {r.get('turns')} model turns, ${r.get('cost_usd', 0):.3f}):")
    st.markdown(r.get("reply") or "_(no reply)_")
    with st.expander("What the model was given (system knowledge for this run)"):
        st.write(r.get("knowledge") or "No approved lessons were given (day-1 setting).")
        if r.get("harness", {}).get("version_id"):
            st.caption(f"Harness version {r['harness']['version_id']}")
else:
    st.json(json.loads(json.dumps(pick["raw"], default=str)), expanded=2)
