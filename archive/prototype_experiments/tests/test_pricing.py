import pytest

from order_agent import db
from order_agent.pricing import compute_quote, to_cases


@pytest.fixture
def conn(tmp_path):
    c = db.connect(db.reset(tmp_path / "business.db"))
    yield c
    c.close()


def test_golden_path(conn):
    q = compute_quote(conn, "C-001", [("GG-SUN-1L", 12)])
    line = q.lines[0]
    assert (line.price_source, line.case_price_paise, line.discount_bp) == ("list", 174000, 500)
    assert line.line_total_paise == 12 * 174000 * 95 // 100
    assert (line.available_cases, line.shortage_cases) == (8, 4)
    assert "2026-11-02" in line.note and "DP-SUN-1L" in line.note
    assert q.flags == ["shortage"]


def test_customer_price_beats_bulk_and_skips_discount(conn):
    line = compute_quote(conn, "C-008", [("GG-SUN-1L", 30)]).lines[0]
    assert (line.price_source, line.case_price_paise, line.discount_bp) == ("customer", 169000, 0)


def test_bulk_price_and_discount_stack(conn):
    line = compute_quote(conn, "C-013", [("KS-SONA-25", 60)]).lines[0]
    assert (line.price_source, line.case_price_paise, line.discount_bp) == ("bulk", 140000, 500)


def test_below_min_cases_no_discount(conn):
    assert compute_quote(conn, "C-001", [("GG-SUN-1L", 9)]).lines[0].discount_bp == 0


def test_scheme_tier_and_dates(conn):
    gold = compute_quote(conn, "C-017", [("NN-DET-1K", 10)]).lines[0]
    assert (gold.scheme_id, gold.free_cases) == ("S-02", 2)
    silver = compute_quote(conn, "C-002", [("NN-DET-1K", 10)]).lines[0]
    assert silver.free_cases == 0  # S-02 is gold-only
    expired = compute_quote(conn, "C-003", [("KS-GHEE-1L", 5)]).lines[0]
    assert expired.free_cases == 0  # S-04 ended 2026-10-15


def test_credit_hold_blocks_discount_and_scheme(conn):
    q = compute_quote(conn, "C-006", [("KF-NOOD-70", 10)])
    assert q.lines[0].discount_bp == 0 and q.lines[0].free_cases == 0
    assert "credit_hold" in q.flags


def test_credit_limit_warning(conn):
    assert "over_credit_limit" in compute_quote(conn, "C-005", [("PF-MOONG-1", 6)]).flags
    assert "over_credit_limit" not in compute_quote(conn, "C-004", [("KF-SALT-1", 50)]).flags  # cash customer


def test_inactive_customer_gets_no_quote(conn):
    q = compute_quote(conn, "C-010", [("KF-SUGAR-1", 4)])
    assert not q.allowed and q.flags == ["inactive_customer"] and not q.lines


@pytest.mark.parametrize("sku, qty, unit, expected", [
    ("KF-SUGAR-50", 2, "bag", (2, False)),
    ("KS-SES-1L", 24, "piece", (2, False)),
    ("NN-SOAP-100", 3, "dozen", (1, True)),
    ("PF-TOOR-1", 50, "kg", (3, True)),
    ("GG-SUN-15L", 5, "tin", (5, False)),
])
def test_unit_conversion(conn, sku, qty, unit, expected):
    assert to_cases(conn, sku, qty, unit) == expected


def test_invalid_unit(conn):
    with pytest.raises(ValueError):
        to_cases(conn, "GG-SUN-1L", 2, "bag")
