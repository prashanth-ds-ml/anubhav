---
name: repair-a-tool
description: When a reusable query fails its code checks or breaks later, revise it to answer the same question for any value of the same inputs.
---
# Repair a tool

You get the tool's query template (inputs are `:name` placeholders), its inputs, and why the code checks failed.

1. **Keep the question and the inputs.** Same `:name` placeholders, same meaning. A repair that answers a different
   question is not a repair.
2. **Fix what the checks said:**
   - "does not give the original answers": the template changed the query's meaning; compare it with what the question
     asked and restore the filter or grouping.
   - "fails on held-out values": a value-specific piece is left in (a fixed spelling, a hard-coded id); make the
     comparison general (for text, compare in one case on both sides).
   - "keeps a fixed date or month": turn it into an input.
   - "takes a list of ids": filter by the attribute that the ids share instead.
   - "finds nothing for most held-out values": the query is too narrow; widen the filter to what the question means.
3. **Return only the revised SELECT.** Code re-runs every check (including the original answers) and a person decides.
   You get at most 2 tries.
