-- Fictional wholesale business simulator. Money is stored as integer paise.

CREATE TABLE customers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    aliases         TEXT NOT NULL DEFAULT '[]',   -- JSON list (English, Telugu script, Roman Telugu)
    city            TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('gold', 'silver', 'bronze')),
    active          INTEGER NOT NULL DEFAULT 1,
    credit_status   TEXT NOT NULL CHECK (credit_status IN ('ok', 'watch', 'hold')),
    payment_terms   TEXT NOT NULL,                 -- e.g. 'net15', 'cash'
    credit_limit_paise INTEGER NOT NULL,
    outstanding_paise  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE products (
    sku             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    brand           TEXT NOT NULL,
    category        TEXT NOT NULL,
    aliases         TEXT NOT NULL DEFAULT '[]',    -- JSON list (English, Telugu script, Roman Telugu)
    base_unit       TEXT NOT NULL,                 -- 'piece' (bottle/packet/bag)
    pack_size       TEXT NOT NULL,                 -- human label, e.g. '1 L', '25 kg'
    units_per_case  INTEGER NOT NULL,              -- pieces per carton
    gst_rate_bp     INTEGER NOT NULL,              -- GST in basis points, 500 = 5%
    active          INTEGER NOT NULL DEFAULT 1
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
    notes           TEXT
);

CREATE TABLE quote_lines (
    quote_id        TEXT NOT NULL REFERENCES quotes(id),
    line_no         INTEGER NOT NULL,
    sku             TEXT NOT NULL REFERENCES products(sku),
    cases           INTEGER NOT NULL,
    case_price_paise INTEGER NOT NULL,
    discount_bp     INTEGER NOT NULL DEFAULT 0,
    line_total_paise INTEGER NOT NULL,             -- after discount, before GST
    gst_paise       INTEGER NOT NULL,
    available_cases INTEGER NOT NULL,
    shortage_cases  INTEGER NOT NULL DEFAULT 0,
    shortage_note   TEXT,
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
