"""Rebuild data/business.db from datasets/business/*.csv and print table counts.

Usage: uv run python scripts/data/build_db.py
"""

from order_agent import db


def main():
    path = db.reset()
    conn = db.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    for t in tables:
        print(f"{t:18} {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>5}")
    print(f"Built {path}")


if __name__ == "__main__":
    main()
