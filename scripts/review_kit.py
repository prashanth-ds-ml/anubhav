"""Builds the dispatcher review kit (D-043, I4): learned lessons as a sheet a real dispatcher can judge, plus a timing
protocol. The sites and companies are fictional, so the dispatcher judges two things they can know: is this KIND of
rule real in their region, and, given only the evidence shown, would they approve it as advice, as an enforced rule,
or reject it. No model calls. Output: docs/review_kit/dispatcher_review.md

  uv run python scripts/review_kit.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anubhav.learning.store import describe  # noqa: E402
from anubhav.ui import core  # noqa: E402

OUT = core.ROOT / "docs" / "review_kit" / "dispatcher_review.md"
KIND = {"site_access": "A site's gate or road limits truck length", "night_only": "A site receives only at night",
        "weekly_off": "A shop is closed one day a week", "receiving_hours": "A site stops receiving at a fixed hour",
        "alias": "Planners use a nickname for a truck, vendor or site", "real_capacity": "A truck safely carries less than its paper payload",
        "vendor_reliability": "A hired-truck vendor often fails at month end", "closure": "A road or bridge is closed for a period",
        "moved_site": "A customer moved", "time_window": "A site accepts some trucks only at certain hours",
        "vehicle_requirement": "A site needs a particular kind of vehicle"}


def evidence(les):
    g = les.get("gate") or {}
    parts = [f"{g.get('support', 0)} supporting record(s)", f"{g.get('counter', 0)} against"]
    ev = (les.get("miner") or {}).get("evidence") or []
    return "; ".join(parts) + (f". Example: {ev[0][:140]}" if ev else "")


def main():
    S = core.store()
    if not S.list("T01"):
        core.load_exp008_lessons()
    rows = []
    for cid in ("T01", "T02"):
        C = core._company(cid)
        rows += [(cid, les, describe(les, C)) for les in S.list(cid)]
    rows = rows[:15]
    lines = [
        "---", "tags: [impact, review]", "---",
        "# Dispatcher review kit (for the interviewed logistics professional)", "",
        "**Purpose.** A real dispatcher checks what the agent learned. The companies and sites are fictional (generated), "
        "so we do **not** ask whether a named site is right. We ask two things you can judge from experience:",
        "1. **Is this kind of rule real in your region?** (yes, common · yes, rare · no · not sure)",
        "2. **Given only the evidence shown, what would you do as the reviewer?** (approve as advice · approve as an "
        "enforced rule · reject · need more evidence)", "",
        "**ఉద్దేశ్యం.** ఏజెంట్ నేర్చుకున్న నియమాలను ఒక నిజమైన డిస్పాచర్ చూస్తారు. కంపెనీలు, సైట్లు కల్పితం, కాబట్టి "
        "ఆ పేరున్న సైట్ సరైనదా అని అడగం. రెండు ప్రశ్నలు మాత్రమే: (1) ఇలాంటి నియమం మీ ప్రాంతంలో నిజంగా ఉంటుందా? "
        "(2) చూపిన ఆధారాలతో మాత్రమే, మీరు దీన్ని సలహాగా ఆమోదిస్తారా, తప్పనిసరి నియమంగా ఆమోదిస్తారా, తిరస్కరిస్తారా, "
        "లేదా ఇంకా ఆధారం కావాలంటారా?", "",
        "**Rules for recording (honesty).** Write the answers exactly as given, including \"no\" and \"not sure\". "
        "Do not explain or argue before they answer. Record the reviewer as \"a logistics professional (Telangana)\", "
        "never by name, and quote them only with their permission. Results go into [[experiments]] as they are, "
        "even if they are bad for us.", "",
        "## Part 1: the lessons", "",
        "| # | What the agent learned | Kind of rule | Evidence it was shown | Real in your region? | Your decision | Comment |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, (cid, les, text) in enumerate(rows, 1):
        lines.append(f"| {i} | {text} | {KIND.get(les['kind'], les['kind'])} | {evidence(les)} | | | |")
    lines += [
        "", f"_Generated from the EXP-008 lessons ({len(rows)} items, {', '.join(sorted({c for c, _, _ in rows}))}) by "
            "`scripts/review_kit.py`. Includes lessons the gate let through with counter-evidence: a good test of the reviewer._", "",
        "## Part 2: timing \"plan tomorrow\" (optional, ~30 min)", "",
        "1. Print the open-orders list for T03's next day (21 orders) with the vehicles free that day "
        "(Workbench → \"Open orders for tomorrow\", company T03; the agent's own `plan_board` view).",
        "2. Ask the dispatcher to plan it the way they do at work, on paper. Time it. Do not help.",
        "3. Show the agent's plan from the saved run (the local app's Logs page, T03 \"plan tomorrow\" run of Oct 30: 16 drafts covering 18 of 21 orders).",
        "4. Ask, for each draft: would you send it as is · send with a change (which) · not send (why).",
        "5. Record: their minutes, the agent's minutes, drafts accepted as is / with a change / rejected, and anything the agent missed.", "",
        "## Part 3: three open questions", "",
        "- Which of these rules would you never let a system enforce on its own? Why?",
        "- What does the agent not know that you would check first every morning?",
        "- Would you use this if it only drafted and you approved every lesson? What would stop you?", "",
        "## Results (fill in after the session)",
        "| Date | Lessons judged | Kind is real (yes, common / rare / no / not sure) | Decisions (advice / rule / reject / more evidence) | Timing (them / agent) | Drafts (as is / changed / rejected) | Permission to quote |",
        "|---|---|---|---|---|---|---|",
        "| | | | | | | |", "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} lessons)")


if __name__ == "__main__":
    main()
