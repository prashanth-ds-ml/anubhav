"""Anubhav demo app.  Run:  uv run streamlit run streamlit_app.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))     # hosted runs don't install the package

import streamlit as st  # noqa: E402

from anubhav.ui import core  # noqa: E402

st.set_page_config(page_title="Anubhav", page_icon=":material/local_shipping:", layout="wide")
with st.spinner("First start: generating the demo world from its seed (about a minute)…"):
    core.ensure_world()

if "company" not in st.session_state:
    st.session_state.update(company="T01", model="Replay (free)", use_lessons=False, chat={})

with st.sidebar:
    st.markdown("### :material/local_shipping: Anubhav")
    st.caption("Learns a business's unwritten rules from its own records.")
    st.selectbox("Company", list(core.COMPANIES), key="company",
                 format_func=lambda c: f"{c} · {core.COMPANIES[c]}")
    st.segmented_control("Model", list(core.MODELS), key="model", selection_mode="single")
    st.toggle("Use approved lessons", key="use_lessons",
              help="Off = day 1 (only what the company's systems record). On = plus lessons a reviewer approved.")
    n_active = len(core.store().list(st.session_state.company, {"ACTIVE_POLICY", "ACTIVE_ADVISORY"}))
    st.caption(f"{n_active} approved lessons for {st.session_state.company}")
    with st.expander("Demo controls"):
        if st.button("Load EXP-008 lessons (free)", icon=":material/download:", width="stretch"):
            st.toast("Loaded the lessons mined and approved in EXP-008." if core.load_exp008_lessons()
                     else "No EXP-008 lesson store found.")
            st.rerun()
        if st.button("Clear all lessons", icon=":material/delete:", width="stretch"):
            core.clear_lessons()
            st.rerun()
        if st.button("Reset today's drafts", icon=":material/restart_alt:", width="stretch"):
            core.company(st.session_state.company).runtime.reset()
            st.session_state.chat = {}
            st.toast("Drafts and vehicle holds cleared.")
    if st.session_state.model != "Replay (free)":
        st.caption(f":orange[:material/payments:] Live mode calls Muse (about $0.05 per request), "
                   f"{core.LIVE_RUNS_PER_SESSION - st.session_state.get('live_runs', 0)} left this session.")

pages = {
    "Work": [st.Page("app_pages/workbench.py", title="Workbench", icon=":material/forum:", default=True)],
    "Learning": [st.Page("app_pages/learned.py", title="What it learned", icon=":material/school:")],
    "Share & proof": [
        st.Page("app_pages/share.py", title="Share", icon=":material/share:"),
        st.Page("app_pages/proof.py", title="Proof & audit", icon=":material/fact_check:"),
        st.Page("app_pages/logs.py", title="Logs", icon=":material/timeline:"),
        st.Page("app_pages/report.py", title="Weekly report", icon=":material/mail:"),
    ],
    "Advanced": [
        st.Page("app_pages/learning_lab.py", title="Lesson details", icon=":material/table_rows:"),
        st.Page("app_pages/skills.py", title="Tool skills", icon=":material/fitness_center:"),
        st.Page("app_pages/tuning.py", title="Tuning", icon=":material/tune:"),
    ],
}
st.navigation(pages, position="top").run()
