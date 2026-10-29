"""Step 9: messy text. Planner messages, driver notes (some as voice-note transcripts), feedback text and
edit reasons, in Roman Telugu, Telugu script and English. Facts come from the simulated events; text only
describes what someone on the ground could see. A note never names a hidden rule or a test answer."""

import re
from datetime import datetime, timedelta

from .config import rng
from .simulate import iso

T = {  # (kind, lang) -> templates
    ("assign", "rt"): ["{site} load ki {veh} pettu", "{site} ki repu {veh} pampu", "{veh} ni {site} ki assign cheyyi",
                       "{town} load {veh} lo vellali", "repu {site} ki {veh}, morning ke reach avvali"],
    ("assign", "te"): ["{site} లోడ్ కి {veh} పెట్టు", "రేపు {site} కి {veh} పంపు", "{veh} ని {site} కి assign చెయ్యి"],
    ("assign", "en"): ["Assign {veh} for {site}", "{veh} to {site} tomorrow morning", "Load for {site} on {veh}",
                       "{site} - send {veh}"],
    ("no_show", "rt"): ["{vendor} bandi raledu, {veh} pettu", "{vendor} vallu malli bandi pettaledu, {veh} ki marchu"],
    ("no_show", "te"): ["{vendor} బండి రాలేదు, {veh} పెట్టు"],
    ("no_show", "en"): ["{vendor} truck didn't turn up, switch to {veh}", "No-show from {vendor}. Using {veh}"],
    ("ice_box", "rt"): ["reefer free ledu, ice boxes saripotayi, {veh} lo pampu"],
    ("ice_box", "te"): ["రీఫర్ లేదు, ఐస్ బాక్స్ లు సరిపోతాయి, {veh} లో పంపు"],
    ("ice_box", "en"): ["No reefer free, ice boxes will do, send on {veh}"],
    ("could_not_enter", "rt"): ["{site} gate lo {len} adugula lorry tiragaledu, load venakki vachindi",
                                "{site} daggara lane chinnadi sir, {len} feet bandi lopaliki ponivvaledu, return vastunnam"],
    ("could_not_enter", "te"): ["{site} గేట్ దగ్గర {len} అడుగుల లారీ లోపలికి వెళ్ళలేదు, లోడ్ వెనక్కి తెస్తున్నాం"],
    ("could_not_enter", "en"): ["{len} ft truck could not enter {site}, load coming back"],
    ("shop_closed", "rt"): ["{town} lo ivvala shops band sir, load return", "{site} band undi, evaru levu"],
    ("shop_closed", "te"): ["{town} లో ఈరోజు షాపులు బంద్ సార్, లోడ్ వెనక్కి"],
    ("shop_closed", "en"): ["{site} closed today, nobody to receive"],
    ("road_blocked", "rt"): ["bhaari varsham sir, road meeda neellu, {town} ki vellalekapotunnam"],
    ("road_blocked", "te"): ["భారీ వర్షం, రోడ్డు మీద నీళ్ళు, {town} కి వెళ్ళలేం"],
    ("road_blocked", "en"): ["Heavy rain, road to {town} flooded, can't go"],
    ("wait_time_window", "rt"): ["Chowrasta lo pagalu pedda lorry ki entry ledu anta, 8 varaku wait", "{site} daggara police aaparu, raatri ke entry"],
    ("wait_time_window", "te"): ["చౌరస్తా లో పగలు పెద్ద లారీకి ఎంట్రీ లేదు అంట, రాత్రి 8 వరకు ఆగాలి"],
    ("wait_time_window", "en"): ["No entry for big trucks near {site} in the day, waiting till 8 pm"],
    ("wait_receiving", "rt"): ["6 tarvata sarukulu teesukoru anta, repu morning unload", "{site} vallu late ga vaste teesukoru, repu podduna"],
    ("wait_receiving", "te"): ["6 తర్వాత సరుకు తీసుకోరు అంట, రేపు పొద్దున అన్‌లోడ్"],
    ("wait_receiving", "en"): ["They don't receive after 6, unloading tomorrow morning"],
    ("wait_night", "rt"): ["raatri 10 tarvate teesukuntaru anta, wait chestunnam", "{site} lo pagalu unload cheyyaru"],
    ("wait_night", "te"): ["రాత్రి 10 తర్వాతే తీసుకుంటారు అంట, ఆగుతున్నాం"],
    ("wait_night", "en"): ["{site} only receives after 10 pm, waiting"],
    ("wait_godown_full", "rt"): ["godown full ani cheppinaru, repu dinchutham", "{site} lo jaaga ledu, wait"],
    ("wait_godown_full", "te"): ["గోడౌన్ ఫుల్ అన్నారు, రేపు దించుతాం"],
    ("wait_godown_full", "en"): ["Godown full at {site}, unloading later"],
    ("wait_generic", "rt"): ["{hrs} gantala nunchi wait chestunnam, inka unload kaledu", "line undi sir, {hrs} hrs ayyindi"],
    ("wait_generic", "te"): ["{hrs} గంటల నుండి వెయిట్ చేస్తున్నాం, ఇంకా అన్‌లోడ్ కాలేదు"],
    ("wait_generic", "en"): ["Waiting {hrs} hrs at {site}, not unloaded yet"],
    ("delay_closure", "rt"): ["Kazipet bridge band, chuttu tirigi veltunnam, {min} min late", "bridge pani jarugutundi, detour"],
    ("delay_closure", "te"): ["కాజీపేట బ్రిడ్జి బంద్, చుట్టూ తిరిగి వెళ్తున్నాం, {min} నిమిషాలు లేట్"],
    ("delay_closure", "en"): ["Kazipet bridge closed, detour, {min} min late"],
    ("delay_address", "rt"): ["paata address ki vellam, kotha godown ki vellali anta, gantha late", "{site} vallu kotha godown ki marcharu anta"],
    ("delay_address", "te"): ["పాత అడ్రస్ కి వెళ్ళాం, కొత్త గోడౌన్ కి రమ్మన్నారు, గంట లేట్"],
    ("delay_address", "en"): ["Went to the old address, they've moved to a new godown, 1 hr late"],
    ("delay_breakdown", "rt"): ["bandi breakdown ayyindi, mechanic kosam wait", "tyre puncture sir, {min} min"],
    ("delay_breakdown", "te"): ["బండి బ్రేక్ డౌన్ అయ్యింది, మెకానిక్ కోసం వెయిట్"],
    ("delay_breakdown", "en"): ["Truck broke down, waiting for mechanic"],
    ("delay_rain", "rt"): ["varsham valla road bagaledu, late avthadi"],
    ("delay_rain", "te"): ["వర్షం వల్ల రోడ్డు బాగాలేదు, లేట్ అవుతుంది"],
    ("delay_rain", "en"): ["Rain, bad road, running late"],
    ("delay_bandh", "rt"): ["ivvala bandh sir, roads band"], ("delay_bandh", "te"): ["ఈరోజు బంద్, రోడ్లు మూసేశారు"],
    ("delay_bandh", "en"): ["Bandh today, roads blocked"],
    ("delay_missing_eway_bill", "rt"): ["checkpost lo EWB adigaru, {hrs} gantalu aapesaru"],
    ("delay_missing_eway_bill", "te"): ["చెక్ పోస్ట్ లో ఈ-వే బిల్ అడిగారు, {hrs} గంటలు ఆపేశారు"],
    ("delay_missing_eway_bill", "en"): ["Stopped at checkpost for e-way bill, {hrs} hrs"],
    ("offload", "rt"): ["{veh} lo {tons} ton ekkadu, {off} kg dinchesam", "weighbridge lo overload annaru, {off} kg digipoyindi"],
    ("offload", "te"): ["వే బ్రిడ్జి లో ఓవర్ లోడ్ అన్నారు, {off} కిలోలు దించేశాం"],
    ("offload", "en"): ["Weighbridge flagged overload, offloaded {off} kg"],
    ("rejected", "rt"): ["fitness ayipoyindi ani loading aapesaru"], ("rejected", "te"): ["డాక్యుమెంట్స్ ఎక్స్‌పైర్ అయ్యాయి అని లోడింగ్ ఆపేశారు"],
    ("rejected", "en"): ["Loading stopped, vehicle papers expired"],
    ("delivered", "rt"): ["delivered sir, POD teesukunna", "unload ayyindi", "ok vachindi"],
    ("delivered", "te"): ["డెలివరీ అయ్యింది సార్", "దించేశాం సార్"], ("delivered", "en"): ["Delivered, POD collected", "Unloaded ok"],
    ("partial", "rt"): ["{cases} cases teesukoledu, return", "konni cases venakki"],
    ("partial", "te"): ["{cases} కేసులు తీసుకోలేదు, వెనక్కి తెస్తున్నా"], ("partial", "en"): ["{cases} cases refused, bringing back"],
    ("vague", "rt"): ["problem undi sir, call chesta", "konchem late avthadi", "akkada issue undi"],
    ("vague", "te"): ["కొంచెం ప్రాబ్లం ఉంది సార్"], ("vague", "en"): ["some issue at site, will call"],
    ("wrong_gate", "rt"): ["gate chinnadi sir, lopaliki ponivvatledu"], ("wrong_gate", "te"): ["గేట్ చిన్నది సార్"],
    ("wrong_gate", "en"): ["Gate is too narrow here"],
}
FEEDBACK = {
    ("long_wait", "rt"): "{site} lo {hrs} gantalu wait chepincharu", ("long_wait", "te"): "{site} లో {hrs} గంటలు వెయిట్ చేయించారు",
    ("long_wait", "en"): "Made to wait {hrs} hrs at {site}",
    ("damage", "rt"): "{cases} cases damage ga vachayi", ("damage", "te"): "{cases} కేసులు డ్యామేజ్ గా వచ్చాయి",
    ("damage", "en"): "{cases} cases arrived damaged",
    ("not_received", "rt"): "maaku sarukulu raledu, enduku?", ("not_received", "te"): "మాకు సరుకు రాలేదు, ఎందుకు?",
    ("not_received", "en"): "We did not receive the goods",
    ("late", "rt"): "sarukulu {hrs} gantalu late ga vachayi", ("late", "te"): "సరుకు {hrs} గంటలు లేట్ గా వచ్చింది",
    ("late", "en"): "Delivery was {hrs} hours late",
    ("rate_query", "rt"): "ee nela rate enduku perigindi?", ("rate_query", "te"): "ఈ నెల రేట్ ఎందుకు పెరిగింది?",
    ("rate_query", "en"): "Why did the rate go up this month?",
    ("short_supply", "rt"): "order lo konni items takkuva vachayi", ("short_supply", "te"): "ఆర్డర్ లో కొన్ని ఐటమ్స్ తక్కువ వచ్చాయి",
    ("short_supply", "en"): "Some items short in the order",
}
SPELL = {"Hanamkonda": ["Hanumakonda", "HNK"], "Jangaon": ["Janagama", "Jangaon"], "Kazipet": ["Kajipet"],
         "Mahabubabad": ["Mahabubabad", "MBD"], "Narsampet": ["Narsampeta"], "Khammam": ["Kammam"]}
VOICE_SLIPS = {"jangaon": "jangam", "hanamkonda": "hanumakonda", "kazipet": "kaji pet", "mahabubabad": "mahabubabadu",
               "narsampet": "narsam peta", "khammam": "kammam", "chowrasta": "chourasta"}
NUM_WORDS = {"2": "rendu", "3": "moodu", "4": "nalugu", "6": "aaru", "8": "enimidi", "10": "padi", "22": "iravai rendu",
             "32": "muppai rendu"}


def lang_pick(r, cfg, key="languages"):
    w = cfg[key]
    return r.choices(list(w), list(w.values()))[0]


def site_ref(W, cid, site, r, short=False):
    for rule in W.rules_of("alias"):
        if cid in rule["companies"] and rule["resolved"].get(cid) == site["site_id"] and r.random() < rule["rate"]:
            return rule["phrase"]
    town = r.choice(SPELL.get(site["town"], [site["town"]])) if r.random() < 0.25 else site["town"]
    return r.choice([site["name"], f"{town} {site['name'].split()[0]}", town] if short else [site["name"], f"{town} {site['name']}"])


def veh_ref(W, cid, v, r):
    for rule in W.rules_of("alias"):
        if cid in rule["companies"] and rule["resolved"].get(cid) == v["vehicle_id"] and r.random() < rule["rate"]:
            return rule["phrase"]
    for rule in W.rules_of("alias"):
        if cid in rule["companies"] and rule["resolved"].get(cid) == v["vendor"] and r.random() < rule["rate"]:
            return f"{rule['phrase']} bandi"
    return r.choice([v["vehicle_id"], v["reg_no"], f"{W.cfg['vehicle_classes'][v['class']]['label']} bandi"])


def vendor_ref(W, cid, vendor, r):
    for rule in W.rules_of("alias"):
        if cid in rule["companies"] and rule["resolved"].get(cid) == vendor and r.random() < rule["rate"]:
            return rule["phrase"]
    return vendor


def fill(tpl, **kw):
    return tpl.format_map({k: v for k, v in kw.items()} | {k: "" for k in re.findall(r"{(\w+)}", tpl) if k not in kw})


def voice(text, r):
    s = text.lower()
    s = re.sub(r"[,.!?]", "", s)
    for k, v in VOICE_SLIPS.items():
        if k in s and r.random() < 0.5:
            s = s.replace(k, v)
    for k, v in NUM_WORDS.items():
        if r.random() < 0.5:
            s = re.sub(rf"\b{k}\b", v, s)
    return ("aa " if r.random() < 0.4 else "") + s + (" sir sir" if r.random() < 0.2 else "")


def run(W, t):
    cfg = W.cfg
    ships = {s["shipment_id"]: s for s in t["shipments"]}
    veh = {(v["company"], v["vehicle_id"]): v for v in W.vehicles}
    drivers = {d["driver_id"]: d for d in W.drivers}
    for s in t["shipments"]:
        cid = s["company"]
        r = rng(cfg, "notes", cid, s["shipment_id"])
        planner = next(p for p in W.companies[cid]["planners"] if p["name"] == s["planned_by"])
        lang = planner["lang"] if r.random() < 0.8 else lang_pick(r, cfg)
        stops = [W.site(cid, x["site_id"]) for x in t["shipment_stops"] if x["shipment_id"] == s["shipment_id"]]
        v = veh[(cid, s["vehicle_id"])]
        site_txt = " + ".join(site_ref(W, cid, st, r) for st in stops)
        msg = fill(r.choice(T[("assign", lang)]), site=site_txt, veh=veh_ref(W, cid, v, r), town=stops[0]["town"])
        chilled = s["vehicle_class"] != "REEFER14" and any(
            W.products and it["sku"].startswith("KD") for it in t["shipment_items"] if it["shipment_id"] == s["shipment_id"])
        if chilled and r.random() < 0.6:
            msg = fill(r.choice(T[("ice_box", lang)]), veh=veh_ref(W, cid, v, r))
        _msg(t, cid, s["planned_at"], planner["name"], lang, msg, s["shipment_id"])
    for p in t["vehicle_placements"]:
        if p["status"] != "no_show":
            continue
        cid = p["company"]
        r = rng(cfg, "notes", cid, "ns", p["shipment_id"], p["vehicle_id"])
        planner = r.choice(W.companies[cid]["planners"])
        nxt = next((e["new"] for e in t["staff_edits"] if e["entity_id"] == p["shipment_id"] and e["old"] == p["vehicle_id"]), None)
        if nxt:
            lang = planner["lang"]
            msg = fill(r.choice(T[("no_show", lang)]), vendor=vendor_ref(W, cid, p["vendor"], r),
                       veh=veh_ref(W, cid, veh[(cid, nxt)], r))
            _msg(t, cid, iso(datetime.fromisoformat(p["confirmed_at"]) + timedelta(hours=3)), planner["name"], lang, msg,
                 p["shipment_id"])
    recent = {}
    for e in sorted(t["trip_events"], key=lambda e: e["ts"]):
        _driver_note(W, t, e, ships, veh, drivers, recent)
    for f in t["feedback"]:
        r = rng(cfg, "notes", f["company"], "fb", f["ts"], f["kind"])
        lang = lang_pick(r, cfg)
        site = W.site(f["company"], f["site_id"])
        f["text"] = fill(FEEDBACK[(f["kind"], lang)], site=site_ref(W, f["company"], site, r, True), hrs=round(f.get("hours", 2)),
                         cases=f.get("cases", 3))
        f["lang"] = lang
    for e in t["staff_edits"]:
        r = rng(cfg, "notes", e["company"], "edit", e["edit_id"])
        e["reason_text"] = _edit_reason(e, r)
    return t


def _msg(t, cid, ts, who, lang, text, ref):
    t["planner_messages"].append({"company": cid, "ts": ts, "from": who, "lang": lang, "text": text, "shipment_id": ref})


def _driver_note(W, t, e, ships, veh, drivers, recent):
    cfg = W.cfg
    cid, sid = e["company"], e["shipment_id"]
    r = rng(cfg, "notes", cid, sid, e["ts"], e["kind"], e.get("stop_seq"))
    kind, cause = e["kind"], e.get("true_cause")
    key, p = None, 0.0
    if kind == "not_delivered":
        key, p = {"could_not_enter": "could_not_enter", "shop_closed": "shop_closed",
                  "road_blocked": "road_blocked"}[e["status_seen"]], 1.0
    elif kind == "waiting":
        key = {"time_window": "wait_time_window", "receiving_hours": "wait_receiving", "night_only": "wait_night",
               "godown_full": "wait_godown_full"}.get(cause, "wait_generic")
        p = 0.75 if e["minutes"] >= 60 else 0.2
    elif kind == "delay":
        key = {"closure": "delay_closure", "address": "delay_address", "breakdown": "delay_breakdown", "rain": "delay_rain",
               "bandh": "delay_bandh", "missing_eway_bill": "delay_missing_eway_bill"}[e["cause_seen"]]
        p = 0.65
    elif kind == "weighbridge_offload":
        key, p = "offload", 1.0
    elif kind == "rejected_at_loading":
        key, p = "rejected", 0.9
    elif kind == "partially_delivered":
        key, p = "partial", 0.8
    elif kind == "delivered":
        key, p = "delivered", 0.08
    last = recent.get((cid, key))
    if last and (datetime.fromisoformat(e["ts"]) - last).days < 3 and kind not in ("not_delivered", "weighbridge_offload"):
        p *= 0.3                      # everyone already knows; drivers stop reporting it every time
    if not key or r.random() >= p:
        return
    recent[(cid, key)] = datetime.fromisoformat(e["ts"])
    s = ships[sid]
    v = veh[(cid, s["vehicle_id"])]
    d = drivers.get(s["driver"])
    lang = d["lang"] if d and r.random() < 0.85 else lang_pick(r, cfg, "driver_languages")
    site = None
    if e.get("stop_seq"):
        stop = next(x for x in t["shipment_stops"] if x["shipment_id"] == sid and x["seq"] == e["stop_seq"])
        site = W.site(cid, stop["site_id"])
    vague = r.random() < cfg["wrong_or_vague_note_share"] and key not in ("could_not_enter",)
    if vague:
        key = "wrong_gate" if key in ("wait_godown_full", "wait_generic") and r.random() < 0.5 else "vague"
    text = fill(r.choice(T[(key, lang)]), site=site_ref(W, cid, site, r, True) if site else "",
                town=site["town"] if site else "", len=v["length_ft"], veh=veh_ref(W, cid, v, r),
                hrs=max(1, round(e.get("minutes", 120) / 60)), min=e.get("minutes", 40) or 40,
                off=e.get("kg", 0), tons=round(e.get("kg", 0) / 1000 + v["real_payload_kg"] / 1000), cases=r.randint(3, 20))
    source = "voice" if r.random() < cfg["voice_note_share"] and lang != "en" else "text"
    if source == "voice":
        text = voice(text, r)
    t["driver_notes"].append({"company": cid, "ts": iso(datetime.fromisoformat(e["ts"]) + timedelta(minutes=r.randint(2, 25))),
                              "shipment_id": sid, "stop_seq": e.get("stop_seq"), "driver": s["driver"], "lang": lang,
                              "source": source, "text": text, "_true_cause": cause, "_rule_id": e.get("rule_id"),
                              "_vague": vague})


def _edit_reason(e, r):
    reasons = {"vendor_no_show": ["vendor bandi raledu", "bandi pettaledu", "vehicle not placed"],
               "documents_expired": ["fitness ayipoyindi", "papers expired"],
               "site_access": ["gate chinnadi", "pedda bandi vellatledu", "lane narrow"],
               "receiving_hours": ["6 tarvata teesukoru", "receiving time changed"],
               "night_only": ["night ke unload", "receives only at night"], "weekly_off": ["Tuesday band", "weekly off"],
               "time_window": ["pagalu entry ledu", "day time no entry"], "moved_godown": ["kotha godown", "address changed"],
               "reverted": ["wrong update", "mistake, reverting"]}
    return r.choice(reasons.get(e["reason_code"], [e["reason_code"].replace("_", " ")]))
