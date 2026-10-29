"""Step 10: write the canonical world (with hidden truth) and each company's agent-visible database in its
own physical schema (adapter variants A/B/C). The same mapping, inverted, is what an MCP adapter uses to
read a company's database back into the canonical model."""

import json
import sqlite3
from pathlib import Path

HIDDEN_COLUMNS = {"true_cause", "rule_id", "correct", "real_payload_kg", "site_key", "demand_weight", "credit_hold_days",
                  "true", "known"}
HIDDEN_TABLES = {"replans"}
VARIANTS = {
    "A": {"tables": {"vehicles": "fleet_vehicles", "driver_notes": "trip_notes"}, "columns": {}, "units": {}},
    "B": {"tables": {"vehicles": "truck_master", "shipments": "loads", "shipment_stops": "load_stops",
                     "shipment_items": "load_items", "trip_events": "delivery_events", "trip_outcomes": "delivery_results"},
          "columns": {"shipment_id": "load_id", "vehicle_id": "truck_id", "site_id": "consignee_code"}, "units": {}},
    "C": {"tables": {"sites": "consignees", "shipments": "consignments", "shipment_stops": "consignment_stops",
                     "shipment_items": "consignment_items", "vehicles": "vehicle_register"},
          "columns": {"shipment_id": "consignment_no", "vehicle_id": "vehicle_no", "site_id": "consignee_id"},
          "units": {("shipments", "weight_kg"): ("weight_t", 0.001), ("vehicles", "payload_kg"): ("payload_t", 0.001)}},
}


def visible_tables(W, t):
    """Agent-visible canonical tables for every company (hidden fields still present; dropped on export)."""
    out = {k: v for k, v in t.items() if not k.startswith("_")}
    out["sites"] = [{**{k: v for k, v in s.items() if k not in ("true", "known")}, **s["known"],
                     "entrances": ",".join(s["entrances"])} for s in W.sites]
    out["vehicles"] = [dict(v, status="available") for v in W.vehicles]
    out["drivers"] = list(W.drivers)
    out["products"] = [dict(p, company=c) for c in W.companies for p in W.products
                       if p["brand"] in W.companies[c]["brands"]]
    out["vendors"] = [{"company": c, "vendor": n, "kind": "attached"} for c, cc in W.companies.items() for n in cc["vendors"]]
    out["written_policies"] = [dict(p, company=c) for c in W.companies for p in W.cfg["written_policies"]]
    rules = []
    for c in W.companies:
        for r in W.rules_of("written_rule"):
            if r["company"] == c:
                rules.append({"company": c, "scope": "city", "rule": "Heavy vehicles (>= 22 ft) may not enter city limits "
                              f"{r['from_hour']:02d}:00-{r['to_hour']:02d}:00", "source": "traffic police notification"})
        for s in W.sites:
            if s["company"] == c and s["known"].get("max_vehicle_length_ft"):
                rules.append({"company": c, "scope": s["site_id"], "rule": f"Max vehicle length {s['known']['max_vehicle_length_ft']} ft",
                              "source": "site master"})
    out["site_access_rules"] = rules
    return out


def _cell(v):
    if isinstance(v, (list, dict, set, tuple)):
        return json.dumps(sorted(v) if isinstance(v, set) else v, ensure_ascii=False, default=str)
    return v


def _write(path, tables):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    for name, rows in sorted(tables.items()):
        cols = []
        for r in rows:
            cols += [k for k in r if k not in cols]
        if not cols:
            continue
        con.execute(f'CREATE TABLE "{name}" ({", ".join(chr(34) + c + chr(34) for c in cols)})')
        con.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in cols)})',
                        [[_cell(r.get(c)) for c in cols] for r in rows])
    con.commit()
    con.close()


def to_physical(tables, variant):
    """Canonical (one company, hidden fields dropped) -> that company's physical schema."""
    m = VARIANTS[variant]
    out = {}
    for name, rows in tables.items():
        new_rows = []
        for r in rows:
            nr = {}
            for k, v in r.items():
                if (name, k) in m["units"]:
                    nk, f = m["units"][(name, k)]
                    nr[nk] = None if v is None else round(v * f, 4)
                else:
                    nr[m["columns"].get(k, k)] = v
            new_rows.append(nr)
        out[m["tables"].get(name, name)] = new_rows
    return out


def to_canonical(physical, variant):
    """Inverse of to_physical: what an adapter does when it reads a company's database."""
    m = VARIANTS[variant]
    tinv = {v: k for k, v in m["tables"].items()}
    cinv = {v: k for k, v in m["columns"].items()}
    out = {}
    for pname, rows in physical.items():
        name = tinv.get(pname, pname)
        uinv = {nk: (k, f) for (t, k), (nk, f) in m["units"].items() if t == name}
        new_rows = []
        for r in rows:
            nr = {}
            for k, v in r.items():
                if k in uinv:
                    ck, f = uinv[k]
                    nr[ck] = None if v is None else round(v / f, 4)
                else:
                    nr[cinv.get(k, k)] = v
            new_rows.append(nr)
        out[name] = new_rows
    return out


def company_view(W, t, cid):
    vis = visible_tables(W, t)
    out = {}
    for name, rows in vis.items():
        if name in HIDDEN_TABLES:
            continue
        out[name] = [{k: v for k, v in r.items() if k not in HIDDEN_COLUMNS and k != "company" and not k.startswith("_")}
                     for r in rows if r.get("company") == cid]
    return out


def write_all(W, t, out_dir: Path):
    out_dir = Path(out_dir)
    canon = visible_tables(W, t)
    canon["true_site_profiles"] = [{"company": s["company"], "site_id": s["site_id"], "site_key": s["site_key"], **s["true"]}
                                   for s in W.sites]
    _write(out_dir / "truth" / "canonical.sqlite", canon)
    (out_dir / "truth").mkdir(parents=True, exist_ok=True)
    (out_dir / "truth" / "hidden_rules.json").write_text(json.dumps(W.rules, indent=1, ensure_ascii=False, default=str),
                                                         encoding="utf-8")
    files = {}
    for cid, c in W.companies.items():
        path = out_dir / f"{cid}.sqlite"
        _write(path, to_physical(company_view(W, t, cid), c["variant"]))
        files[cid] = path
    return files
