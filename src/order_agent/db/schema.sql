-- Fictional wholesale business simulator. Money is stored as integer paise.
-- Source of truth: datasets/business/*.csv (rupees); seed.py converts and loads them.

CREATE TABLE customers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    city            TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('gold', 'silver', 'bronze')),
    active          INTEGER NOT NULL DEFAULT 1,
    credit_status   TEXT NOT NULL CHECK (credit_status IN ('ok', 'watch', 'hold')),
    payment_terms   TEXT NOT NULL,                 -- e.g. 'net15', 'cash'
    credit_limit_paise INTEGER NOT NULL,
    outstanding_paise  INTEGER NOT NULL DEFAULT 0
);

-- Names as people say them: English, Telugu script, Roman Telugu.
CREATE TABLE customer_aliases (
    customer_id     TEXT NOT NULL REFERENCES customers(id),
    alias           TEXT NOT NULL,
    script          TEXT NOT NULL CHECK (script IN ('en', 'te', 'roman')),
    PRIMARY KEY (customer_id, alias)
);

CREATE TABLE products (
    sku             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    brand           TEXT NOT NULL,
    type            TEXT NOT NULL,                 -- e.g. 'sunflower oil'; several SKUs share a type
    variant         TEXT NOT NULL DEFAULT '',      -- e.g. 'neem', 'tin', 'bag'
    category        TEXT NOT NULL,
    pack_size       TEXT NOT NULL,                 -- human label, e.g. '1 L', '15 L tin'
    size_value      REAL NOT NULL,
    size_unit       TEXT NOT NULL CHECK (size_unit IN ('g', 'kg', 'ml', 'L')),
    units_per_case  INTEGER NOT NULL,              -- pieces per case
    gst_rate_bp     INTEGER NOT NULL,              -- GST in basis points, 500 = 5%
    mrp_paise       INTEGER NOT NULL,              -- printed MRP per piece
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE product_aliases (
    sku             TEXT NOT NULL REFERENCES products(sku),
    alias           TEXT NOT NULL,
    script          TEXT NOT NULL CHECK (script IN ('en', 'te', 'roman')),
    kind            TEXT NOT NULL CHECK (kind IN ('generic', 'brand', 'pack')),
    PRIMARY KEY (sku, alias)
);

CREATE TABLE units (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL
);

CREATE TABLE unit_aliases (
    unit_code       TEXT NOT NULL REFERENCES units(code),
    alias           TEXT NOT NULL,
    script          TEXT NOT NULL CHECK (script IN ('en', 'te', 'roman')),
    PRIMARY KEY (unit_code, alias)
);

-- How many pieces one unit of a SKU means (case = units_per_case, kg on a 500 g pack = 2).
CREATE TABLE product_units (
    sku             TEXT NOT NULL REFERENCES products(sku),
    unit_code       TEXT NOT NULL REFERENCES units(code),
    pieces_per_unit REAL NOT NULL,
    PRIMARY KEY (sku, unit_code)
);

CREATE TABLE substitutes (
    sku             TEXT NOT NULL REFERENCES products(sku),
    substitute_sku  TEXT NOT NULL REFERENCES products(sku),
    PRIMARY KEY (sku, substitute_sku)
);

CREATE TABLE warehouses (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    city            TEXT NOT NULL
);

CREATE TABLE inventory (
    sku             TEXT NOT NULL REFERENCES products(sku),
    warehouse_id    TEXT NOT NULL REFERENCES warehouses(id),
    on_hand_cases   INTEGER NOT NULL,
    reserved_cases  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sku, warehouse_id)
);

CREATE TABLE restocks (
    sku             TEXT NOT NULL REFERENCES products(sku),
    warehouse_id    TEXT NOT NULL REFERENCES warehouses(id),
    expected_date   TEXT NOT NULL,                 -- ISO date
    cases           INTEGER NOT NULL
);

-- Standard (list) price per case. Customer-specific and bulk prices are rules on top.
CREATE TABLE prices (
    sku             TEXT PRIMARY KEY REFERENCES products(sku),
    case_price_paise INTEGER NOT NULL
);

CREATE TABLE bulk_prices (
    sku             TEXT NOT NULL REFERENCES products(sku),
    min_cases       INTEGER NOT NULL,
    case_price_paise INTEGER NOT NULL,
    PRIMARY KEY (sku, min_cases)
);

CREATE TABLE customer_prices (
    customer_id     TEXT NOT NULL REFERENCES customers(id),
    sku             TEXT NOT NULL REFERENCES products(sku),
    case_price_paise INTEGER NOT NULL,
    PRIMARY KEY (customer_id, sku)
);

-- Tier discount policy: percentage off when the order line meets min_cases.
CREATE TABLE discount_rules (
    tier            TEXT PRIMARY KEY,
    discount_bp     INTEGER NOT NULL,              -- 500 = 5%
    min_cases       INTEGER NOT NULL
);

-- Trade schemes: buy N cases, get M free, within dates, for some tiers.
CREATE TABLE schemes (
    id              TEXT PRIMARY KEY,
    sku             TEXT NOT NULL REFERENCES products(sku),
    buy_cases       INTEGER NOT NULL,
    free_cases      INTEGER NOT NULL,
    valid_from      TEXT NOT NULL,
    valid_to        TEXT NOT NULL,
    tiers           TEXT NOT NULL,                 -- 'all' or comma-separated tiers
    description     TEXT NOT NULL
);

CREATE TABLE policies (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

CREATE TABLE quotes (
    id              TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(id),
    status          TEXT NOT NULL CHECK (status IN ('draft')),   -- MVP: drafts only
    created_at      TEXT NOT NULL,
    harness_version TEXT,
    run_id          TEXT,
    source_request  TEXT,
    flags           TEXT NOT NULL DEFAULT '[]',    -- JSON list, e.g. ["credit_hold", "shortage"]
    notes           TEXT
);

CREATE TABLE quote_lines (
    quote_id        TEXT NOT NULL REFERENCES quotes(id),
    line_no         INTEGER NOT NULL,
    sku             TEXT NOT NULL REFERENCES products(sku),
    cases           INTEGER NOT NULL,
    free_cases      INTEGER NOT NULL DEFAULT 0,
    scheme_id       TEXT REFERENCES schemes(id),
    price_source    TEXT NOT NULL CHECK (price_source IN ('customer', 'bulk', 'list')),
    case_price_paise INTEGER NOT NULL,
    discount_bp     INTEGER NOT NULL DEFAULT 0,
    line_total_paise INTEGER NOT NULL,             -- after discount, before GST
    gst_paise       INTEGER NOT NULL,
    available_cases INTEGER NOT NULL,
    shortage_cases  INTEGER NOT NULL DEFAULT 0,
    note            TEXT,
    PRIMARY KEY (quote_id, line_no)
);

CREATE TABLE orders (
    id              TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(id),
    status          TEXT NOT NULL CHECK (status IN ('draft', 'confirmed', 'dispatched', 'delivered')),
    created_at      TEXT NOT NULL,
    total_paise     INTEGER NOT NULL
);

CREATE TABLE order_lines (
    order_id        TEXT NOT NULL REFERENCES orders(id),
    line_no         INTEGER NOT NULL,
    sku             TEXT NOT NULL REFERENCES products(sku),
    cases           INTEGER NOT NULL,
    case_price_paise INTEGER NOT NULL,
    PRIMARY KEY (order_id, line_no)
);
