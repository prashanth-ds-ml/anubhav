---
tags: [impact, review]
---
# Dispatcher review kit (for the interviewed logistics professional)

**Purpose.** A real dispatcher checks what the agent learned. The companies and sites are fictional (generated), so we do **not** ask whether a named site is right. We ask two things you can judge from experience:
1. **Is this kind of rule real in your region?** (yes, common · yes, rare · no · not sure)
2. **Given only the evidence shown, what would you do as the reviewer?** (approve as advice · approve as an enforced rule · reject · need more evidence)

**ఉద్దేశ్యం.** ఏజెంట్ నేర్చుకున్న నియమాలను ఒక నిజమైన డిస్పాచర్ చూస్తారు. కంపెనీలు, సైట్లు కల్పితం, కాబట్టి ఆ పేరున్న సైట్ సరైనదా అని అడగం. రెండు ప్రశ్నలు మాత్రమే: (1) ఇలాంటి నియమం మీ ప్రాంతంలో నిజంగా ఉంటుందా? (2) చూపిన ఆధారాలతో మాత్రమే, మీరు దీన్ని సలహాగా ఆమోదిస్తారా, తప్పనిసరి నియమంగా ఆమోదిస్తారా, తిరస్కరిస్తారా, లేదా ఇంకా ఆధారం కావాలంటారా?

**Rules for recording (honesty).** Write the answers exactly as given, including "no" and "not sure". Do not explain or argue before they answer. Record the reviewer as "a logistics professional (Telangana)", never by name, and quote them only with their permission. Results go into [[experiments]] as they are, even if they are bad for us.

## Part 1: the lessons

| # | What the agent learned | Kind of rule | Evidence it was shown | Real in your region? | Your decision | Comment |
|---|---|---|---|---|---|---|
| 1 | Sri Rama Warehousing, Jangaon (site C0012): receives only at night (22:00-6:00) | A site receives only at night | 26 supporting record(s); 0 against. Example: 12 daytime arrivals 2026-08-05 to 2026-10-01 all waited 699-1041 min | | | |
| 2 | Lakshmi Agencies, Jangaon (site C0003): vehicles longer than 22 ft cannot enter | A site's gate or road limits truck length | 3 supporting record(s); 0 against. Example: 3x 32ft returned could_not_enter 2026-08-19, 2026-08-20, 2026-08-21 | | | |
| 3 | Sri Lakshmi Narasimha Traders, Parkal (site C0011): closed on Tue | A shop is closed one day a week | 2 supporting record(s); 0 against. Example: 2026-09-08 Tue V12 32ft returned shop_closed Parkal shops band | | | |
| 4 | Annapurna Mart, Jangaon (site C0030): does not receive after 18:00; plan arrival earlier | A site stops receiving at a fixed hour | 1 supporting record(s); 0 against. Example: 2026-09-05 23:20 arrival waited 520 min note They don't receive after 6 unloading tomorrow | | | |
| 5 | "nalla lorry" means vehicle V11 | Planners use a nickname for a truck, vendor or site | 44 supporting record(s); 0 against. Example: 44 messages with nalla lorry all map to V11 Kakatiya Logistics | | | |
| 6 | "anna vallu" means vendor SVR Transport | Planners use a nickname for a truck, vendor or site | 42 supporting record(s); 0 against. Example: 42 messages with anna vallu map to V13 and V08 | | | |
| 7 | "pedda godown" means Venkata Sri Traders, Warangal (site C0045) | Planners use a nickname for a truck, vendor or site | 15 supporting record(s); 0 against. Example: 15 messages with pedda all map to C0045 Venkata Sri Traders | | | |
| 8 | vehicle V13 safely carries at most 12000 kg (less than its paper payload) | A truck safely carries less than its paper payload | 21 supporting record(s); 0 against. Example: 21 weighbridge offloads, 0 loads >80% without offload | | | |
| 9 | vendor Sri Durga Roadlines often fails to place trucks in the last week of the month; book a backup | A hired-truck vendor often fails at month end | 3 supporting record(s); 0 against. Example: month_end 3 no-shows /9 bookings vs other_days 0/36 | | | |
| 10 | vendor market often fails to place trucks in the last week of the month; book a backup | A hired-truck vendor often fails at month end | 9 supporting record(s); 5 against. Example: month_end 9 no-shows /46 vs other_days 5/65 | | | |
| 11 | Kazipet: bridge (from 2026-08-01 to 2026-09-29) | A road or bridge is closed for a period | 45 supporting record(s); 0 against. Example: 33 Kazipet delays first 2026-08-01 last 2026-09-29 | | | |

_Generated from the EXP-008 lessons (11 items, T01) by `scripts/review_kit.py`. Includes lessons the gate let through with counter-evidence: a good test of the reviewer._

## Part 2: timing "plan tomorrow" (optional, ~30 min)

1. Print the open-orders list for T03's next day (21 orders) with the vehicles free that day (Workbench → "Open orders for tomorrow", company T03; the agent's own `plan_board` view).
2. Ask the dispatcher to plan it the way they do at work, on paper. Time it. Do not help.
3. Show the agent's plan from the saved run (the local app's Logs page, T03 "plan tomorrow" run of Oct 30: 16 drafts covering 18 of 21 orders).
4. Ask, for each draft: would you send it as is · send with a change (which) · not send (why).
5. Record: their minutes, the agent's minutes, drafts accepted as is / with a change / rejected, and anything the agent missed.

## Part 3: three open questions

- Which of these rules would you never let a system enforce on its own? Why?
- What does the agent not know that you would check first every morning?
- Would you use this if it only drafted and you approved every lesson? What would stop you?

## Results (fill in after the session)
| Date | Lessons judged | Kind is real (yes, common / rare / no / not sure) | Decisions (advice / rule / reject / more evidence) | Timing (them / agent) | Drafts (as is / changed / rejected) | Permission to quote |
|---|---|---|---|---|---|---|
| | | | | | | |
