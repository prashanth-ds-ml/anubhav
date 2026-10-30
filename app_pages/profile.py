import streamlit as st

from anubhav.learning import profile
from anubhav.ui import core

cid = st.session_state.company
C = core.company(cid)
S = core.store()
st.title("Business profile")
st.caption("Session 0: before planning, the agent learns what this business is. The facts are counted from the "
           "company's own records; the owner adds what records can't show. The agent reads a short version of it "
           "on every live run, as information, never as an instruction. Owner statements are not rules: rules still "
           "come from the records, the evidence gate and a reviewer.")

saved = profile.latest(S, cid)
facts = saved["facts"] if saved else profile.from_records(C)

st.subheader("From its records")
a = facts
with st.container(horizontal=True):
    st.metric("Customer sites", a["service_area"]["sites"], f"in {a['service_area']['towns']} towns", delta_color="off", border=True)
    st.metric("Vehicles", a["fleet"]["vehicles"], f"{a['fleet']['own']} own · {a['fleet']['hired']} hired", delta_color="off", border=True)
    st.metric("Orders a day", a["volume"]["orders_per_day"], f"{a['volume']['orders']} in {a['volume']['days']} days", delta_color="off", border=True)
    st.metric("Client brands", a["clients"]["brands"], ", ".join(a["clients"]["largest"][:2]), delta_color="off", border=True)
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Goods (share of cases)**")
    st.bar_chart({k: v for k, v in a["goods"]["by_share"].items()}, horizontal=True, height=180, y_label="%")
    st.caption(f"Most sites in {', '.join(a['service_area']['most_sites_in'])} · busiest days "
               f"{', '.join(a['busiest_days']['top'])}, quietest {a['busiest_days']['quietest']}")
with right:
    st.markdown("**Fleet by class**")
    st.bar_chart(a["fleet"]["classes"], horizontal=True, height=180)
    st.caption("Planner languages: " + ", ".join(f"{k} {v}%" for k, v in a["planner_languages"]["by_share"].items())
               + f" · {a['written_policies']['count']} written policies")
with st.expander("Where each fact comes from"):
    st.dataframe([{"fact": k.replace("_", " "), "table(s)": v["source"]} for k, v in a.items()], hide_index=True,
                 alt="The record tables each profile fact was counted from")

st.subheader("From the owner")
owner = saved["owner"] if saved else {}
with st.form("owner", border=True):
    vals = {k: st.text_input(label, value=owner.get(k, ""), max_chars=profile.MAX_FIELD) for k, label in profile.OWNER_FIELDS.items()}
    if st.form_submit_button("Save profile (new version)", icon=":material/save:", type="primary"):
        saved = profile.save(S, C, "owner", vals)
        st.toast(f"Saved version {saved['version']}. The agent reads it from the next live run.")
        st.rerun()

st.subheader("What the agent reads")
if saved:
    st.code(profile.render(saved), language=None, wrap_lines=True)
    st.caption(f"Version {saved['version']} · saved {saved['ts'].replace('T', ' ')} by {saved['actor']} · "
               f"{len(profile.render(saved))}/{profile.MAX_BLOCK} characters")
    hist = profile.versions(S, cid)
    if len(hist) > 1:
        with st.expander(f"{len(hist)} versions"):
            st.dataframe([{"version": v["version"], "saved": v["ts"], "by": v["actor"], **v["owner"]} for v in hist],
                         hide_index=True, alt="Saved versions of the business profile")
else:
    st.info("Nothing yet: save the profile once (even with the owner fields empty) and the agent starts reading it.",
            icon=":material/info:")
