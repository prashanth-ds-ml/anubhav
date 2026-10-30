import tempfile
from pathlib import Path

import streamlit as st

from anubhav import muse
from anubhav.harness.store import CATEGORIES as CATS
from anubhav.ui import core, graphs

cid, use = st.session_state.company, st.session_state.use_lessons
mode = st.session_state.model or "Replay (free)"
C = core.company(cid)
key = f"{cid}:{use}"
history = st.session_state.chat.setdefault(key, [])

st.title("Plan tomorrow")
st.caption(f"{cid} · {core.COMPANIES[cid]} · planning {C.today} deliveries · "
           + ("with approved lessons" if use else "day 1: only what the company's systems record"))

left, right = st.columns([3, 2], gap="large")


def feedback_box(r):
    """Thumbs plus, on thumbs-down, what was wrong. Stored as tester feedback for Loop A (never as a rule)."""
    done = st.session_state.setdefault("fb_done", set())
    if r["run_id"] in done:
        st.caption(":material/check: Feedback saved, thank you")
        return
    rating = st.feedback("thumbs", key=f"fb:{r['run_id']}")
    if rating == 1:
        core.harness_store().add_feedback(cid, r, 1, "good", "")
        done.add(r["run_id"])
    elif rating == 0:
        with st.form(f"fbf:{r['run_id']}", border=True):
            cat = st.segmented_control("What was wrong?", list(CATS), format_func=CATS.get, default="not_from_data")
            note = st.text_area("How should it have answered or worked?", height=70,
                                placeholder="e.g. we don't need these kinds of answers here; stick to the data")
            if st.form_submit_button("Save feedback", icon=":material/rate_review:"):
                core.harness_store().add_feedback(cid, r, 0, cat or "other", note)
                done.add(r["run_id"])
                st.rerun()


def render_run(r):
    with st.chat_message("assistant", avatar=":material/local_shipping:"):
        steps = core.tool_steps(r)
        with st.status(f"{len(steps)} tool calls · {r['turns']} model turns · ${r['cost_usd']:.3f}"
                       + (" · replay" if r.get("_replay") else ""), type="compact", state="complete"):
            for s in steps:
                with st.status(s["name"], type="step", state="complete" if s["ok"] else "error"):
                    st.caption(core.summarize(s))
        if r.get("error"):
            st.warning("Muse didn't answer (the model call failed after retries). Drafts made so far are kept; "
                       "try again, or use Replay.", icon=":material/cloud_off:")
        st.markdown(r["reply"] or "_(no reply)_")
        rc = r.get("reply_check") or {}
        if rc and not rc["ok"]:
            st.warning("Code check of this reply: "
                       + "; ".join(([f"ids not found in this run: {', '.join(rc['unknown_ids'])}"] if rc["unknown_ids"] else [])
                                   + ([f"claims something was done ({', '.join(rc['claims'])}); only drafts exist"]
                                      if rc["claims"] else [])), icon=":material/fact_check:")
        for k in core.lessons_used(r):
            st.badge(k.rsplit(" [", 1)[0][:90], icon=":material/school:", color="green")
        if st.toggle("Show as a graph", key=f"g:{r['run_id']}", value=True):
            st.graphviz_chart(graphs.run_dot(r, C), width="content",
                              alt="The question, the tools the agent called in order, the lessons it used, and its decision")
        feedback_box(r)


with left:
    for item in history:
        with st.chat_message("user"):
            st.markdown(item["request"])
        render_run(item["run"])

    prompt = st.chat_input("Type in Roman Telugu, Telugu or English…", submit_mode="disable")
    if not history:
        replay = mode == "Replay (free)"
        options = core.replayable(cid, use) if replay else list(core.SUGGESTIONS)
        if options:
            pick = st.pills("Try", options, label_visibility="collapsed", key=f"pick:{key}")
            if pick:
                prompt = core.SUGGESTIONS[pick]
            if replay:
                st.caption(":material/history: Replay shows saved real runs for these requests. "
                           "Typed requests need a live model.")
        elif replay:
            other = [c for c in core.COMPANIES if c != cid and core.replayable(c, use)]
            st.info(f"No saved runs for {cid} with lessons {'on' if use else 'off'}. "
                    + (f"Try {', '.join(other)} in the sidebar" if other else "Try the other lessons setting")
                    + (", or switch Model to a live option." if not core.live_ready("open") else "."),
                    icon=":material/history:")
    with st.container(border=True):
        audio = st.audio_input(":material/mic: Speak in Telugu, Roman Telugu or English", sample_rate=16000,
                               key=f"mic:{key}:{len(history)}")
        sig = hash(audio.getvalue()) if audio is not None else None
        fresh = sig is not None and st.session_state.get("voice_sig") != sig   # a new recording: transcribe it once
        blocked = core.live_client("spark")[1] if fresh else None
        if blocked:
            st.warning(blocked.replace("Use Replay", "Voice needs Muse Voice Transcribe"), icon=":material/mic_off:")
        elif audio is not None:
            if fresh:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio.getvalue())
                try:
                    with st.spinner("Muse Voice Transcribe…"):
                        t = muse.transcribe(Path(f.name), keywords=sorted({s["town"] for s in C.sites.values()}))
                finally:
                    Path(f.name).unlink(missing_ok=True)
                st.session_state.update(voice_sig=sig, voice_text=t["transcript"],
                                        voice_meta=f"{t['audio_ms'] / 1000:.1f} s audio · ${t['cost_usd']:.4f}")
            with st.form(f"voice:{key}", border=False):
                text = st.text_area("Transcript (fix anything misheard, then send)", value=st.session_state.voice_text,
                                    height=80)
                st.caption(st.session_state.voice_meta)
                if st.form_submit_button("Send", icon=":material/send:", type="primary") and text.strip():
                    prompt = text.strip()

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
        elif blocked := core.live_ready(core.MODELS[mode]):
            r = None
            st.warning(blocked, icon=":material/block:")
        else:
            try:
                with st.spinner("Muse is planning…"):
                    r = core.run_live(cid, prompt, core.MODELS[mode], use, history)
            except muse.MissingKeyError as e:
                r = None
                st.warning(str(e), icon=":material/block:")
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
