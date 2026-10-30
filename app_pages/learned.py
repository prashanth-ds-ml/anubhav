import altair as alt
import streamlit as st

from anubhav.learning import digest, miner, timeline
from anubhav.learning.store import describe
from anubhav.ui import core

cid = st.session_state.company
C, S = core.company(cid), core.store()

st.title("What it learned")
st.caption(f"{core.COMPANIES[cid]} · from its own {len(C.t.get('shipments', [])):,} trips, "
           f"{len(C.t.get('driver_notes', [])):,} driver notes and {len(C.t.get('planner_messages', [])):,} planner messages")

off = core.live_ready("spark")
if st.button("Learn from my records", icon=":material/auto_awesome:", type="primary", disabled=bool(off), help=off):
    client, off = core.live_client("spark")
    if client:
        with st.spinner("Reading 90 days of records and checking every finding against them…"):
            F, d = digest.build(C)
            props, meta = miner.mine(client, C, d)
            new = S.add_proposals(cid, F, props, meta)
        st.toast(f"{len(new)} new findings (${meta['cost_usd']:.2f}).")
        st.rerun()
if off:
    st.caption(f":material/info: {off} The lessons below were mined by Muse in EXP-008.")

lessons = S.list(cid)
if not lessons:
    st.info("Nothing learned yet. Click **Learn from my records** (about $0.06), or load the EXP-008 lessons "
            "from the sidebar for free.", icon=":material/school:")
    st.stop()


@st.cache_data(max_entries=8)
def knowable(cid, ids, _C, _lessons):
    end = max(o["delivery_date"] for o in _C.t["orders"]) if _C.t.get("orders") else "2026-10-29"
    return {r["lesson_id"]: r for r in timeline.curve(_C, _lessons, "2026-08-01", end)}


when = knowable(cid, tuple(l["lesson_id"] for l in lessons), C, lessons)
pts = sorted((w["learnable"], lid) for lid, w in when.items() if w["learnable"])
if pts:
    chart = [{"date": d, "lessons": i + 1, "what": describe(S.get(lid), C)} for i, (d, lid) in enumerate(pts)]
    base = alt.Chart(alt.Data(values=chart)).encode(x=alt.X("date:T", title=None), y=alt.Y("lessons:Q", title="Lessons learned"))
    st.altair_chart((base.mark_line(interpolate="step-after", color="#0F7A74") +
                     base.mark_circle(size=80, color="#0F7A74").encode(tooltip=["date:T", "what:N"])).properties(height=200),
                    alt="Lessons the agent could learn from the records, over the 90 days")
    st.caption("How it learned over time: each dot is the day the records first gave enough evidence.")

waiting = [l for l in lessons if l["state"] in ("CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED")]
in_use = [l for l in lessons if l["state"] in ("ACTIVE_POLICY", "ACTIVE_ADVISORY")]
ignored = [l for l in lessons if l["state"] in ("REJECTED", "EXPIRED", "RETIRED")]


def card(l, actions):
    w = when.get(l["lesson_id"], {})
    with st.container(border=True):
        st.markdown(f"**{describe(l, C)}**")
        why = l["gate"]["reason"]
        since = f" · knowable since {w['learnable']}" if w.get("learnable") else ""
        after = f" · {w['incidents_after']} more incidents after that" if w.get("incidents_after") else ""
        st.caption(f"Why it thinks so: {why}{since}{after}")
        if actions:
            a, b, _ = st.columns([1, 1, 4])
            if a.button("Use it", key=f"use:{l['lesson_id']}", icon=":material/check:", type="primary"):
                strong = l["state"] == "CANDIDATE" and l["gate"].get("enforceable")
                S.approve(l["lesson_id"], "owner", "policy" if strong else "advisory",
                          f"approved after checking the evidence: {why}")
                st.rerun()
            if b.button("Not true", key=f"no:{l['lesson_id']}", icon=":material/close:"):
                S.reject(l["lesson_id"], "owner", "owner said not true")
                st.rerun()
        else:
            st.caption(":green[:material/check_circle:] In use · " + ("enforced as a rule" if l["state"] == "ACTIVE_POLICY" else "given to the agent as advice"))


st.subheader(f"New findings ({len(waiting)})")
st.caption("Nothing is used until you say so.")
for l in waiting:
    card(l, True)
if not waiting:
    st.caption("All reviewed.")

if in_use:
    st.subheader(f"In use ({len(in_use)})")
    for l in in_use:
        card(l, False)

if ignored:
    with st.expander(f"What it ignored and why ({len(ignored)})"):
        for l in ignored:
            label = "no longer true" if l["state"] == "EXPIRED" else "not used"
            st.markdown(f"- **{describe(l, C)}**: {label}. {l['gate']['reason']}")
