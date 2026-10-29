"""A company's data as the agent's tools see it: its own SQLite database in its own physical schema (A/B/C),
read through the inverse adapter mapping into the canonical model. Plus a small runtime store for what the
agent writes (drafts, exclusive holds, appended notes, audit). The company's records are never modified."""

import json
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from ..data.store import to_canonical

SPELLINGS = {"hanumakonda": "hanamkonda", "hnk": "hanamkonda", "janagama": "jangaon", "kajipet": "kazipet",
             "narsampeta": "narsampet", "kammam": "khammam", "mbd": "mahabubabad", "wgl": "warangal"}


class CompanyData:
    def __init__(self, world_dir: Path, company: str, runtime_dir: Path | None = None):
        world_dir = Path(world_dir)
        manifest = json.loads((world_dir / "manifest.json").read_text(encoding="utf-8"))
        self.company, self.variant = company, manifest["variants"][company]
        self.today = (date.fromisoformat(manifest["window"][1]) + timedelta(days=1)).isoformat()
        con = sqlite3.connect(world_dir / manifest["files"][company])
        con.row_factory = sqlite3.Row
        physical = {name: [dict(r) for r in con.execute(f'select * from "{name}"')]
                    for (name,) in con.execute("select name from sqlite_master where type='table'")}
        con.close()
        self.t = to_canonical(physical, self.variant)
        for name in ("orders", "order_items", "sites", "vehicles", "products", "trip_outcomes", "driver_notes",
                     "planner_messages", "feedback", "written_policies", "site_access_rules", "shipments", "shipment_stops"):
            self.t.setdefault(name, [])
        self.sites = {s["site_id"]: s for s in self.t["sites"]}
        self.vehicles = {v["vehicle_id"]: v for v in self.t["vehicles"]}
        self.products = {p["sku"]: p for p in self.t["products"]}
        self.orders = {o["order_id"]: o for o in self.t["orders"]}
        self.items = {}
        for i in self.t["order_items"]:
            self.items.setdefault(i["order_id"], []).append(i)
        self.runtime = Runtime((runtime_dir or world_dir / "runtime") / f"{company}.sqlite")

    def order_load(self, order_id):
        lines = self.items.get(order_id, [])
        kg = sum(self.products[i["sku"]]["case_kg"] * i["ordered_cases"] for i in lines)
        m3 = sum(self.products[i["sku"]]["case_m3"] * i["ordered_cases"] for i in lines)
        value = sum(self.products[i["sku"]]["price_rs"] * i["ordered_cases"] for i in lines)
        classes = sorted({self.products[i["sku"]]["handling_class"] for i in lines})
        return {"kg": round(kg, 1), "m3": round(m3, 2), "value_rs": round(value), "cases": sum(i["ordered_cases"] for i in lines),
                "handling_classes": classes}


class Runtime:
    """Agent-written state. Exclusive holds rely on a UNIQUE constraint inside one transaction, so two concurrent
    drafts can never hold the same vehicle on the same day; an idempotency key makes retries return the same draft."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.lock = path, threading.Lock()
        with self._con() as con:
            con.executescript("""
                create table if not exists drafts (draft_id text primary key, created_at text, created_by text,
                    status text, delivery_date text, vehicle_id text, order_ids text, verdict text, idempotency_key text unique);
                create table if not exists holds (vehicle_id text, delivery_date text, draft_id text,
                    unique (vehicle_id, delivery_date));
                create table if not exists added_notes (ts text, author text, shipment_id text, lang text, text text);
                create table if not exists audit (ts text, user text, role text, tool text, args text, outcome text);
            """)

    def _con(self):
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    def reset(self):
        with self._con() as con:
            for t in ("drafts", "holds", "added_notes", "audit"):
                con.execute(f"delete from {t}")

    def create_draft(self, draft_id, user, delivery_date, vehicle_id, order_ids, verdict, idempotency_key):
        """Returns (draft row, created?). Raises Conflict if the vehicle is already held that day."""
        con = self._con()
        try:
            con.execute("begin immediate")
            prior = con.execute("select * from drafts where idempotency_key = ?", (idempotency_key,)).fetchone()
            if prior:
                con.execute("commit")
                return dict(prior), False
            held = con.execute("select draft_id from holds where vehicle_id = ? and delivery_date = ?",
                               (vehicle_id, delivery_date)).fetchone()
            if held:
                con.execute("rollback")
                raise Conflict(f"vehicle {vehicle_id} is already held for {delivery_date} by draft {held['draft_id']}")
            now = datetime.now().isoformat(timespec="seconds")
            con.execute("insert into holds values (?, ?, ?)", (vehicle_id, delivery_date, draft_id))
            con.execute("insert into drafts values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (draft_id, now, user, "draft", delivery_date, vehicle_id, json.dumps(order_ids),
                         json.dumps(verdict, ensure_ascii=False), idempotency_key))
            con.execute("commit")
            return dict(con.execute("select * from drafts where draft_id = ?", (draft_id,)).fetchone()), True
        except Conflict:
            raise
        except Exception:
            con.execute("rollback")
            raise
        finally:
            con.close()

    def by_key(self, key):
        with self._con() as con:
            r = con.execute("select * from drafts where idempotency_key = ?", (key,)).fetchone()
            return dict(r) if r else None

    def draft(self, draft_id):
        with self._con() as con:
            r = con.execute("select * from drafts where draft_id = ?", (draft_id,)).fetchone()
            return dict(r) if r else None

    def drafts(self, delivery_date=None):
        with self._con() as con:
            q = "select * from drafts" + (" where delivery_date = ?" if delivery_date else "")
            return [dict(r) for r in con.execute(q, (delivery_date,) if delivery_date else ())]

    def held(self, vehicle_id, delivery_date):
        with self._con() as con:
            r = con.execute("select draft_id from holds where vehicle_id = ? and delivery_date = ?",
                            (vehicle_id, delivery_date)).fetchone()
            return r["draft_id"] if r else None

    def orders_in_drafts(self, delivery_date):
        out = set()
        for d in self.drafts(delivery_date):
            if d["status"] == "draft":
                out |= set(json.loads(d["order_ids"]))
        return out

    def cancel(self, draft_id):
        con = self._con()
        try:
            con.execute("begin immediate")
            n = con.execute("update drafts set status = 'cancelled' where draft_id = ? and status = 'draft'", (draft_id,)).rowcount
            con.execute("delete from holds where draft_id = ?", (draft_id,))
            con.execute("commit")
            return n == 1
        finally:
            con.close()

    def add_note(self, author, shipment_id, lang, text):
        with self._con() as con:
            con.execute("insert into added_notes values (?, ?, ?, ?, ?)",
                        (datetime.now().isoformat(timespec="seconds"), author, shipment_id, lang, text))

    def audit(self, user, role, tool, args, outcome):
        with self._con() as con:
            con.execute("insert into audit values (?, ?, ?, ?, ?, ?)", (datetime.now().isoformat(timespec="seconds"), user,
                        role, tool, json.dumps(args, ensure_ascii=False, default=str), outcome))

    def audit_rows(self):
        with self._con() as con:
            return [dict(r) for r in con.execute("select * from audit")]


class Conflict(Exception):
    pass
