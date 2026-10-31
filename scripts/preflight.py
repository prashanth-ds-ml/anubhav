"""Check everything before recording or going live. Lists models only: no tokens are spent.
  uv run python scripts/preflight.py                 # both models
  uv run python scripts/preflight.py --replay-only   # a host with no keys
"""

import argparse
import sys

from anubhav import preflight


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay-only", action="store_true", help="skip the model keys")
    a = ap.parse_args()
    rows = preflight.run(models=() if a.replay_only else ("spark", "open"))
    for name, ok, detail in rows:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
