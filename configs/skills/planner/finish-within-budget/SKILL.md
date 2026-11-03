---
name: finish-within-budget
description: Keep a request inside its tool, turn and cost limits, and when a limit is reached answer with what was found and what is left.
---
# Finish within the budget

Every request has a limit on turns, tool calls and cost.

1. **Plan the calls first.** Prefer one tool that covers many items (`plan_board`, a learned tool, a teammate's single
   query) over many one-item calls.
2. **Don't repeat a call** with the same arguments, and don't retry a refused tool with the same input: read the error.
3. **"Tool-call limit reached"** means your budget is used up, not that the tool is broken. Stop calling tools.
4. **Answer with what you have:** what you found, what you could not check, and the one next step that would finish it
   (for example "a single query over the records can total this; ask again and I'll hand it to tool_forge").
