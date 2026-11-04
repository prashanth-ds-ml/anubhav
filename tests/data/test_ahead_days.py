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


def test_the_hosted_world_is_made_again_when_its_history_does_not_end_today(tmp_path, monkeypatch):
    """Nov 4: the agent answered for 30 Oct. With ANUBHAV_WORLD_END=today the history runs through the real date (open
    orders start tomorrow); a world from an earlier day is generated again at start-up."""
    import json
    from datetime import date
    from anubhav.service import session
    world = tmp_path / "w"
    world.mkdir()
    (world / "manifest.json").write_text(json.dumps({"window": ["2026-08-01", "2026-10-29"]}))
    calls = []
    monkeypatch.setattr("anubhav.data.generate.main", lambda argv: calls.append(argv) or 0)
    monkeypatch.delenv("ANUBHAV_WORLD_END", raising=False)
    session.ensure_world(world)
    assert calls == []                                                  # locally and in tests: the world is kept
    monkeypatch.setenv("ANUBHAV_WORLD_END", "today")
    session.ensure_world(world)
    assert calls == [["--full", "--end", "today", "--ahead-days", "5"]]
    (world / "manifest.json").write_text(json.dumps({"window": ["2026-08-01", date.today().isoformat()]}))
    session.ensure_world(world)
    assert len(calls) == 1                                              # already today's world: not made again
