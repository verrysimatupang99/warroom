#!/usr/bin/env bash
# Runner mesin IDX 616 versi lokal War Room.
# Pakai: run_idx616.sh <ara|bsjp|grader|drift>
# Semua output -> state/log; TIDAK menyentuh Tencent.
set -uo pipefail
ROOT=/home/admin/live-trading
SCRIPTS=/home/admin/warroom/packages/live-trading/idx616/scripts
PY=/home/admin/warroom/.venv/bin/python
LOG="$ROOT/logs/idx616.log"
mkdir -p "$ROOT/logs"
cd "$SCRIPTS" || exit 1
ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
case "${1:-}" in
  ara)
    out=$(timeout 180 "$PY" idx_ara_collect.py 2>&1); rc=$?
    [ -n "$out" ] && echo "[$(ts)] ara rc=$rc :: $out" >> "$LOG"
    ;;
  bsjp)
    out=$(timeout 180 "$PY" idx_bsjp_collect.py --top 5 2>&1); rc=$?
    [ -n "$out" ] && echo "[$(ts)] bsjp rc=$rc :: $out" >> "$LOG"
    ;;
  grader)
    out=$(timeout 300 "$PY" idx616_forward_grader_v3.py 2>&1); rc=$?
    echo "[$(ts)] grader rc=$rc :: $out" >> "$LOG"
    ;;
  drift)
    out=$(timeout 120 "$PY" idx616_drift.py 2>&1); rc=$?
    echo "[$(ts)] drift rc=$rc :: $out" >> "$LOG"
    ;;
  *) echo "pakai: $0 <ara|bsjp|grader|drift>" >&2; exit 2 ;;
esac
exit 0
