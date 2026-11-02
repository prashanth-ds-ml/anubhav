#!/usr/bin/env bash
# D-054 overnight batch (2026-11-03): three pre-registered experiments, one after another, on the Meta API only.
# The Baseten key is blanked, so a Baseten call fails instead of spending. Each experiment stops at its own cap
# (total $63) and a failure or a cap does not stop the next one. Resume a capped run with its own --resume STAMP.
#   bash scripts/overnight_d054.sh
set -u
cd "$(dirname "$0")/.."
export baseten_api_key=
LOG="artifacts/benchmark/overnight_d054_$(date +%Y%m%d_%H%M%S).log"

run() {
  local name=$1; shift
  echo "=== $name start $(date '+%Y-%m-%d %H:%M:%S')" >>"$LOG"
  uv run python "$@" >>"$LOG" 2>&1
  echo "=== $name exit $? $(date '+%Y-%m-%d %H:%M:%S')" >>"$LOG"
}

run EXP-015 scripts/exp011r_benchmark.py --model spark --tag exp015 --budget 22
run EXP-014 scripts/exp014_curve.py --model spark --budget 35
run EXP-016 scripts/exp012b_new_tools.py --model spark --tag exp016 --budget 6
echo "=== batch done $(date '+%Y-%m-%d %H:%M:%S')" >>"$LOG"
