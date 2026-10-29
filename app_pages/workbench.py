import tempfile
from pathlib import Path

import streamlit as st

from anubhav import muse
from anubhav.ui import core

cid, use = st.session_state.company, st.session_state.use_lessons
mode = st.session_state.model or "Replay (free)"
C = core.company(cid)
key = f"{cid}:{use}"
history = st.session_state.chat.setdefault(key, [])

st.title("Plan tomorrow")
st.caption(f"{cid} · {core.COMPANIES[cid]} · planning {C.today} deliveries · "
           + ("with approved lessons" if use else "day 1: only what the company's systems record"))

left, right = st.columns([3, 2], gap="large")


def render_run(r):
    with st.chat_message("assistant", avatar=":material/local_shipping:"):
        steps = core.tool_steps(r)
        with st.status(f"{len(steps)} tool calls · {r['turns']} model turns · ${r['cost_usd']:.3f}"
                       + (" · replay" if r.get("_replay") else ""), type="compact", state="complete"):
            for s in steps:
                with st.status(s["name"], type="step", state="complete" if s["ok"] else "error"):
                    st.caption(core.summarize(s))
        st.markdown(r["reply"] or "_(no reply)_")
        for k in core.lessons_used(r):
            st.badge(k.rsplit(" [", 1)[0][:90], icon=":material/school:", color="green")


with left:
    for item in history:
        with st.chat_message("user"):
            st.markdown(item["request"])
        render_run(item["run"])

    prompt = st.chat_input("Type in Roman Telugu, Telugu or English…", submit_mode="disable")
    if not history:
        pick = st.pills("Try", list(core.SUGGESTIONS), label_visibility="collapsed", key=f"pick:{key}")
        if pick:
            prompt = core.SUGGESTIONS[pick]
    audio = st.audio_input("Or speak (Muse Voice Transcribe)", sample_rate=16000, key=f"mic:{key}")
    if audio is not None and st.button("Use this voice note", icon=":material/mic:"):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio.getvalue())
        with st.spinner("Transcribing…"):
            t = muse.transcribe(Path(f.name), keywords=sorted({s["town"] for s in C.sites.values()}))
        st.info(t["transcript"] or "(empty)", icon=":material/mic:", title=f"Transcript · ${t['cost_usd']:.4f}")
        prompt = t["transcript"] or None

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        if mode == "Replay (free)":
            r = core.find_replay(cid, prompt, use)
            if r:
                r = dict(r, _replay=True)
            else:
                st.warning("No saved run for this request and setting. Switch Model to a live option.",
                           icon=":material/history:")
        else:
            with st.spinner("Muse is planning…"):
                r = core.run_live(cid, prompt, core.MODELS[mode], use)
        if r:
            history.append({"request": prompt, "run": r})
            st.rerun()

with right:
    last = history[-1]["run"] if history else None
    st.subheader("Draft")
    if last and core.drafts(last):
        for d in core.drafts(last):
            v = C.vehicles.get(d["vehicle_id"], {})
            with st.container(border=True):
                st.markdown(f"**{d['draft_id']}** · :green-badge[draft · not dispatched]")
                a, b = st.columns(2)
                a.metric("Vehicle", f"{d['vehicle_id']} · {v.get('length_ft')} ft")
                b.metric("Load", f"{d['load']['kg']:,.0f} kg", f"of {v.get('payload_kg', 0):,.0f} kg", delta_color="off")
                for w in d.get("warnings", []):
                    st.caption(f":orange[:material/warning:] {w['message']}")
    else:
        st.caption("No draft yet.")

    st.subheader("What it knows about the site")
    sites = []
    if last:
        for s in core.tool_steps(last):
            if s["name"] == "get_site_constraints" and s["ok"]:
                sites.append(s["result"])
    if sites:
        for res in sites[-1:]:
            with st.container(border=True):
                st.markdown(f"**{res['name']}, {res['town']}**")
                st.caption(f"Site master: {res['recorded_in_site_master']}")
                for p in res.get("approved_policies", []):
                    st.success(f"{p['rule']} ({p['id']})", icon=":material/gavel:")
                for x in res.get("advisories", []):
                    st.info(f"{x['text']} ({x['id']})", icon=":material/lightbulb:")
    else:
        st.caption("Ask about a site to see this.")

    with st.expander("Open orders for tomorrow"):
        b, _ = core.broker(cid, False)
        orders = b.call("list_open_orders", {})["result"]["orders"]
        st.dataframe([{k: o[k] for k in ("order_id", "site", "town", "window", "kg", "value_rs")} for o in orders],
                     hide_index=True, alt="Open orders for tomorrow")
