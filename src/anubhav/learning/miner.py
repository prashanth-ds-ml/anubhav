"""The miner: Muse reads a company's evidence digests and proposes candidate lessons as structured JSON.
It proposes; it never decides. Every proposal goes through the deterministic gate (gate.py)."""

import json
import re

KINDS = """Allowed lesson kinds and their params (use ids exactly as they appear in the evidence):
- site_access: {"site_id", "max_length_ft"}  (longest vehicle that can enter this one site)
- receiving_hours: {"site_id", "until_hour"}  (site does not receive after this hour)
- night_only: {"site_id", "from_hour", "to_hour"}  (site receives only at night)
- time_window: {"site_id", "min_length_ft", "from_hour", "to_hour"}  (vehicles of this length or longer can't unload in this window)
- weekly_off: {"site_id" or "town", "weekday"}  (weekday 0=Mon .. 6=Sun; closed that day)
- alias: {"phrase", "target_kind": "site"|"vehicle"|"vendor", "target_id"}  (target_id = site_id, vehicle_id, or vendor name)
- real_capacity: {"vehicle_id", "max_kg"}  (vehicle safely carries less than its paper payload)
- vendor_reliability: {"vendor", "condition": "month_end"}  (vendor often fails to place trucks in that period)
- closure: {"town", "what", "valid_from", "valid_to"}  (temporary road problem; dates YYYY-MM-DD)
- moved_site: {"site_id", "since"}  (site moved; master address is out of date)
- vehicle_requirement: {"town" or "site_id", "vehicle_class"}  (only if trips with other vehicles actually failed)
- other: {"description"}"""

PROMPT = """You are reviewing the operating records of {company}, a transport company (3PL) in Telangana, to find
UNWRITTEN operational knowledge its planners rely on: things true about sites, places, vehicles, vendors and the
words planners use, that are not recorded in the company's systems. Today is {today}.

Be careful:
- A pattern of habit is not a rule. Only propose a constraint if the records show something failing, waiting or
  being refused because of it, not just because it was always done one way.
- One unusual event (bad weather, one wrong note) is not a rule. Notes and staff edits can be wrong or vague.
- Scope every lesson as narrowly as the evidence supports (one site, not a whole town, unless every site there shows it).
- Some problems are temporary: give dates when the evidence starts and stops.
- Give the evidence you relied on and any evidence against it, and possible other explanations.

{kinds}

EVIDENCE (from the company's own records)
== Sites with problems ==
{sites}

== Recurring phrases in planner messages (not in the master data) ==
{phrases}

== Weighbridge offloads by vehicle ==
{vehicles}

== Vendor placements ==
{vendors}

== Recurring delays ==
{delays}

Reply with JSON only:
{{"lessons": [{{"kind": "...", "params": {{...}}, "claim": "one short sentence", "evidence": ["short facts"],
  "counter_evidence": ["short facts"], "alternatives": ["other explanations"], "confidence": "low|medium|high"}}]}}"""


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("lessons", [])
    except json.JSONDecodeError:
        return []


def mine(client, C, digests):
    prompt = PROMPT.format(company=C.company, today=C.today, kinds=KINDS, **digests)
    r = client.chat([{"role": "user", "content": prompt}], None, temperature=0)
    return parse(r.content), {"model": r.model, "cost_usd": r.cost_usd, "tokens_in": r.tokens_in,
                              "tokens_out": r.tokens_out, "latency_s": r.latency_s, "prompt_chars": len(prompt)}
