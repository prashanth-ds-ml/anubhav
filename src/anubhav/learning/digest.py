"""Evidence digests: compact, factual summaries of a company's own records (only what the company can see),
so Muse can read 90 days of operations in one prompt. The digest groups facts; it never decides what they mean.
The gate later re-checks every proposed lesson against the full records, not against the digest."""

import re
from collections import Counter, defaultdict
from datetime import datetime

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Facts:
    """Indexes over CompanyData.t used by both the digest and the gate."""

    def __init__(self, C, until=None):
        """until='YYYY-MM-DD' keeps only records up to that day (to replay what was knowable then)."""
        self.C = C
        self.today = until or C.today
        cut = (until or "9999-12-31") + "T99"
        keep = lambda ts: (ts or "") <= cut
        t = {k: [r for r in v if keep(r.get("ts") or r.get("arrived_at") or r.get("confirmed_at")
                                       or r.get("planned_at") or "")] if isinstance(v, list) else v
             for k, v in C.t.items()} if until else C.t
        self.messages = t.get("planner_messages", [])
        self.ships = {s["shipment_id"]: s for s in t.get("shipments", [])}
        self.stops = defaultdict(dict)
        for x in t.get("shipment_stops", []):
            self.stops[x["shipment_id"]][x["seq"]] = x["site_id"]
        self.events = defaultdict(list)
        for e in t.get("trip_events", []):
            self.events[e["shipment_id"]].append(e)
        self.notes = defaultdict(list)
        for n in t.get("driver_notes", []):
            self.notes[(n["shipment_id"], n.get("stop_seq"))].append(n["text"])
        self.placements = defaultdict(list)
        for p in t.get("vehicle_placements", []):
            self.placements[p["shipment_id"]].append(p)
        self.visits = []          # one row per (shipment, stop): what a planner could see afterwards
        for o in t.get("trip_outcomes", []):
            s = self.ships.get(o["shipment_id"])
            if not s:
                continue
            v = C.vehicles.get(s["vehicle_id"], {})
            evs = [e for e in self.events[o["shipment_id"]] if e.get("stop_seq") == o["stop_seq"]]
            arrived = next((e["ts"] for e in evs if e["kind"] == "arrived"), o["arrived_at"])
            seen = next((e.get("status_seen") for e in evs if e["kind"] == "not_delivered"), None)
            self.visits.append({
                "shipment_id": o["shipment_id"], "stop": o["stop_seq"], "site_id": o["site_id"], "date": arrived[:10],
                "arrived": arrived, "hour": int(arrived[11:13]), "weekday": datetime.fromisoformat(arrived).weekday(),
                "vehicle_id": s["vehicle_id"], "vehicle_class": s["vehicle_class"], "length_ft": v.get("length_ft"),
                "status": o["status"], "wait_min": o.get("wait_min") or 0, "status_seen": seen,
                "notes": self.notes.get((o["shipment_id"], o["stop_seq"]), [])})
        self.by_site = defaultdict(list)
        for x in self.visits:
            self.by_site[x["site_id"]].append(x)

    def ship_vehicles(self, sid):
        """Every vehicle linked to a shipment: the one that ran it and any that were booked but didn't turn up."""
        s = self.ships.get(sid)
        return {p["vehicle_id"] for p in self.placements.get(sid, [])} | ({s["vehicle_id"]} if s else set())


def site_digest(F, max_sites=45, max_rows=14):
    C = F.C
    scored = []
    for sid, vs in F.by_site.items():
        bad = [x for x in vs if x["status"] == "returned" or x["wait_min"] >= 120 or x["notes"]]
        if bad:
            scored.append((len([x for x in vs if x["status"] == "returned"]) * 5 + len(bad), sid))
    lines = []
    for _, sid in sorted(scored, reverse=True)[:max_sites]:
        s, vs = C.sites[sid], sorted(F.by_site[sid], key=lambda x: x["arrived"])
        by_len = Counter((x["length_ft"], "ok" if x["status"] != "returned" else "returned") for x in vs)
        lines.append(f"\nSITE {sid} | {s['name']}, {s['town']} ({s['type']}) | visits {len(vs)} | by truck length: "
                     + ", ".join(f"{ln}ft {st} x{n}" for (ln, st), n in sorted(by_len.items())))
        shown = [x for x in vs if x["status"] == "returned" or x["wait_min"] >= 120 or x["notes"]][:max_rows]
        for x in shown:
            lines.append(f"  {x['arrived']} {WEEKDAYS[x['weekday']]} {x['vehicle_id']} {x['length_ft']}ft -> {x['status']}"
                         f"{' (' + x['status_seen'] + ')' if x['status_seen'] else ''}"
                         f"{', waited ' + str(x['wait_min']) + ' min' if x['wait_min'] else ''}"
                         + (f" | notes: {' / '.join(x['notes'])}" if x["notes"] else ""))
        edits = [e for e in C.t.get("staff_edits", []) if e.get("entity") == "site" and e.get("entity_id") == sid
                 and e.get("field") not in ("phone", "contact_person", "landmark", "remarks")]
        for e in edits[:4]:
            lines.append(f"  staff edit {e['ts'][:10]} {e['user']}: {e['field']} {e['old']!r} -> {e['new']!r} ({e.get('reason_text', '')})")
    return "\n".join(lines)


def phrase_digest(F, min_count=3, max_phrases=25, examples=5, common_df=0.12):
    """Recurring words/phrases in planner messages that aren't in the company's master data, with what each
    message's shipment actually went to. Muse decides what (if anything) a phrase means.

    No hand-written word lists: words in more than `common_df` of all messages count as everyday language, and
    candidates are ranked by how consistently their messages point to one site, vehicle or vendor (a statistic,
    not a decision; the gate still checks every proposed alias against the records)."""
    C = F.C
    vocab = set()
    for s in C.sites.values():
        vocab |= set(re.findall(r"[a-z0-9]+", f"{s['name']} {s['town']} {s.get('street', '')}".lower()))
    for v in C.vehicles.values():
        vocab |= set(re.findall(r"[a-z0-9]+", f"{v['vehicle_id']} {v['reg_no']} {v['vendor']}".lower()))
    msgs = [m for m in C.t.get("planner_messages", []) if m.get("shipment_id") in F.ships]
    toks = [re.findall(r"[a-z]+", m["text"].lower()) for m in msgs]
    df = Counter(w for ts in toks for w in set(ts))
    common = {w for w, n in df.items() if n > common_df * max(1, len(msgs))}

    def targets(m):
        sid = m["shipment_id"]
        vehs = F.ship_vehicles(sid)
        return set(F.stops[sid].values()) | vehs | {C.vehicles[v]["vendor"] for v in vehs if v in C.vehicles}

    grams = defaultdict(list)
    for m, ts in zip(msgs, toks):
        seen = set()
        for n in (1, 2):
            for i in range(len(ts) - n + 1):
                g = ts[i:i + n]
                if all(w not in vocab and w not in common and len(w) > 2 for w in g) and " ".join(g) not in seen:
                    seen.add(" ".join(g))
                    grams[" ".join(g)].append(m)
    scored = []
    for g, ms in grams.items():
        if len(ms) < min_count:
            continue
        tally = Counter(x for m in ms for x in targets(m))
        concentration = tally.most_common(1)[0][1] / len(ms) if tally else 0
        scored.append((concentration * (1 + len(ms)) ** 0.5, g, ms))
    lines = []
    for _, g, ms in sorted(scored, key=lambda x: (-x[0], x[1]))[:max_phrases]:
        lines.append(f'\nPHRASE "{g}" in {len(ms)} messages; examples:')
        for m in ms[:examples]:
            sid = m["shipment_id"]
            sites = [f"{x} {C.sites[x]['name']} ({C.sites[x]['town']})" for x in F.stops[sid].values()]
            vehs = [f"{v} ({C.vehicles[v]['vendor']})" for v in sorted(F.ship_vehicles(sid)) if v in C.vehicles]
            lines.append(f"  \"{m['text']}\" -> sites: {', '.join(sites)}; vehicles: {', '.join(vehs)}")
    return "\n".join(lines)


def vehicle_digest(F):
    lines = []
    off = defaultdict(list)
    for sid, evs in F.events.items():
        for e in evs:
            if e["kind"] == "weighbridge_offload":
                loaded = next((x.get("kg") for x in evs if x["kind"] == "loaded"), None)
                off[F.ships[sid]["vehicle_id"]].append((e["ts"][:10], (loaded or 0) + (e.get("kg") or 0), e.get("kg"),
                                                        F.notes.get((sid, None), [])))
    for vid, rows in sorted(off.items(), key=lambda x: -len(x[1])):
        v = F.C.vehicles.get(vid, {})
        heavy_ok = sum(1 for s in F.ships.values() if s["vehicle_id"] == vid and not any(
            e["kind"] == "weighbridge_offload" for e in F.events[s["shipment_id"]]) and s["weight_kg"] > v.get("payload_kg", 0) * 0.8)
        lines.append(f"\nVEHICLE {vid} ({v.get('class')}, paper payload {v.get('payload_kg')} kg) weighbridge offloads x{len(rows)}; "
                     f"loads >80% of paper payload without offload: {heavy_ok}")
        for d, planned, kg, notes in rows[:8]:
            lines.append(f"  {d}: planned ~{planned:.0f} kg, offloaded {kg} kg" + (f" | notes: {' / '.join(notes)}" if notes else ""))
    return "\n".join(lines)


def vendor_digest(F):
    from datetime import date
    rows = defaultdict(lambda: Counter())
    for sid, ps in F.placements.items():
        for p in ps:
            d = date.fromisoformat(p["confirmed_at"][:10])
            nxt = date.fromordinal(d.toordinal() + 9)
            period = "month_end" if nxt.month != d.month else "other_days"
            rows[p["vendor"]][(period, p["status"])] += 1
    lines = []
    for vendor, c in sorted(rows.items()):
        parts = []
        for period in ("month_end", "other_days"):
            tot = sum(n for (pp, _), n in c.items() if pp == period)
            ns = c[(period, "no_show")]
            parts.append(f"{period}: {ns} no-shows / {tot} bookings")
        lines.append(f"VENDOR {vendor}: " + "; ".join(parts))
    return "\n".join(lines)


def delay_digest(F, max_rows=20):
    by = defaultdict(list)
    for sid, evs in F.events.items():
        for e in evs:
            if e["kind"] == "delay" and e.get("cause_seen") in ("closure", "address"):
                site = F.stops[sid].get(e.get("stop_seq"))
                town = F.C.sites[site]["town"] if site in F.C.sites else "?"
                by[(e["cause_seen"], town if e["cause_seen"] == "closure" else site)].append(
                    (e["ts"][:10], F.notes.get((sid, e.get("stop_seq")), [])))
    lines = []
    for (cause, where), rows in sorted(by.items(), key=lambda x: -len(x[1])):
        rows.sort()
        label = f"site {where} {F.C.sites[where]['name']}" if cause == "address" and where in F.C.sites else f"town {where}"
        lines.append(f"\nDELAY ({cause}) at {label}: {len(rows)} times, first {rows[0][0]}, last {rows[-1][0]}")
        for d, notes in [r for r in rows if r[1]][:max_rows // 4]:
            lines.append(f"  {d}: {' / '.join(notes)}")
    return "\n".join(lines)


def build(C):
    F = Facts(C)
    return F, {"sites": site_digest(F), "phrases": phrase_digest(F), "vehicles": vehicle_digest(F),
               "vendors": vendor_digest(F), "delays": delay_digest(F)}
