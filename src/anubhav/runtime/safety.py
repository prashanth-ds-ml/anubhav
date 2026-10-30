"""The deterministic validator. The model proposes; this code decides whether a draft is allowed.
It checks only what the company's systems know (paper capacity, recorded site limits, approved policies);
learned advisories become warnings, never silent rewrites."""

from dataclasses import dataclass, field

FOOD = {"dense_food", "light_food", "liquid", "chilled"}
EWB_LIMIT = 50000


@dataclass
class Verdict:
    ok: bool
    errors: list = field(default_factory=list)       # [{"code", "message"}] blocking
    warnings: list = field(default_factory=list)     # [{"code", "message"}] shown to the planner
    load: dict = field(default_factory=dict)

    def as_dict(self):
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "load": self.load}


def validate_draft(C, order_ids, vehicle_id, delivery_date, policies=(), advisories=()) -> Verdict:
    """C: CompanyData. policies: approved enforceable site rules [{"site_id", "max_length_ft", "id"}].
    advisories: approved/candidate warnings [{"site_id", "text", "id"}]."""
    err, warn = [], []
    e = lambda code, msg: err.append({"code": code, "message": msg})
    w = lambda code, msg: warn.append({"code": code, "message": msg})
    v = C.vehicles.get(vehicle_id)
    if not v:
        e("NOT_FOUND", f"unknown vehicle {vehicle_id}")
    if not order_ids:
        e("NOT_FOUND", "no orders given")
    kg = m3 = value = 0.0
    classes, sites = set(), []
    in_drafts = C.runtime.orders_in_drafts(delivery_date)
    for oid in order_ids:
        o = C.orders.get(oid)
        if not o:
            e("NOT_FOUND", f"unknown order {oid}")
            continue
        if o["status"] != "open":
            e("ORDER_NOT_OPEN", f"order {oid} is {o['status']}")
        if o["delivery_date"] != delivery_date:
            e("WRONG_DATE", f"order {oid} is due {o['delivery_date']}, not {delivery_date}")
        if oid in in_drafts:
            e("CONFLICT", f"order {oid} is already in another draft")
        ld = C.order_load(oid)
        kg, m3, value = kg + ld["kg"], m3 + ld["m3"], value + ld["value_rs"]
        classes |= set(ld["handling_classes"])
        if o["site_id"] not in sites:
            sites.append(o["site_id"])
    load = {"kg": round(kg, 1), "m3": round(m3, 2), "value_rs": round(value), "stops": len(sites), "sites": sites,
            "handling_classes": sorted(classes)}
    if v:
        if v["status"] != "available":
            e("VEHICLE_UNAVAILABLE", f"{vehicle_id} is {v['status']}")
        if v.get("maintenance_day") and int(v["maintenance_day"]) == int(delivery_date[8:10]):
            e("VEHICLE_UNAVAILABLE", f"{vehicle_id} is in the workshop on {delivery_date} (maintenance day)")
        lapsed = [k for k in ("fitness_until", "permit_until", "insurance_until", "puc_until") if (v.get(k) or "9999") < delivery_date]
        if lapsed:
            e("DOCUMENTS_EXPIRED", f"{vehicle_id}: {', '.join(lapsed)} expired")
        if C.runtime.held(vehicle_id, delivery_date):
            e("CONFLICT", f"{vehicle_id} is already held for {delivery_date}")
        if kg > v["payload_kg"]:
            e("CAPACITY_EXCEEDED", f"{kg:.0f} kg > {vehicle_id} payload {v['payload_kg']:.0f} kg")
        if m3 > v["volume_m3"]:
            e("VOLUME_EXCEEDED", f"{m3:.1f} m3 > {vehicle_id} volume {v['volume_m3']:.0f} m3")
        if "chilled" in classes and v["class"] != "REEFER14":
            e("COLD_CHAIN", "chilled goods need a reefer")
        for sid in sites:
            s = C.sites.get(sid, {})
            if s.get("max_vehicle_length_ft") and v["length_ft"] > s["max_vehicle_length_ft"]:
                e("SITE_ACCESS", f"{s.get('name')}: site master says max {s['max_vehicle_length_ft']} ft, {vehicle_id} is {v['length_ft']} ft")
            for p in policies:
                if p["site_id"] == sid and v["length_ft"] > p["max_length_ft"]:
                    e("SITE_ACCESS", f"{s.get('name')}: approved rule {p['id']} allows max {p['max_length_ft']} ft")
            for a in advisories:
                if a["site_id"] == sid:
                    w("ADVISORY", f"{s.get('name')}: {a['text']} ({a['id']})")
    if "chemical" in classes and classes & FOOD:
        e("SEGREGATION", "food and chemical/home-care products can't share a vehicle")
    if len(sites) > 3:
        w("MANY_STOPS", f"{len(sites)} stops; usual maximum is 3")
    if value > EWB_LIMIT:
        w("EWAY_BILL", f"consignment value Rs {value:,.0f} > Rs 50,000: e-way bill needed")
    return Verdict(ok=not err, errors=err, warnings=warn, load=load)
