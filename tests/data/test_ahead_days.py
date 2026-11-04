"""Open orders booked for the days after today (the hosted demo's week to plan) change nothing generated before them."""

from anubhav.data import config, generate


def _gen(ahead):
    cfg = config.load(config.DEFAULT_CONFIG)
    p = cfg["pilot"]
    return generate.generate(cfg, p["companies"], str(p["start"]), str(p["end"]), ahead)[1]


def test_days_ahead_only_add_open_orders_and_change_nothing_before():
    base, more = _gen(0), _gen(3)
    for table, rows in base.items():
        if table.startswith("_") or not isinstance(rows, list):
            continue
        assert more[table][: len(rows)] == rows, table                       # every earlier row unchanged, same order
    today = max(o["delivery_date"] for o in base["orders"])
    extra = more["orders"][len(base["orders"]):]
    assert extra and {o["status"] for o in extra} == {"open"}
    assert all(o["delivery_date"] > today for o in extra)
    assert all(o["created_at"][:10] < today for o in extra)                  # booked before today, never in the future
    assert len(more["order_items"]) > len(base["order_items"])
