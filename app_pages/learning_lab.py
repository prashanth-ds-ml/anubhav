import streamlit as st

from anubhav import muse
from anubhav.learning import digest, miner
from anubhav.learning.store import ReviewError
from anubhav.ui import core

cid = st.session_state.company
C, S = core.company(cid), core.store()

st.title("Learning Lab")
st.caption("Muse proposes lessons from the company's own records; code checks the evidence; you decide.")

lessons = S.list(cid)
states = [l["state"] for l in lessons]
with st.container(horizontal=True):
    st.metric("Trips read", f"{len(C.t.get('shipments', [])):,}", border=True)
    st.metric("Driver notes", f"{len(C.t.get('driver_notes', [])):,}", border=True)
    st.metric("Lessons", len(lessons), border=True)
    st.metric("Waiting for you", sum(s in ("CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED") for s in states), border=True)
    st.metric("Approved", sum(s in ("ACTIVE_POLICY", "ACTIVE_ADVISORY") for s in states), border=True)

with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Mine my records now", icon=":material/auto_awesome:", type="primary"):
        with st.spinner("Muse Spark is reading 90 days of records…"):
            F, d = digest.build(C)
            props, meta = miner.mine(muse.client("spark"), C, d)
            S.add_proposals(cid, F, props, meta)
        st.toast(f"{len(props)} proposals checked by the gate (${meta['cost_usd']:.3f}).")
        st.rerun()
    st.caption("Uses Muse Spark (~$0.07). Or load the EXP-008 lessons from the sidebar for free.")

if not lessons:
    st.info("No lessons yet for this company.", icon=":material/school:")
    st.stop()

LABEL = {"CANDIDATE": "to review", "NEEDS_EVIDENCE": "to review (1 observation)", "ACTIVE_POLICY": "rule",
         "ACTIVE_ADVISORY": "advice", "REJECTED": "rejected", "EXPIRED": "no longer true", "CHALLENGED": "challenged",
         "RETIRED": "retired"}
knowledge, _, _ = S.active_for(cid, C)
rows = [{"Lesson": l["lesson_id"], "Status": LABEL.get(l["state"], l["state"]), "Kind": l["kind"],
         "What": l["claim"] or str(l["params"]), "Evidence check": l["gate"]["reason"]} for l in lessons]
left, right = st.columns([3, 2], gap="large")
with left:
    sel = st.dataframe(rows, hide_index=True, on_select="rerun", selection_mode="single-row", key="lessons",
                       alt="Lessons proposed from this company's records")
picked = lessons[sel.selection.rows[0]] if sel.selection.rows else lessons[0]

with right:
    l = picked
    st.subheader(l["lesson_id"])
    st.markdown(f"**{l['claim'] or l['kind']}**")
    st.caption(f"{l['kind']} · {LABEL.get(l['state'], l['state'])} · source: {l['source']}")
    st.markdown(f":material/rule: **Evidence check:** {l['gate']['reason']}")
    m = l.get("miner") or {}
    if m.get("evidence"):
        st.markdown("**Muse's evidence**")
        for e in m["evidence"]:
            st.caption(f"• {e}")
    if m.get("counter_evidence") or m.get("alternatives"):
        st.markdown("**Against / other explanations**")
        for e in (m.get("counter_evidence") or []) + (m.get("alternatives") or []):
            st.caption(f"• {e}")
    with st.form(f"review:{l['lesson_id']}"):
        verified = st.text_input("What did you verify? (needed for a rule)", placeholder="e.g. called the driver")
        a, b, c, d = st.columns(4)
        rule = a.form_submit_button("Rule", icon=":material/gavel:", width="stretch",
                                    disabled=not l["gate"].get("enforceable") or l["state"] != "CANDIDATE")
        advice = b.form_submit_button("Advice", icon=":material/lightbulb:", width="stretch")
        reject = c.form_submit_button("Reject", icon=":material/block:", width="stretch")
        undo = d.form_submit_button("Undo", icon=":material/undo:", width="stretch")
    try:
        if rule:
            S.approve(l["lesson_id"], "reviewer", "policy", verified)
        elif advice:
            S.approve(l["lesson_id"], "reviewer", "advisory", verified)
        elif reject:
            S.reject(l["lesson_id"], "reviewer", verified or "rejected in review")
        elif undo:
            S.rollback(l["lesson_id"], "reviewer")
        if rule or advice or reject or undo:
            st.rerun()
    except ReviewError as e:
        st.error(str(e), icon=":material/error:")
    with st.expander("History"):
        for e in S.events(l["lesson_id"]):
            st.caption(f"{e['ts']} · {e['actor']} · {e['action']} · {e['from_state']} → {e['to_state']} {e['note'][:80]}")
