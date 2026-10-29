import json
import sqlite3

import streamlit as st

from anubhav import trace
from anubhav.data.config import ROOT

st.title("Proof & audit")
runs = sorted((ROOT / "artifacts" / "learning").glob("exp008_*.json"))
if not runs:
    st.info("No EXP-008 results found.")
    st.stop()
d = json.loads(runs[-1].read_text(encoding="utf-8"))
st.caption(f"EXP-008 · pre-registered and frozen before any model call · {runs[-1].name}")

B = d["B"]
def safe(company, lessons):
    rs = [r for r in B if r["company"] == company and r["lessons"] == lessons]
    return sum(r["safe"] for r in rs), len(rs)

st.subheader("Same request, same model: does learning change the choice?")
with st.container(horizontal=True):
    for label, c, l in (("T01 before", "T01", False), ("T01 with its lessons", "T01", True),
                        ("New company cold", "TNEW", False), ("New company + pack", "TNEW", True)):
        s, n = safe(c, l)
        st.metric(label, f"{s} / {n} safe", border=True)
st.caption("Safe = every draft for the Jangaon order uses a vehicle of 22 ft or less. "
           "All safe runs were safe on the first attempt; pack leaks: "
           f"{sum(len(p['leaks']) for p in d.get('packs', []))}.")

st.subheader("How good is the mining?")
A0 = {k: v for k, v in d["A"].items() if k.endswith("#0")}
passed = sum(v["passed"] for v in A0.values())
true_passed = sum(round((v["precision"] or 0) * v["passed"]) for v in A0.values())
learn = sum(len(v["learnable"]) for v in A0.values())
found = sum(len(v["found"]) for v in A0.values())
with st.container(horizontal=True):
    st.metric("Recall", f"{found / learn:.0%}", "bar 60%", delta_color="off", border=True)
    st.metric("Precision", f"{true_passed / passed:.0%}", "bar 85%: not met", delta_color="inverse", border=True)
    st.metric("Traps let in", sum(len(v["traps_admitted"]) for v in A0.values()), border=True)
st.caption("The misses: closing-time lessons with the wrong hour and a noisy spot-truck pattern. "
           "Next experiment tightens these checks; every lesson still needs a reviewer.")

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
