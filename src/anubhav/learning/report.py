"""The weekly 'What I learned' report for a company owner: what the agent proposed, what passed the evidence
check, what a reviewer approved, what was rejected and why, and what stopped being true."""

from collections import Counter

STATE_LABEL = {"ACTIVE_POLICY": "approved rule", "ACTIVE_ADVISORY": "approved advice", "CANDIDATE": "waiting for review",
               "NEEDS_EVIDENCE": "waiting (one piece of evidence)", "REJECTED": "rejected", "EXPIRED": "no longer true",
               "CHALLENGED": "challenged by new evidence", "RETIRED": "retired"}


def weekly(store, company, C):
    rows = store.list(company)
    c = Counter(r["state"] for r in rows)
    L = [f"# What I learned: {company} (week ending {C.today})", "",
         f"**Ee vaaram nenu nerchukunnavi** ('what I learned this week'). {len(rows)} lessons proposed from your own records: "
         + ", ".join(f"{n} {STATE_LABEL.get(s, s)}" for s, n in c.most_common()) + ".", ""]
    sections = [("Approved and in use", ("ACTIVE_POLICY", "ACTIVE_ADVISORY")),
                ("Waiting for your review", ("CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED")),
                ("No longer true", ("EXPIRED", "RETIRED")), ("Rejected (and why)", ("REJECTED",))]
    knowledge, _, _ = store.active_for(company, C)
    by_id = {k.rsplit(" ", 1)[-1].rstrip("]"): k for k in knowledge}
    for title, states in sections:
        sel = [r for r in rows if r["state"] in states]
        if not sel:
            continue
        L += [f"## {title} ({len(sel)})", "| Lesson | What | Evidence check | Status |", "|---|---|---|---|"]
        for r in sel:
            what = by_id.get(r["lesson_id"], "").rsplit(" [", 1)[0] or r["claim"] or f"{r['kind']} {r['params']}"
            L.append(f"| {r['lesson_id']} | {what} | {r['gate']['reason']} | {STATE_LABEL.get(r['state'], r['state'])} |")
        L.append("")
    L.append("Approve, narrow, reject or undo any of these in the Learning Lab. Nothing becomes a rule without your approval.")
    return "\n".join(L) + "\n"
