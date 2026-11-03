---
name: hand-to-tool-forge
description: When no tool answers a records question in a few calls, delegate it to tool_forge with a brief it can turn into one general query.
---
# Hand a question to Tool Forge

1. **When:** `find_capability` says `tool_missing`, or the answer would take more than a few tool calls (a total over
   many sites, days or trips).
2. **Brief it for one general query:** the measure (count, sum of kg, km), the grouping (by day, site, town, vehicle),
   the filter values (towns, sites, statuses) and the absolute date range. Ask for the SQL back with the answer.
3. **Say which inputs vary** ("for any town and any date range"), so the query can become a reusable tool later.
4. **Check the reply** has numbers, dates and the SQL; if not, ask once for what is missing.
