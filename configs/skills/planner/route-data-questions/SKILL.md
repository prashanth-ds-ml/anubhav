---
name: route-data-questions
description: For counts, totals, trends or comparisons over the records, find the right tool or teammate instead of calling a per-item tool many times.
---
# Route a data question

Use this for questions like "how many …", "how much in total …", "which weekday …", "compare …" over days, sites or towns.

1. **Do not loop a per-item tool.** A tool that answers for one site or one order, called once per item, runs out of
   your tool budget on any week-sized question. One query over the records answers it in one step.
2. **Ask `find_capability`** with the need in plain words.
   - A tool that plainly answers it (including a learned tool): use it.
   - Existing tools that together might answer it: `delegate` to **analyst**.
   - Nothing fits (`tool_missing`), or it needs a total over many rows: `delegate` to **tool_forge**.
3. **Write a complete brief.** What to find, for which dates (absolute dates, not "this week"), which sites or towns,
   what to include (for distances: depot to site and back), and what to return (the numbers, the date range, how it was
   counted).
4. **Report the answer** with its numbers, dates and method, and say plainly what was estimated (for example road
   distances are estimates from the depot).
