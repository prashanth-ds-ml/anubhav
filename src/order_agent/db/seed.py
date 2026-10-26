"""Deterministic, fully fictional seed data for the wholesale simulator.

All brands, customers, cities' businesses and prices are invented. Money is in paise.
Golden-path fixture: Ravi Traders (gold) asks for 12 cases of Godavari Gold Sunflower Oil 1 L;
8 cases are available across warehouses, so 4 are short; a restock lands 2026-11-02.
"""

import json
import sqlite3


def rs(rupees: float) -> int:
    return round(rupees * 100)


# Telugu-script and Roman-Telugu names per product type, used to build aliases.
TYPE_ALIASES = {
    "sunflower oil": ["సన్‌ఫ్లవర్ నూనె", "sunflower nune", "sunflower oil"],
    "groundnut oil": ["వేరుశనగ నూనె", "verusenaga nune", "palli nune", "groundnut oil"],
    "palmolein oil": ["పామాయిల్", "pamoil", "palm oil"],
    "sona masoori rice": ["సోనా మసూరి బియ్యం", "sona masoori biyyam", "sona biyyam"],
    "bpt rice": ["బీపీటీ బియ్యం", "bpt biyyam"],
    "basmati rice": ["బాస్మతి బియ్యం", "basmati biyyam"],
    "toor dal": ["కంది పప్పు", "kandi pappu", "toor dal"],
    "moong dal": ["పెసర పప్పు", "pesara pappu", "moong dal"],
    "chana dal": ["శనగ పప్పు", "senaga pappu", "chana dal"],
    "urad dal": ["మినప పప్పు", "minapa pappu", "urad dal"],
    "sugar": ["చక్కెర", "chakkera", "panchadara"],
    "wheat atta": ["గోధుమ పిండి", "godhuma pindi", "atta"],
    "bombay rava": ["బొంబాయి రవ్వ", "bombay ravva", "upma ravva"],
    "salt": ["ఉప్పు", "uppu"],
    "jaggery": ["బెల్లం", "bellam"],
    "tamarind": ["చింతపండు", "chintapandu"],
    "poha": ["అటుకులు", "atukulu"],
    "turmeric powder": ["పసుపు", "pasupu"],
    "chilli powder": ["కారం", "karam", "kaaram podi"],
    "coriander powder": ["ధనియాల పొడి", "dhaniyala podi"],
    "sambar powder": ["సాంబార్ పొడి", "sambar podi"],
    "tea powder": ["టీ పొడి", "tea podi", "chai podi"],
    "filter coffee": ["కాఫీ పొడి", "coffee podi"],
    "glucose biscuits": ["గ్లూకోజ్ బిస్కెట్లు", "glucose biscuits"],
    "cream biscuits": ["క్రీమ్ బిస్కెట్లు", "cream biscuits"],
    "instant noodles": ["నూడుల్స్", "noodles"],
    "bath soap": ["సబ్బు", "sabbu", "snanam sabbu"],
    "detergent powder": ["బట్టల పొడి", "battala podi", "washing powder"],
    "dishwash liquid": ["గిన్నెల లిక్విడ్", "ginnela liquid", "dishwash"],
    "toothpaste": ["టూత్‌పేస్ట్", "toothpaste", "pasta"],
    "floor cleaner": ["ఫ్లోర్ క్లీనర్", "phenyl", "floor cleaner"],
    "ghee": ["నెయ్యి", "neyyi", "ghee"],
    "milk powder": ["పాల పొడి", "paala podi", "milk powder"],
}

# sku, brand, type, pack label, units per case, GST bp, case price (Rs)
PRODUCTS = [
    ("GG-SUN-1L", "Godavari Gold", "sunflower oil", "1 L", 12, 500, 1740),
    ("GG-SUN-5L", "Godavari Gold", "sunflower oil", "5 L", 4, 500, 2800),
    ("DP-SUN-1L", "Deccan Pure", "sunflower oil", "1 L", 12, 500, 1680),
    ("GG-GNUT-1L", "Godavari Gold", "groundnut oil", "1 L", 12, 500, 2160),
    ("KF-PALM-1L", "Krishna Fresh", "palmolein oil", "1 L", 12, 500, 1320),
    ("KS-SONA-25", "Konaseema", "sona masoori rice", "25 kg", 1, 500, 1450),
    ("KS-SONA-10", "Konaseema", "sona masoori rice", "10 kg", 2, 500, 1220),
    ("PF-BPT-25", "Palnadu Farms", "bpt rice", "25 kg", 1, 500, 1350),
    ("DP-BASM-5", "Deccan Pure", "basmati rice", "5 kg", 4, 500, 2400),
    ("PF-TOOR-1", "Palnadu Farms", "toor dal", "1 kg", 20, 500, 3200),
    ("PF-MOONG-1", "Palnadu Farms", "moong dal", "1 kg", 20, 500, 2600),
    ("PF-CHANA-1", "Palnadu Farms", "chana dal", "1 kg", 20, 500, 1900),
    ("PF-URAD-1", "Palnadu Farms", "urad dal", "1 kg", 20, 500, 2800),
    ("KF-SUGAR-1", "Krishna Fresh", "sugar", "1 kg", 30, 500, 1350),
    ("KF-ATTA-10", "Krishna Fresh", "wheat atta", "10 kg", 2, 500, 840),
    ("KF-RAVA-1", "Krishna Fresh", "bombay rava", "1 kg", 25, 500, 1125),
    ("KF-SALT-1", "Krishna Fresh", "salt", "1 kg", 50, 0, 1000),
    ("PF-JAG-1", "Palnadu Farms", "jaggery", "1 kg", 20, 500, 1300),
    ("PF-TAM-1", "Palnadu Farms", "tamarind", "1 kg", 20, 500, 3400),
    ("KF-POHA-1", "Krishna Fresh", "poha", "1 kg", 25, 500, 1375),
    ("KK-TURM-200", "Kakatiya", "turmeric powder", "200 g", 50, 500, 2250),
    ("KK-CHILLI-500", "Kakatiya", "chilli powder", "500 g", 24, 500, 3360),
    ("KK-CHILLI-1K", "Kakatiya", "chilli powder", "1 kg", 12, 500, 3240),
    ("KK-CORI-200", "Kakatiya", "coriander powder", "200 g", 50, 500, 1750),
    ("KK-SAMBAR-100", "Kakatiya", "sambar powder", "100 g", 100, 500, 4500),
    ("DP-TEA-250", "Deccan Pure", "tea powder", "250 g", 40, 500, 4400),
    ("DP-TEA-1K", "Deccan Pure", "tea powder", "1 kg", 12, 500, 5040),
    ("DP-COFFEE-200", "Deccan Pure", "filter coffee", "200 g", 40, 500, 5600),
    ("GG-BISC-GLU", "Godavari Gold", "glucose biscuits", "100 g", 120, 1800, 1200),
    ("GG-BISC-CRM", "Godavari Gold", "cream biscuits", "75 g", 96, 1800, 1920),
    ("KF-NOOD-70", "Krishna Fresh", "instant noodles", "70 g", 96, 1800, 1248),
    ("NN-SOAP-100", "Nellore Naturals", "bath soap", "100 g", 144, 1800, 4320),
    ("NN-DET-1K", "Nellore Naturals", "detergent powder", "1 kg", 20, 1800, 1800),
    ("NN-DET-500", "Nellore Naturals", "detergent powder", "500 g", 40, 1800, 1880),
    ("NN-DISH-500", "Nellore Naturals", "dishwash liquid", "500 ml", 24, 1800, 2400),
    ("NN-TOOTH-100", "Nellore Naturals", "toothpaste", "100 g", 72, 1800, 4320),
    ("NN-FLOOR-1L", "Nellore Naturals", "floor cleaner", "1 L", 12, 1800, 1080),
    ("KS-GHEE-1L", "Konaseema", "ghee", "1 L", 12, 1200, 7800),
    ("KS-GHEE-500", "Konaseema", "ghee", "500 ml", 24, 1200, 8160),
    ("DP-MILK-500", "Deccan Pure", "milk powder", "500 g", 24, 500, 6240),
]

CATEGORY = {
    "oil": "edible oil", "rice": "rice", "dal": "pulses", "powder": "spices",
}

# id, name, Telugu-script / Roman aliases, city, tier, active, credit_status, terms, limit (Rs), outstanding (Rs)
CUSTOMERS = [
    ("C-001", "Ravi Traders", ["రవి ట్రేడర్స్", "ravi shop", "ravi traders"], "Vijayawada", "gold", 1, "ok", "net15", 300000, 42000),
    ("C-002", "Lakshmi Kirana", ["లక్ష్మి కిరాణా", "lakshmi kirana", "lakshmi shop"], "Guntur", "silver", 1, "ok", "net7", 100000, 18000),
    ("C-003", "Sri Venkateswara Stores", ["శ్రీ వెంకటేశ్వర స్టోర్స్", "venkateswara stores", "SV stores"], "Vijayawada", "gold", 1, "ok", "net15", 250000, 0),
    ("C-004", "Ganesh General Stores", ["గణేష్ జనరల్ స్టోర్స్", "ganesh stores"], "Tenali", "bronze", 1, "ok", "cash", 0, 0),
    ("C-005", "Padma Provisions", ["పద్మ ప్రొవిజన్స్", "padma provisions"], "Guntur", "silver", 1, "watch", "net7", 80000, 71000),
    ("C-006", "Srinivasa Agencies", ["శ్రీనివాస ఏజెన్సీస్", "srinivasa agencies"], "Eluru", "gold", 1, "hold", "net15", 200000, 215000),
    ("C-007", "Anjali Supermart", ["అంజలి సూపర్‌మార్ట్", "anjali mart"], "Vijayawada", "silver", 1, "ok", "net7", 120000, 9000),
    ("C-008", "Balaji Wholesale", ["బాలాజీ హోల్‌సేల్", "balaji wholesale"], "Machilipatnam", "gold", 1, "ok", "net30", 500000, 150000),
    ("C-009", "Durga Traders", ["దుర్గ ట్రేడర్స్", "durga traders"], "Vijayawada", "bronze", 1, "ok", "cash", 0, 0),
    ("C-010", "Kamala Stores", ["కమల స్టోర్స్", "kamala stores"], "Tenali", "silver", 0, "ok", "net7", 60000, 0),
    ("C-011", "Sai Ram Kirana", ["సాయి రామ్ కిరాణా", "sairam kirana", "sai ram shop"], "Guntur", "bronze", 1, "ok", "cash", 0, 0),
    ("C-012", "Vijaya Mart", ["విజయ మార్ట్", "vijaya mart"], "Ongole", "silver", 1, "ok", "net7", 90000, 12000),
    ("C-013", "Raju & Sons", ["రాజు అండ్ సన్స్", "raju sons", "raju and sons"], "Vijayawada", "gold", 1, "ok", "net15", 350000, 60000),
    ("C-014", "Annapurna Stores", ["అన్నపూర్ణ స్టోర్స్", "annapurna stores"], "Eluru", "bronze", 1, "watch", "cash", 0, 0),
    ("C-015", "Ravi Kumar Provisions", ["రవి కుమార్ ప్రొవిజన్స్", "ravi kumar shop"], "Guntur", "silver", 1, "ok", "net7", 70000, 5000),
]

WAREHOUSES = [("WH-VJA", "Vijayawada Main", "Vijayawada"), ("WH-GNT", "Guntur Depot", "Guntur")]

# Explicit stock for scenario-relevant SKUs: sku -> {warehouse: (on_hand, reserved)}
STOCK_OVERRIDES = {
    "GG-SUN-1L": {"WH-VJA": (6, 0), "WH-GNT": (3, 1)},   # available 8 -> golden-path shortfall of 4
    "DP-SUN-1L": {"WH-VJA": (30, 0), "WH-GNT": (10, 0)},  # substitute with plenty of stock
    "DP-BASM-5": {"WH-VJA": (0, 0), "WH-GNT": (0, 0)},    # out of stock, restock pending
    "KS-GHEE-500": {"WH-VJA": (0, 0), "WH-GNT": (0, 0)},  # out of stock, no restock
}

RESTOCKS = [
    ("GG-SUN-1L", "WH-VJA", "2026-11-02", 40),
    ("DP-BASM-5", "WH-VJA", "2026-11-05", 20),
    ("PF-TOOR-1", "WH-GNT", "2026-11-03", 30),
]

SUBSTITUTES = [
    ("GG-SUN-1L", "DP-SUN-1L"), ("DP-SUN-1L", "GG-SUN-1L"),
    ("KS-SONA-25", "PF-BPT-25"), ("PF-BPT-25", "KS-SONA-25"),
    ("KK-CHILLI-1K", "KK-CHILLI-500"), ("DP-TEA-1K", "DP-TEA-250"),
    ("NN-DET-1K", "NN-DET-500"), ("KS-GHEE-500", "KS-GHEE-1L"),
]

BULK_PRICES = [
    ("GG-SUN-1L", 20, 1700), ("KS-SONA-25", 50, 1400), ("KF-SUGAR-1", 20, 1300), ("PF-TOOR-1", 15, 3100),
]

CUSTOMER_PRICES = [
    ("C-001", "KS-SONA-25", 1420), ("C-008", "GG-SUN-1L", 1690), ("C-013", "PF-TOOR-1", 3120),
]

DISCOUNT_RULES = [("gold", 500, 10), ("silver", 200, 10), ("bronze", 0, 0)]

POLICIES = {
    "pricing.precedence": "Use the customer-specific price if one exists; otherwise the bulk price for the "
    "highest min_cases threshold met; otherwise the standard price.",
    "discount.eligibility": "Tier discount applies when the line meets the tier's min_cases, the customer is "
    "active and credit_status is not 'hold'. It applies to standard and bulk prices, not to "
    "customer-specific negotiated prices.",
    "credit.hold": "Customers on credit hold may receive draft quotes, but no discount and the quote must "
    "carry a credit-hold warning.",
    "quote.shortage": "Quote the full requested quantity; record available and shortage cases per line with a "
    "note. Never reserve or allocate stock from a quote.",
    "quote.validity_days": "7",
    "returns": "Unopened cases may be returned within 7 days of delivery with invoice.",
    "orders.confirmation": "Orders are confirmed only by a human operator in the ERP. The assistant may only "
    "create drafts.",
}

# id, customer, status, created, lines [(sku, cases, case price Rs)]
ORDERS = [
    ("O-1001", "C-001", "delivered", "2026-10-05", [("GG-SUN-1L", 10, 1740), ("KS-SONA-25", 20, 1420)]),
    ("O-1002", "C-001", "dispatched", "2026-10-22", [("PF-TOOR-1", 5, 3200)]),
    ("O-1003", "C-003", "delivered", "2026-10-12", [("KF-SUGAR-1", 15, 1350), ("DP-TEA-250", 4, 4400)]),
    ("O-1004", "C-008", "confirmed", "2026-10-25", [("GG-SUN-1L", 25, 1690)]),
    ("O-1005", "C-002", "delivered", "2026-10-15", [("NN-DET-1K", 6, 1800)]),
]


def product_rows():
    for sku, brand, ptype, pack, upc, gst, price in PRODUCTS:
        name = f"{brand} {ptype.title()} {pack}"
        category = next((v for k, v in CATEGORY.items() if k in ptype), "grocery")
        aliases = TYPE_ALIASES[ptype] + [f"{brand} {ptype}", f"{ptype} {pack}".lower()]
        yield sku, name, brand, category, json.dumps(aliases, ensure_ascii=False), "piece", pack, upc, gst, rs(price)


def seed(conn: sqlite3.Connection) -> None:
    for sku, name, brand, cat, aliases, unit, pack, upc, gst, _ in product_rows():
        conn.execute(
            "INSERT INTO products (sku, name, brand, category, aliases, base_unit, pack_size, units_per_case, gst_rate_bp)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (sku, name, brand, cat, aliases, unit, pack, upc, gst),
        )
    conn.executemany("INSERT INTO prices VALUES (?,?)", [(r[0], r[9]) for r in product_rows()])

    for cid, name, aliases, city, tier, active, credit, terms, limit, outstanding in CUSTOMERS:
        conn.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, name, json.dumps(aliases, ensure_ascii=False), city, tier, active, credit, terms, rs(limit), rs(outstanding)),
        )

    conn.executemany("INSERT INTO warehouses VALUES (?,?,?)", WAREHOUSES)
    for i, (sku, *_rest) in enumerate(PRODUCTS):
        for j, (wh, *_w) in enumerate(WAREHOUSES):
            on_hand, reserved = STOCK_OVERRIDES.get(sku, {}).get(wh, ((i * 7 + j * 11) % 45 + 12, (i + j) % 3))
            conn.execute("INSERT INTO inventory VALUES (?,?,?,?)", (sku, wh, on_hand, reserved))

    conn.executemany("INSERT INTO restocks VALUES (?,?,?,?)", RESTOCKS)
    conn.executemany("INSERT INTO substitutes VALUES (?,?)", SUBSTITUTES)
    conn.executemany("INSERT INTO bulk_prices VALUES (?,?,?)", [(s, m, rs(p)) for s, m, p in BULK_PRICES])
    conn.executemany("INSERT INTO customer_prices VALUES (?,?,?)", [(c, s, rs(p)) for c, s, p in CUSTOMER_PRICES])
    conn.executemany("INSERT INTO discount_rules VALUES (?,?,?)", DISCOUNT_RULES)
    conn.executemany("INSERT INTO policies VALUES (?,?)", POLICIES.items())

    for oid, cid, status, created, lines in ORDERS:
        total = sum(rs(p) * n for _, n, p in lines)
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?)", (oid, cid, status, created, total))
        for n, (sku, cases, price) in enumerate(lines, 1):
            conn.execute("INSERT INTO order_lines VALUES (?,?,?,?,?)", (oid, n, sku, cases, rs(price)))
