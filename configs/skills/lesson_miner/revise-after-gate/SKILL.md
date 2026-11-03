---
name: revise-after-gate
description: When the evidence gate rejects a proposal, revise it once only if the records support a narrower rule; otherwise drop it.
---
# Revise once after the gate

`propose_lesson` returns the gate's verdict and its reason.

1. **Read the reason.** "imprecise" (the limit does not match the evidence), "too few cases", "contradicted", "a habit".
2. **Revise once**, only if the reason points to a narrower rule the records do support: a tighter limit that matches
   the evidence, a narrower place, or a date range. Propose that once.
3. **Never argue with the gate** or re-propose the same rule in other words.
4. **If it is rejected again, drop it** and say so in your reply. Code decides what holds; a person approves what passes.
