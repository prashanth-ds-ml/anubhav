---
tags: [project, overview, anubhavam]
date: 2026-10-28
---
# Anubhavam: project overview, walkthrough and hackathon fit

> **One line:** an agent that learns a business's unwritten rules from the business's own records. The reviewer approves the risky lessons, and the next customer of the same type starts already knowing the regional ones.

Diagram: `docs/diagrams/anubhavam_flow.excalidraw` (open at excalidraw.com → Menu → Open)
Experiments: [[experiments]] (files in `archive/prototype_experiments/`) · Costs: [[cost_ledger]] · Rubric: [[rubric_scorecard]] · Submission: [[submission_checklist]]

---

## 1. The problem

**A business's most important operating rules are never written down.** They live in staff heads, so an AI agent connected to the business data still makes costly mistakes.

- **Example:** a dispatch planner near Warangal knows "never send a 32 ft truck to Jangaon, the lane is narrow". No system records this.
- **Real-world evidence** (interview, 2026-10-27, former FMCG logistics manager, anonymised):
  - Ordering and allocation are already digital (app → SAP).
  - The pain is truck and transporter planning: **1–1.5 hours per plan**, and **up to 10 re-plans in festival season**.
  - The constraints are kept in the planner's head. The interviewee said this is "the only place I feel AI is required".
- **Cost of the gap:** returned loads, wasted trips and slow plans. When an experienced planner is absent or leaves, the knowledge leaves too.

**What is *not* the problem:** understanding Telugu, English or Roman Telugu and calling tools correctly. Muse already does this at 88–100% (EXP-005).

---

## 2. The solution

An agent that:
1. Sits on top of each business's own data through **MCP tools**.
2. Takes questions (**Ask**) and instructions (**Do**) in **Telugu, English or Roman Telugu**, by **text or voice**.
3. **Improves by itself** by learning unwritten rules from the business's own records. A human reviews; nobody types rules in by hand.
4. **Shares safe regional knowledge** through a domain pack, so a new customer of the same type is smarter on day 1.

**Who it's for:** three separate businesses near Warangal: an FMCG distributor, a pharma distributor, and a 3PL (transport company). Each has its own data, its own MCP connection and its own private lessons.

---

## 3. Step-by-step walkthrough, with one example

**Setting:** Ramesh is a dispatch planner at a 3PL near Warangal (fictional). The FMCG and pharma distributors work the same way.

### Part 1: Daily work (Ask / Do)

| Step | What happens | Example |
|---|---|---|
| 1. Speak / type | Muse Voice Transcribe turns speech into text. Typing works too. | *"Repu Jangaon ki 8 ton load undi, edi lorry pettali?"* (8-ton load to Jangaon tomorrow, which lorry?) |
| 2. Pick tools | Tool search gives the agent only the MCP tools it needs. | `list_shipments`, `list_vehicles`, `get_area_rules` |
| 3. Read data | The agent calls the tools on the business data. | Shipment 8,000 kg to the Jangaon distributor. Free trucks: V10 (32 ft), V05 (9 MT), V09 (9 MT). Jangaon has **no restriction** in the data. |
| 4. Propose plan | Day 1, wrong: the data looks fine. | Picks **V10, the 32 ft truck**. *EXP-005: Muse did exactly this in 4/4 runs.* |
| 5. Safety check | Code checks capacity, double-booking and written area rules. | All pass. The check can't catch a rule nobody wrote down. |
| 6. Answer | Reply in the user's language. | *"V10 (32 adugula lorry) Jangaon ki pettanu."* |
| 7. Outcome recorded | The result and the driver's note are saved. | *"Jangaon godown lane lo 32 adugula lorry tiragaledu, load venakki vachindi."* The load is re-sent on two 9 MT trucks, and that is recorded too. |

### Part 2: Learning by itself

| Step | What happens | Example |
|---|---|---|
| 8. Records pile up | Trips, staff corrections and outcomes collect over weeks. | EXP-006 used 123 trips, including the Jangaon failure and the split re-send. |
| 9. Muse proposes lessons | **Muse Spark** reads the history and suggests lessons. | "Jangaon: no 32 ft" · "Pedda godown" = Warangal distributor · "nalla lorry" = V08 · "Anna vallu" = SVR Transport · "Chowrasta load" = Hanamkonda distributor · **trap:** "Khammam always 36 ft" (a habit, not a rule) |
| 10. Evidence check (code, not AI) | **Name aliases:** ≥2 supporting messages and 0 contradictions. **Truck limits:** 0 successful deliveries that break the rule, plus ≥1 failure the rule explains. | Jangaon **passes** (one failure explained, no 32 ft truck ever delivered there). Khammam **fails** (nothing ever failed with a smaller truck, so it's a habit). *EXP-006: 5/5 real lessons found, 0 false, the Khammam trap never got through.* |
| 11. Review and visibility | Risky lessons (truck limits) need reviewer approval. Low-risk aliases can go through automatically. A **code rule** sets visibility: lessons that name the company's own trucks or vendors stay **private**; lessons about regional places go into the **domain pack**. | "nalla lorry = V08" is private. Jangaon, Pedda godown and Chowrasta go into the domain pack. *EXP-006: Muse labelled visibility wrongly 3 times; the code rule was right every time.* |
| 12. Store | Saved with evidence, date, approver and expiry. | Evidence: trip T033. |
| 13. Used next time | The lesson is added to the agent's context and enforced by the safety check. | Picks 9 MT trucks or splits the load. *EXP-006: unwritten-rule tasks 0% → 100%, unsafe Jangaon trips 6 → 0.* |
| 14. Weekly report | The owner gets "What I learned this week", with one-tap approve or undo. | *"I learned 5 things… Jangaon: no 32 ft (proof: trip T033)."* |
| 15. Freshness | A successful delivery that contradicts a lesson flags it. Lessons with no recent confirmation expire. Any lesson can be undone. | Two months later the road is widened and a 32 ft truck delivers, so the lesson is flagged and retired. |
| 16. Training data | Approved, correct plans are exported as fine-tuning data. | Each record: question, tools used, correct plan. Covers the "validated experience data" part of the problem statement. |

### Part 3: A new customer benefits

| Step | What happens | Example |
|---|---|---|
| 17. New customer joins | It connects only the tools it needs and gets the **domain pack**, not other customers' private lessons. | Ramappa Carriers (fictional 3PL) gets Jangaon, Pedda godown and Chowrasta, but **not** "nalla lorry = V08". |
| 18. Smarter on day 1 | Regional knowledge works immediately. Its own private names are learned later from its own records. | *"Pedda godown ki load pampu"* → correct distributor on day 1. It learns "pacha lorry" later. *EXP-006: 0% → 100%, 0 leaks.* |

---

## 4. Experiments and findings

All experiments were pre-registered: tasks, data and code were frozen and hashed before any model call, and every call is logged in [[cost_ledger]]. **All data is synthetic.**

| Exp | Question | Result | Takeaway |
|---|---|---|---|
| EXP-001 | Can Muse run a code-mixed order desk with tools? | 88% | Language and tool calls work. |
| EXP-002 | Does it scale to 40 tools with tool search? | 86%, ~2× cost | Works, but tool search was not selective. |
| EXP-003 | Does the Lab optimiser beat a simple heuristic? | Muse optimal 15/15, but the heuristic also matched | Dropped Lab; no pivot. |
| EXP-004 | Spark Open vs Spark? | About equal | Spark Open is good enough for the agent. |
| EXP-005 | Dispatch planning: where does Muse fail? | Control 88–100% · strategy traps 100% · **unwritten knowledge 0–12%** | The only real gap is unwritten knowledge. |
| EXP-006 | Can it learn that knowledge from history and share it? | Mining 5/5 true, 0 false · same company **0% → 100%** · new company with pack **0% → 100%** · unsafe Jangaon 6 → 0 · **0 leaks** | Self-improvement and transfer both shown. |

**EXP-006 notes:**
- Two double-booking slips appeared, only in the runs that had lessons. They were within tolerance; the fix is the pre-assign safety check.
- Muse's visibility labels were wrong 3 times, so visibility stays a code rule.

**Total spend so far:** ~$24 (Meta ~$15.3, Baseten ~$9.4).

### Insights
1. **Language and tools are solved.** Don't pitch the project on them.
2. **Unwritten knowledge is the gap,** and it can be learned from records the business already has.
3. **Use AI to propose and code to decide.** Muse finds patterns well but mislabels visibility, and the evidence rules catch habits.
4. **Sharing works safely** when private versus regional is decided by rules, not by the model.

### Limits
- The data is synthetic. Results must be rerun on realistic, larger data.
- The test sets are small (13–16 tasks, 2 repeats).
- Only one domain (3PL dispatch) has been tested end to end so far.
- The interview is a single source. Quotes need the interviewee's permission.

---

## 5. How it fits the hackathon rules

| Rule | How we meet it |
|---|---|
| Theme: **Push the Frontier** | A measured new capability: Muse alone scores 0% on unwritten rules, and 100% with our loop. |
| Track: **Indie Developer** | Solo. |
| Clear use of **Meta models** | Muse is used at every step: agent, miner, voice input, tool search. |
| Built during the hackathon | All code and data from Oct 27 onward, with daily commits. |
| Not an anti-project | Not basic RAG, not a simple chatbot, no medical advice. It takes real actions on data. |
| Rights and originality | All companies, people and data are fictional. The interview is anonymised and quoted only with permission. |

### Submission requirements
- [ ] Public GitHub repo: `prashanth-ds-ml/anubhav`
- [ ] **3-minute demo video**, showing only features built during the hackathon
- [ ] Submitted on Cerebral Valley by **Nov 4, 9 PM ET (Nov 5, 7:30 AM IST)**
- [ ] README: problem, Meta models used, architecture diagram, setup, results, limits
- [ ] No keys or secrets in the git history
- [ ] No Claude co-author trailer

---

## 6. Scoring

**Stage 1 (pass/fail):** fits the theme and clearly uses Meta models. We expect to pass.

**Stage 2 (100 points):**

| Criterion | Weight | Judges ask | Our answer |
|---|---|---|---|
| **Impact** | 30 | Real problem? Who benefits? | Planning takes 1–1.5 h with up to 10 re-plans, and the knowledge sits in people's heads (interview). Small distributors and transporters benefit in their own language. A new customer gets value on day 1. |
| **Meta AI tooling** | 25 | Beyond basic use? Surprising? | **Spark** mines lessons from messy code-mixed records · **Spark Open** is the agent (open weights) · **Voice Transcribe** handles Telugu voice · **tool search** picks MCP tools. |
| **Technical depth** | 20 | Sound and well thought out? | Code-based evidence check, reviewer approval, private vs domain-pack visibility with 0 leaks, expiry and undo, pre-assign safety check, frozen pre-registered tests, logged costs. |
| **Demo** | 25 | Works? Impressive? | Before/after story: the 32 ft truck fails at Jangaon → the agent learns from records → gets it right → a new company gets it right on day 1. |

### Bonus prizes
| Prize | Fit | Note |
|---|---|---|
| Best Agentic Use-Case ($5K) | **Strong** | The core of the build |
| Best Open Weights ($10K) | **Good** | The agent runs on Spark Open; we export fine-tuning data |
| Most Viral ($20K) | Possible | Short Telugu demo clip on X |
| Community Vote ($10K) | Possible | Telugu community push |
| Best Creative Build ($5K) | No | Needs Muse Image/Wonder |

### Current self-score and gaps
**About 6/10 today, about 8.5/10 if the demo works smoothly.**

| Gap | Criterion | Fix |
|---|---|---|
| Nothing runnable yet | Demo (25) | Build the app early; record early |
| Synthetic, small data | Impact (30), Technical (20) | Realistic datasets for 3 parties plus a second customer; rerun the tests |
| No industry-size figures | Impact (30) | Add 1–2 cited facts |

---

## 7. Build plan (Oct 28 → Nov 4)

| Day | Work |
|---|---|
| Oct 28–29 | Realistic data for 3 parties (FMCG distributor, pharma distributor, 3PL) plus a second customer of the same type. Months of history in which the rules exist only as patterns. |
| Oct 29–30 | MCP server with domain tools, tool search (each business connects only what it needs), pre-assign safety check. |
| Oct 30–31 | Learning loop as a module: mine → check → approve → use → expire/undo. Lesson store with private and domain-pack levels. |
| Nov 1 | App screens: chat (text and voice), review queue, weekly report, before/after scores. |
| Nov 2 | Final frozen evaluation runs on realistic data. Fine-tuning data export. |
| Nov 3 | 3-minute demo video, README, architecture diagram. |
| Nov 4 | Buffer, then submit before 9 PM ET. |

### Out of scope
- New domains (retail, inventory and so on)
- A generic RAG chatbot
- Running fine-tuning (we export the data only)
- UI beyond what the demo needs
