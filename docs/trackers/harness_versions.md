---
tags: [tracker, harness]
---
# Harness versions and corrections

The core story of the project: each row is one improvement candidate, from failure to human decision.
**Allowed surfaces:** tool metadata · language aliases/guidance · workflow guidance. Nothing else may be patched.

## Active version
- **Current:** `h-000` (baseline)
- **Model (frozen):** `<muse model id>` · temperature `__`

## Version history
| Version | Date | Parent | Surface | Change summary | Approved by | Status |
|---|---|---|---|---|---|---|
| h-000 | | | | Baseline harness | | active |

## Candidate corrections
| C-ID | From failure (run_id / E-ID) | Root-cause class | Surface | Patch (diff link) | Targeted fixed? | Paraphrase probes pass | Regressions | Held-out Δ | Cost/latency Δ | Decision | → Version |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | ⬜ approve / ⬜ reject | |

**Root-cause classes:** retrieval-miss · wrong-tool · bad-args · multilingual-misread · sequencing · data-issue · policy-attempt

## Promotion checklist (every candidate)
- [ ] Targeted failure fixed
- [ ] Zero critical safety failures
- [ ] No new high-priority regressions
- [ ] No meaningful held-out drop
- [ ] Cost and latency change shown
- [ ] Human approval recorded
- [ ] Rollback tested

---
## Candidate details
