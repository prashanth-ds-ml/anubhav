import streamlit as st

from anubhav.learning import newtools as nt
from anubhav.runtime.query import sandbox
from anubhav.ui import core

cid = st.session_state.company
C = core.company(cid)
S = core.store()
sb = sandbox(C)
st.title("New tools")
st.caption("When no tool fits, the agent may write one read-only query over the company's records. A query it needed "
           f"again for another request (used for {nt.MIN_USES}+ different requests) is a candidate tool. Code turns its "
           "values into parameters and checks it: with the original values it must return the original rows, and it "
           f"must work on {nt.HELD_OUT} values it never saw. Only a person can make it a tool. Then the agent calls it in "
           "one step, like any other tool. Tools stay private to this company.")

mine = nt.tools(S, cid)
active = [t for t in mine if t["status"] == "active"]
waiting = [t for t in mine if t["status"] == "candidate"]
known = {t["tool_id"].rsplit("-", 1)[-1] for t in mine}
fresh = [g for g in nt.groups(core.recent_runs(500), cid, sb) if g["key"][:8] not in known]

with st.container(horizontal=True):
    st.metric("Tools in use", len(active), border=True)
    st.metric("Waiting for approval", len(waiting), border=True)
    st.metric("Reused queries", sum(len(g["requests"]) >= nt.MIN_USES for g in fresh), border=True)
    st.metric("Queries written (not yet tools)", len(fresh), border=True)


def show_params(params):
    st.caption("Parameters: " + ", ".join(f"`{p['name']}` ({'date' if p['kind'] == 'date' else p['column']}, e.g. {p.get('example') or p.get('value')})"
                                          for p in params))


st.subheader("Tools in use")
if not active:
    st.caption("None yet.")
for t in active:
    with st.container(border=True):
        st.markdown(f"**`{t['name']}`** · {t['description']}")
        show_params(t["params"])
        st.code(t["template"], language="sql", wrap_lines=True)
        st.caption(f"Approved by {t['decided_by']} on {t['decided'].replace('T', ' ')} · learned from "
                   f"{len(t['source'])} queries in runs {', '.join(s['run_id'] for s in t['source'])}")
        if st.button("Retire", key=f"ret:{t['tool_id']}", icon=":material/archive:"):
            nt.decide(S, t["tool_id"], "owner", False, "retired from the New tools page")
            st.rerun()

st.subheader("Waiting for your approval")
if not waiting:
    st.caption("Nothing waiting. Check a query below.")
for t in waiting:
    c = t["checks"] or {}
    with st.container(border=True):
        st.markdown(f"**`{t['name']}`** · {t['description']}")
        show_params(t["params"])
        st.code(t["template"], language="sql", wrap_lines=True)
        same = c.get("same_rows", [])
        held = c.get("held_out", [])
        a, b = st.columns(2)
        a.markdown(("✅" if same and all(x["same"] for x in same) else "❌") + f" **Same rows** with the original values "
                   f"({sum(x['same'] for x in same)}/{len(same)})")
        b.markdown(("✅" if held and all(h["ok"] for h in held) else "❌") + f" **Held-out values** run: "
                   f"{sum(h['ok'] for h in held)}/{len(held)}, with rows: {sum(h.get('rows', 0) > 0 for h in held)}")
        with st.expander("Check details"):
            st.dataframe([{**h["values"], "ran": h["ok"], "rows": h.get("rows"), "error": h.get("error", "")} for h in held],
                         hide_index=True, alt="The held-out parameter values the tool was tested on")
            for r in c.get("reasons", []):
                st.error(r, icon=":material/block:")
        with st.container(horizontal=True):
            if st.button("Approve as a tool", key=f"ok:{t['tool_id']}", type="primary", icon=":material/check:",
                         disabled=not c.get("pass"), help=None if c.get("pass") else "Its checks failed"):
                nt.decide(S, t["tool_id"], "owner", True)
                st.toast(f"{t['name']} is now a tool. The agent sees it from the next live run.")
                st.rerun()
            if st.button("Reject", key=f"no:{t['tool_id']}", icon=":material/close:"):
                nt.decide(S, t["tool_id"], "owner", False, "rejected on the New tools page")
                st.rerun()

st.subheader("Queries the agent wrote")
if not fresh:
    st.info("No queries yet. Ask the Workbench a question no tool answers in live mode (for example, which weekday had "
            "the worst on-time deliveries last month).", icon=":material/query_stats:")
for g in fresh:
    reused = len(g["requests"]) >= nt.MIN_USES
    with st.container(border=True):
        st.markdown(("🔁 **Reused** " if reused else "") + f"for {len(g['requests'])} request(s): "
                    + " · ".join(f"_{r[:80]}_" for r in g["requests"][:3]))
        show_params(g["uses"][0]["params"])
        st.code(g["template"], language="sql", wrap_lines=True)
        with st.form(f"chk:{g['key']}", border=False):
            n1, n2 = st.columns([1, 2])
            name = n1.text_input("Tool name", value=nt.suggest_name(g), key=f"n:{g['key']}", max_chars=40)
            desc = n2.text_input("What it answers", value=nt.describe(g),
                                 key=f"d:{g['key']}", max_chars=300)
            if st.form_submit_button("Check it as a tool" if reused else "Check it anyway (used once)",
                                     icon=":material/rule:", type="primary" if reused else "secondary"):
                try:
                    nt.propose(S, cid, g, nt.check(g, sb), name, desc)
                    st.rerun()
                except ValueError as e:
                    st.warning(str(e), icon=":material/edit:")
