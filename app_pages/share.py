import streamlit as st

from anubhav.learning import pack
from anubhav.ui import core

S = core.store()
st.title("Share with a new company")
st.caption("Only approved, regional site and place facts travel, re-written in the recipient's ids. "
           "Trucks, vendors, nicknames for them, capacities and evidence text stay private.")

with st.container(horizontal=True, vertical_alignment="bottom"):
    sources = st.pills("From", ["T01", "T02", "T03"], selection_mode="multi", default=["T01", "T02"], key="pack_src")
    target = st.selectbox("To", ["TNEW", "T01", "T02", "T03"], key="pack_dst")
    accept_rules = st.toggle("Accept enforced rules too", value=True)

if st.button("Publish and accept pack", icon=":material/share:", type="primary"):
    dst = core.company(target)
    for src in sources or []:
        if src == target:
            continue
        p = pack.publish(S, core.company(src), dst, approved_by=f"owner-{src}")
        ids = pack.import_pack(S, p, dst, accepted_by=f"owner-{target}", accept_policies=accept_rules)
        st.session_state.setdefault("packs", []).append(
            {"pack": p["pack_id"], "items": len(p["items"]), "skipped": len(p["skipped"]),
             "leaks": pack.leaks(p, core.company(src)), "imported": ids})
    st.rerun()

for p in st.session_state.get("packs", []):
    st.success(f"{p['pack']}: {p['items']} lessons shared, {p['skipped']} skipped (no matching site), "
               f"leaks: {len(p['leaks'])}", icon=":material/verified_user:")

dst = core.company(target)
active = S.list(target, {"ACTIVE_POLICY", "ACTIVE_ADVISORY"})
imported = [l for l in active if l["source"].startswith("pack:")]
st.subheader(f"What {target} received")
if not imported:
    st.caption("Nothing yet.")
else:
    merged = {}
    for l in imported:      # the same lesson from several partners shows once, with all its confirmations
        k = (l["kind"], tuple(sorted((k, str(v)) for k, v in l["params"].items())))
        merged.setdefault(k, []).append(l)
    knowledge, _, _ = S.active_for(target, dst)
    text = {k.rsplit(" [", 1)[1].split()[-1].rstrip("]"): k.rsplit(" [", 1)[0] for k in knowledge}
    st.dataframe([{"Lesson": text.get(ls[0]["lesson_id"], ls[0]["kind"]),
                   "Confirmed by": (lambda n: f"{n} compan{'y' if n == 1 else 'ies'}")(len(ls[0]["gate"].get("confirmed_by") or ls)),
                   "Arrives as": "rule" if any(x["state"] == "ACTIVE_POLICY" for x in ls) else "advice"}
                  for ls in merged.values()], hide_index=True, alt="Lessons received from partner companies")
    if st.button("Revoke all packs", icon=":material/block:"):
        for pid in {p for l in imported for p in (l["gate"].get("confirmed_by") or [l["source"].split(":", 1)[1]])}:
            pack.revoke(S, pid, target, "owner")
        st.rerun()
