import streamlit as st

from anubhav.learning import report
from anubhav.ui import core

cid = st.session_state.company
st.title("Weekly report")
st.caption("What the owner receives every week (on the phone in the real product).")
with st.container(border=True):
    st.markdown(report.weekly(core.store(), cid, core.company(cid)))
