"""Domain packs: sharing approved regional knowledge with another company without leaking private information.

What may travel is decided by code, never by the model's opinion:
- only regional kinds (site and place facts, and nicknames for sites); never vehicles, vendors or capacities;
- only active, approved lessons;
- only if the recipient has the same site (matched by name + town, i.e. public identity) or the same town;
- the lesson is re-written in the recipient's own ids, so no source id, vehicle, vendor or driver appears.
Publishing needs the source's approval; importing needs the recipient's opt-in; a pack can be revoked."""

import json
import sqlite3
from datetime import datetime

from .store import ACTIVE

REGIONAL = {"site_access", "receiving_hours", "night_only", "time_window", "weekly_off", "closure", "moved_site", "alias"}


def eligible(les):
    if les["state"] not in ACTIVE or les["kind"] not in REGIONAL:
        return False
    if les["kind"] == "alias" and les["params"].get("target_kind") != "site":
        return False             # truck and vendor nicknames are private
    return True


def private_tokens(C):
    """Everything about the source company that must never reach another company."""
    toks = set()
    for v in C.vehicles.values():
        toks |= {v["vehicle_id"], v["reg_no"]}
        if v["owner"] != "own":
            toks.add(v["vendor"])
    toks |= {s["site_id"] for s in C.sites.values()}
    toks |= {d.get("name", "") for d in C.t.get("drivers", [])}
    return {t for t in toks if t and len(t) >= 3}


def translate(les, src, dst):
    """Re-express a lesson in the recipient's ids. Returns None if the recipient has no matching site/town."""
    p = dict(les["params"])
    sid = p.get("site_id") or (p.get("target_id") if les["kind"] == "alias" else None)
    if sid:
        s = src.sites.get(sid)
        match = [x for x in dst.sites.values() if s and x["name"] == s["name"] and x["town"] == s["town"]]
        if not match:
            return None
        if "site_id" in p:
            p["site_id"] = match[0]["site_id"]
        else:
            p["target_id"] = match[0]["site_id"]
    elif "town" in p:
        if not any(x["town"].lower() == str(p["town"]).lower() for x in dst.sites.values()):
            return None
    return p


def publish(store, src, dst, approved_by, lesson_ids=None):
    """Source side: choose eligible lessons and record the publication (needs an approver)."""
    if not approved_by:
        raise PermissionError("publishing a pack needs the source company's approval")
    lessons = [l for l in store.list(src.company) if eligible(l) and (not lesson_ids or l["lesson_id"] in lesson_ids)]
    items, skipped = [], []
    for les in lessons:
        p = translate(les, src, dst)
        if p is None:
            skipped.append((les["lesson_id"], "recipient has no matching site or town"))
            continue
        g = les["gate"]          # only counts travel; the source's wording and ids stay at home
        items.append({"kind": les["kind"], "params": p, "source_lesson": les["lesson_id"].split("-")[-1], "effect": les["effect"],
                      "evidence": f"another company in the region: {g.get('support', 0)} supporting observation(s), "
                                  f"{g.get('counter', 0)} against; approved by its reviewer"})
    pack_id = f"PK-{src.company}-{dst.company}-{datetime.now():%H%M%S}"
    found = leaks({"items": items}, src, dst)
    if found:
        raise PermissionError(f"pack would leak private information: {found}")
    with store._con() as con:
        con.execute("create table if not exists packs (pack_id text primary key, source text, recipient text, approved_by text, "
                    "created text, items text, status text)")
        con.execute("insert into packs values (?,?,?,?,?,?,?)", (pack_id, src.company, dst.company, approved_by,
                    datetime.now().isoformat(timespec="seconds"), json.dumps(items, ensure_ascii=False), "published"))
    return {"pack_id": pack_id, "items": items, "skipped": skipped}


def leaks(pack, src, dst=None):
    """Source-private tokens found in the pack. The recipient's own ids are never a leak (two companies can share an
    id format, e.g. both number their sites C0001…). Matching is on whole tokens, not substrings."""
    import re
    toks = private_tokens(src)
    if dst is not None:
        toks -= set(dst.sites) | set(dst.vehicles)
    text = json.dumps(pack["items"], ensure_ascii=False)
    return sorted(t for t in toks if re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", text))


def _key(kind, params):
    return kind, json.dumps({k: str(v).lower() for k, v in (params or {}).items()}, sort_keys=True)


def import_pack(store, pack, dst, accepted_by, accept_policies=False):
    """Recipient side: opt in. Lessons arrive as advice unless the recipient also accepts enforceable policies.
    A lesson the recipient already received from another partner is not duplicated: it gains a confirmation."""
    if not accepted_by:
        raise PermissionError("importing a pack needs the recipient's opt-in")
    existing = {_key(l["kind"], l["params"]): l for l in store.list(dst.company, ACTIVE)}
    ids = []
    with store._con() as con:
        n = con.execute("select count(*) from lessons where company = ?", (dst.company,)).fetchone()[0]
        for it in pack["items"]:
            now = datetime.now().isoformat(timespec="seconds")
            prior = existing.get(_key(it["kind"], it["params"]))
            if prior:
                g = dict(prior["gate"])
                g["confirmed_by"] = sorted(set(g.get("confirmed_by", [])) | {pack["pack_id"]})
                g["reason"] = f"confirmed by {len(g['confirmed_by'])} partner companies"
                con.execute("update lessons set gate = ?, updated = ? where lesson_id = ?", (json.dumps(g), now, prior["lesson_id"]))
                store._event(con, prior["lesson_id"], dst.company, accepted_by, "confirm", prior["state"], prior["state"], pack["pack_id"])
                ids.append(prior["lesson_id"])
                continue
            n += 1
            lid = f"L-{dst.company}-{n:03d}"
            state = "ACTIVE_POLICY" if accept_policies and it["effect"] == "policy" else "ACTIVE_ADVISORY"
            gate = {"verdict": "imported", "reason": f"from a partner company: {it['evidence']}",
                    "enforceable": it["kind"] == "site_access", "confirmed_by": [pack["pack_id"]]}
            con.execute("insert into lessons values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (lid, dst.company, it["kind"], json.dumps(it["params"], ensure_ascii=False), "", state,
                         "policy" if state == "ACTIVE_POLICY" else "advisory", json.dumps(gate), json.dumps({}),
                         f"pack:{pack['pack_id']}", now, now, accepted_by, "imported", None, None))
            store._event(con, lid, dst.company, accepted_by, "import", None, state, pack["pack_id"])
            existing[_key(it["kind"], it["params"])] = {"lesson_id": lid, "kind": it["kind"],
                                                                                   "params": it["params"], "gate": gate, "state": state}
            ids.append(lid)
    return list(dict.fromkeys(ids))


def revoke(store, pack_id, dst_company, actor):
    """Revoking a pack removes its confirmation; a lesson no other partner confirms is retired."""
    out = []
    for les in store.list(dst_company, ACTIVE):
        conf = les["gate"].get("confirmed_by") or ([les["source"].split(":", 1)[1]] if les["source"].startswith("pack:") else [])
        if pack_id not in conf:
            continue
        rest = [c for c in conf if c != pack_id]
        if rest:
            g = dict(les["gate"], confirmed_by=rest, reason=f"confirmed by {len(rest)} partner compan{'y' if len(rest) == 1 else 'ies'}")
            with store._con() as con:
                con.execute("update lessons set gate = ?, source = ? where lesson_id = ?", (json.dumps(g), f"pack:{rest[0]}", les["lesson_id"]))
                store._event(con, les["lesson_id"], dst_company, actor, "unconfirm", les["state"], les["state"], pack_id)
            out.append(store.get(les["lesson_id"]))
        else:
            out.append(store.retire(les["lesson_id"], actor, f"pack {pack_id} revoked"))
