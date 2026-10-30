import streamlit as st

from anubhav.harness import loop
from anubhav.harness.store import CATEGORIES, PatchError, diff
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData
from anubhav.ui import core

H = core.harness_store()
cid = st.session_state.company
st.title("Tuning: how the agent works")
st.caption("Loop A. The agent improves how it uses its tools and how it answers, from its own runs and from "
           "native-speaker feedback. Every change is one small patch, tested old-vs-new, and needs your approval. "
           "Business facts never go here (they are lessons); the harness is shared by every client.")

active = H.active()
with st.container(horizontal=True):
    st.metric("Active version", active["version_id"], border=True)
    st.metric("Feedback waiting", len([f for f in H.feedback("new") if f["rating"] == 0]), border=True)
    st.metric("Thumbs up", len([f for f in H.feedback() if f["rating"] == 1]), border=True)
    st.metric("Versions tried", len(H.versions()) - 1, border=True)

st.subheader("1 · What went wrong")
fb = H.feedback()
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Tester feedback**")
    down = [f for f in fb if f["rating"] == 0]
    if down:
        st.dataframe([{"id": f["feedback_id"], "status": f["status"], "category": CATEGORIES.get(f["category"], f["category"]),
                       "note": f["note"], "request": f["request"]} for f in down], hide_index=True,
                     alt="Feedback from testers")
    else:
        st.caption("No thumbs-down yet. Give feedback under any reply on the Workbench.")
runs = core.recent_runs()
problems = loop.collect(runs, [f for f in fb if f["status"] == "new"])
with right:
    st.markdown(f"**From the agent's own last {len(runs)} runs**")
    if problems["trace_issues"]:
        st.dataframe([{"issue": i["kind"], "tool": i["tool"] or "", "times": i["count"],
                       "example": i["examples"][0]["detail"]} for i in problems["trace_issues"]], hide_index=True,
                     alt="Problems the agent detected in its own runs")
    else:
        st.caption("No tool errors, repeats or limit hits in recent runs.")

st.subheader("2 · Propose one fix")
off = core.live_ready("spark")
if off:
    st.caption(f":material/info: {off}")
client = None
if st.button("Ask Muse for a patch", icon=":material/auto_awesome:", type="primary",
             disabled=bool(off) or not (problems["feedback"] or problems["trace_issues"]), help=off):
    client, off = core.live_client("spark")
if client:
    C = core.company(cid)
    b = Broker(C, Session(cid))
    with st.spinner("Muse Spark is reading the problems…"):
        patch, meta = loop.propose(client, b, active["surfaces"], problems)
    try:
        v = H.propose(patch, patch.get("rationale", ""), [t.name for t in b.list_tools()], C)
        st.session_state["addresses"] = {v["version_id"]: [x for x in patch.get("addresses", []) if str(x).startswith("FB-")]}
        st.toast(f"Candidate {v['version_id']} proposed (${meta['cost_usd']:.3f}).")
    except PatchError as e:
        st.error(f"Patch refused by the rules: {e}", icon=":material/block:")
        st.json(patch)

st.subheader("3 · Test and decide")
cands = [v for v in H.versions() if v["status"] == "candidate"]
if not cands:
    st.caption("No candidates waiting.")
for v in cands:
    with st.container(border=True):
        st.markdown(f"**{v['version_id']}** (from {v['parent']}) · {v['rationale']}")
        st.code("\n".join(diff(H.get(v["parent"])["surfaces"], v["surfaces"])) or "(no change)", language="diff")
        if not v["probe"]:
            new_fb = [f for f in fb if f["rating"] == 0 and f["status"] == "new"]
            cases = [{"request": f["request"], "company": f["company"], "use_lessons": bool(f["use_lessons"]),
                      "origin": f"feedback {f['feedback_id']}", "feedback_id": f["feedback_id"], "expects_draft": False}
                     for f in new_fb[:3]]
            cases += [{"request": core.SUGGESTIONS["Roman Telugu"], "company": cid, "use_lessons": False,
                       "origin": "regression (golden path)", "expects_draft": True},
                      {"request": core.SUGGESTIONS["Ambiguous"], "company": cid, "use_lessons": False,
                       "origin": "regression (ambiguity)", "expects_draft": False}]
            st.caption(f"Paired test: {len(cases)} requests × old and new on Muse Spark Open (~${len(cases) * 0.1:.2f}).")
            probe_off = core.live_ready("open") or core.live_ready("spark")
            if st.button("Run paired test", key=f"probe:{v['version_id']}", icon=":material/science:",
                         disabled=bool(probe_off), help=probe_off) and (agent := core.live_client("open")[0])                     and (judge := core.live_client("spark")[0]):
                fb_by_id = {f["feedback_id"]: {"note": f["note"], "category": CATEGORIES.get(f["category"])} for f in new_fb}
                with st.spinner("Running old and new versions on the same requests…"):
                    C = CompanyData(core.WORLD, cid, core.WORLD / "runtime" / "probe")
                    res = loop.probe(C, agent, judge, cases, H.get(v["parent"])["surfaces"],
                                     v["surfaces"], fb_by_id, core.knowledge_for)
                H.record_probe(v["version_id"], res)
                st.rerun()
        else:
            g = v["probe"]["gate"]
            if g["pass"]:
                st.success("Passed: no lost drafts, no new tool errors, cost within limit, problem improved.",
                           icon=":material/check_circle:")
            else:
                st.warning("Did not pass: " + "; ".join(g["reasons"]), icon=":material/cancel:")
            if v["probe"].get("kind") == "practice":
                pb, pc = v["probe"]["base"], v["probe"]["cand"]
                st.caption(f"Held-out practice: answers right {pb['answer_ok']:.0%} → {pc['answer_ok']:.0%} · "
                           f"no lookup {pb['no_lookup']:.0%} → {pc['no_lookup']:.0%} · tool errors {pb['tool_errors']} → "
                           f"{pc['tool_errors']} · golden drafts {v['probe']['golden']} · details on the Skills page")
            else:
                fa = g["feedback_addressed"]
                st.caption(f"Feedback addressed (Muse judge, diagnostic): old {fa['base']}/{fa['of']} → new {fa['cand']}/{fa['of']} · "
                           f"cost ${g['cost']['base']} → ${g['cost']['cand']}")
            for row in ([] if v["probe"].get("kind") == "practice" else v["probe"]["rows"]):
                with st.expander(f"{row['origin']}: {row['request'][:70]}"):
                    a, b = st.columns(2)
                    a.markdown(f"**Old** · {row['base']['tool_calls']} calls, {row['base']['tool_errors']} errors, "
                               f"drafts {row['base']['drafts']}")
                    a.markdown(row["base_reply"])
                    b.markdown(f"**New** · {row['cand']['tool_calls']} calls, {row['cand']['tool_errors']} errors, "
                               f"drafts {row['cand']['drafts']}")
                    b.markdown(row["cand_reply"])
            with st.container(horizontal=True):
                if core.PUBLIC:        # the harness is shared by every visitor: decisions only in a local run
                    st.caption("Activate and reject are available when you run it locally.")
                elif st.button("Activate", key=f"ok:{v['version_id']}", icon=":material/check:", type="primary",
                             disabled=not g["pass"]):
                    H.decide(v["version_id"], "reviewer", True)
                    H.mark_feedback([f["feedback_id"] for f in fb if f["status"] == "new" and f["rating"] == 0], "addressed")
                    st.rerun()
                if not core.PUBLIC and st.button("Reject", key=f"no:{v['version_id']}", icon=":material/close:"):
                    H.decide(v["version_id"], "reviewer", False)
                    st.rerun()

st.subheader("Versions")
st.dataframe([{"version": v["version_id"], "status": v["status"], "from": v["parent"], "why": v["rationale"],
               "decided by": v["decided_by"]} for v in H.versions()], hide_index=True, alt="Harness versions")
if active["parent"] and not core.PUBLIC and st.button("Roll back to the previous version", icon=":material/undo:"):
    H.rollback("reviewer")
    st.rerun()
with st.expander("Active harness (what the agent is told, in addition to its base prompt)"):
    st.json(active["surfaces"])
