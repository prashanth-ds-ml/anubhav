---
tags: [tracker, learning]
---
# Lessons tracker (Loop B)

What the agent learned about each business, from candidate to retired. The lesson store in `learning.sqlite` is the real record; this page tracks the notable ones for the demo and README. Loop A (tool-use patches) lives in [[harness_versions]].

**States:** OBSERVED → CANDIDATE → NEEDS_EVIDENCE → REVIEWED_APPROVED → ACTIVE_ADVISORY / ACTIVE_POLICY → CHALLENGED → RETIRED · also REJECTED, EXPIRED, SUPERSEDED
**Visibility:** private (default) · domain pack (approved, regional, opt-in)

## Evidence gate rules (code, not the model)
| Kind | Needed to become a candidate | Needed to be enforced |
|---|---|---|
| Alias (name → entity) | ≥ 2 supporting messages, 0 contradictions | Reviewer approval |
| Site/entrance access limit | ≥ 1 failure it explains, 0 comparable successes | Reviewer approval stating *what was verified* |
| Habit ("always uses X") | Never a rule unless a failure or written source supports it | — |
| Anything naming the company's own trucks, vendors or customers | Private only | — |

## Notable lessons
| L-ID | Company | Claim (scoped) | Kind | Evidence | Counter-evidence | State | Visibility | Reviewer / date | Expires |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

## Rejected (keep these: they prove the gate works)
| L-ID | Claim | Why rejected |
|---|---|---|
| | | |

## Domain pack publications
| Pack | From | To | Lessons | Approved by | Leak test | Revoked? |
|---|---|---|---|---|---|---|
| EXP-008 pack | T01 | TNEW | gated regional items | rule-based review (EXP-008) | ✅ 0 leaks | no |
| EXP-011 packs | T01, T02 | TNEW (world 5279) | 5 + 5 | fixed review rule (EXP-011) | ✅ 0 leaks (recipient's own ids excluded, whole-token match) | no |
