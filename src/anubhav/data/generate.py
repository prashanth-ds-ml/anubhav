"""Generate a world: build -> simulate -> people -> text -> validate -> export (spec §9).

  uv run python -m anubhav.data.generate --pilot            # T01, Sep 8-14 (spec §11)
  uv run python -m anubhav.data.generate --full             # 90 days, all companies
Writes data/worlds/<run_id>/ and refuses to write anything if a critical check fails."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from . import config, people, simulate, store, text, validate, world


def generate(cfg, companies, start, end):
    W = world.build(cfg, companies)
    t = simulate.Sim(W, start, end).run()
    people.run(W, t, start, end)
    text.run(W, t)
    return W, t


def snapshot_hash(W, t, cid):
    view = store.company_view(W, t, cid)
    return hashlib.sha256(json.dumps(view, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def check(W, t, companies, start, end):
    problems = validate.integrity(W, t) + validate.leaks(W, t)
    ev = validate.evidence(W, t, companies, start, end)
    problems += validate.evidence_problems(ev, W)
    return problems, ev


def summary(W, t, ev, st, start, end):
    lines = [f"# World summary ({start} → {end})", ""]
    for cid in W.companies:
        o = [x for x in t["orders"] if x["company"] == cid]
        if not o:
            lines.append(f"## {cid}: no history (cold-start company)\n")
            continue
        days = len({x["delivery_date"] for x in o})
        sh = [x for x in t["shipments"] if x["company"] == cid]
        out = Counter(x["status"] for x in t["trip_outcomes"] if x["company"] == cid)
        causes = Counter(x["true_cause"] for x in t["trip_outcomes"] if x["company"] == cid and x["true_cause"])
        rp = Counter(x["date"] for x in t["replans"] if x["company"] == cid)
        charges = Counter()
        for c in t["trip_charges"]:
            if c["company"] == cid:
                charges[c["kind"]] += c["amount_rs"]
        lines += [f"## {cid} {W.companies[cid]['name']} (schema {W.companies[cid]['variant']})",
                  f"- Orders: {len(o)} over {days} days ({len(o) / max(1, days):.1f}/day) · statuses {dict(Counter(x['status'] for x in o))}",
                  f"- Shipments: {len(sh)} · stops {sum(1 for x in t['shipment_stops'] if x['company'] == cid)} · "
                  f"classes {dict(Counter(x['vehicle_class'] for x in sh))}",
                  f"- Stop outcomes: {dict(out)}",
                  f"- Causes (hidden): {dict(causes)}",
                  f"- Re-plans per day: max {max(rp.values(), default=0)}, mean {sum(rp.values()) / max(1, days):.1f} · reasons "
                  f"{dict(Counter(x['reason'] for x in t['replans'] if x['company'] == cid))}",
                  f"- Charges: {dict(charges)}",
                  f"- Staff edits: {sum(1 for x in t['staff_edits'] if x['company'] == cid)} · feedback "
                  f"{sum(1 for x in t['feedback'] if x['company'] == cid)} · planner messages "
                  f"{sum(1 for x in t['planner_messages'] if x['company'] == cid)} · driver notes "
                  f"{sum(1 for x in t['driver_notes'] if x['company'] == cid)}", ""]
    lines += ["## Text", f"- Language mix: {st['languages']} · voice {st['voice_share']} · wrong/vague {st['vague_share']}", "",
              "## Evidence per hidden rule", "| Rule | Kind | Strength | Planned exposures | Evidence |", "|---|---|---|---|---|"]
    for rid, e in ev.items():
        shown = {k: v for k, v in e.items() if v and k not in ("strength", "planned_exposures_in_window", "total")}
        lines.append(f"| {rid} | {W.rule(rid)['kind']} | {e['strength']} | {e['planned_exposures_in_window']} | {shown or '—'} |")
    return "\n".join(lines) + "\n"


def review_packet(W, t, cid, n_orders=30, n_trips=20, n_notes=40):
    """A readable sample for the human realism review (spec §11 checklist)."""
    import random
    r = random.Random(0)
    L = [f"# Review packet: {cid} {W.companies[cid]['name']}", "",
         "Read each part and note anything that feels unreal in docs/trackers/data_and_benchmark.md §4.", ""]
    orders = [o for o in t["orders"] if o["company"] == cid and not o.get("_resend")]
    L += ["## 1. Orders (30)", "| Order | Site | Town | Delivery | Window | Items (cases) | kg | Status |", "|---|---|---|---|---|---|---|---|"]
    prod = {p["sku"]: p for p in W.products}
    for o in r.sample(orders, min(n_orders, len(orders))):
        s = W.site(cid, o["site_id"])
        its = [i for i in t["order_items"] if i["order_id"] == o["order_id"] and i["company"] == cid]
        kg = sum(prod[i["sku"]]["case_kg"] * i["ordered_cases"] for i in its)
        L.append(f"| {o['order_id']} | {s['name']} | {s['town']} | {o['delivery_date']} | {o['window_start']}-{o['window_end']} | "
                 f"{', '.join(prod[i['sku']]['name'] + ' x' + str(i['ordered_cases']) for i in its)} | {kg:,.0f} | {o['status']} |")
    ships = [x for x in t["shipments"] if x["company"] == cid]
    L += ["", "## 2. Trips (20)", "| Shipment | Planner | Truck | kg | Stops | Outcome per stop |", "|---|---|---|---|---|---|"]
    for sh in r.sample(ships, min(n_trips, len(ships))):
        stops = [x for x in t["shipment_stops"] if x["shipment_id"] == sh["shipment_id"] and x["company"] == cid]
        outs = {o["stop_seq"]: o for o in t["trip_outcomes"] if o["shipment_id"] == sh["shipment_id"] and o["company"] == cid}
        desc = "; ".join(f"{W.site(cid, x['site_id'])['town']}: {outs.get(x['seq'], {}).get('status', '?')}"
                         f"{' (wait ' + str(outs[x['seq']]['wait_min']) + ' min)' if outs.get(x['seq'], {}).get('wait_min') else ''}"
                         for x in stops)
        L.append(f"| {sh['shipment_id']} | {sh['planned_by']} | {sh['vehicle_id']} {sh['vehicle_class']} | {sh['weight_kg']:,.0f} | {len(stops)} | {desc} |")
    L += ["", "## 3. Planner messages and driver notes (40)", "| Time | Who | Lang | Source | Text |", "|---|---|---|---|---|"]
    texts = [("planner " + m["from"], m["lang"], "text", m["ts"], m["text"]) for m in t["planner_messages"] if m["company"] == cid]
    texts += [("driver", n["lang"], n["source"], n["ts"], n["text"]) for n in t["driver_notes"] if n["company"] == cid]
    for who, lang, src, ts, txt in sorted(r.sample(texts, min(n_notes, len(texts))), key=lambda x: x[3]):
        L.append(f"| {ts} | {who} | {lang} | {src} | {txt} |")
    L += ["", "## 4. Staff edits and feedback", "| Time | Who | Change | Reason |", "|---|---|---|---|"]
    for e in [e for e in t["staff_edits"] if e["company"] == cid][:15]:
        L.append(f"| {e['ts']} | {e['user']} | {e['entity']} {e['entity_id']} {e['field']}: {e['old']!r} → {e['new']!r} | {e.get('reason_text', '')} |")
    for f in [f for f in t["feedback"] if f["company"] == cid][:10]:
        L.append(f"| {f['ts']} | {f['source']} | feedback: {f['kind']} | {f['text']} |")
    L += ["", "## 5. Site master (what the company knows)", "| Site | Town | Type | Known profile |", "|---|---|---|---|"]
    for s in [s for s in W.sites if s["company"] == cid][:15]:
        known = {k: v for k, v in s["known"].items() if v is not None}
        L.append(f"| {s['name']} | {s['town']} | {s['type']} | {known or 'blank'} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true")
    g.add_argument("--full", action="store_true")
    ap.add_argument("--config", default=str(config.DEFAULT_CONFIG))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", default=str(config.ROOT / "data" / "worlds"))
    a = ap.parse_args(argv)
    cfg = config.load(a.config, **({"master_seed": a.seed} if a.seed else {}))
    if a.pilot:
        companies, start, end, label = cfg["pilot"]["companies"], str(cfg["pilot"]["start"]), str(cfg["pilot"]["end"]), "pilot"
    else:
        companies, start, end, label = list(cfg["companies"]), str(cfg["period"]["start"]), str(cfg["period"]["end"]), "full"
    W, t = generate(cfg, companies, start, end)
    problems, ev = check(W, t, companies, start, end)
    st = validate.stats(t)
    run_id = f"{label}_seed{cfg['master_seed']}"
    out = Path(a.out) / run_id
    if problems:
        print(f"✗ {len(problems)} critical problem(s); nothing written:")
        for p in problems[:40]:
            print("  -", p)
        return 1
    files = store.write_all(W, t, out)
    manifest = {"run_id": run_id, "generator_version": cfg["generator_version"], "master_seed": cfg["master_seed"],
                "config_hash": config.config_hash(cfg), "window": [start, end], "companies": companies,
                "variants": {c: W.companies[c]["variant"] for c in companies},
                "snapshot_hashes": {c: snapshot_hash(W, t, c) for c in companies},
                "files": {c: str(p.relative_to(out)) for c, p in files.items()}, "stats": st}
    (out / "reports").mkdir(exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out / "reports" / "evidence.json").write_text(json.dumps(ev, indent=1), encoding="utf-8")
    (out / "reports" / "summary.md").write_text(summary(W, t, ev, st, start, end), encoding="utf-8")
    for cid in companies:
        if any(o["company"] == cid for o in t["orders"]):
            (out / "reports" / f"review_{cid}.md").write_text(review_packet(W, t, cid), encoding="utf-8")
    print(f"✓ {run_id}: 0 critical problems · written to {out}")
    print((out / "reports" / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
