---
name: answer-with-tools
description: Answer a records question with the existing and learned tools, stating the dates, the counts and how they were combined.
---
# Answer with the tools you have

1. **Find the tool.** `find_capability` with the need. A learned tool (made from queries the team reused and approved
   by a person) is often the one-step answer: use it first when it fits.
2. **Fix the period first.** Turn "this week", "last month" into absolute dates from today's date before calling.
3. **Call as few tools as possible.** If the answer would need the same one-item tool for every site or day, hand it
   to tool_forge instead (skill: hand-to-tool-forge).
4. **Combine carefully.** Say how you added or compared the numbers. Keep units (kg, tonnes, km) and convert once.
5. **Return** the numbers, the date range, the tools used, and anything that was estimated or missing.

You never write SQL and never create or cancel drafts; those are other agents' work.
