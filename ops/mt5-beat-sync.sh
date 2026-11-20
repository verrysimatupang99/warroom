#!/usr/bin/env bash
# Sentuh mt5_telemetri.beat kalau telemetri MT5 aktif di War Room API (<= 120s) atau nginx access log <= 120s.
set -euo pipefail
BEAT="/home/admin/live-trading/state/mt5_telemetri.beat"
LOG="/var/www/logs/access.log"

if [[ -f /etc/warroom/service_token.env ]]; then
  source /etc/warroom/service_token.env
fi

if curl -fsS --max-time 5 -H "X-Warroom-Token: ${WARROOM_SERVICE_TOKEN:-}" http://127.0.0.1:8800/api/v1/tencent/mt5/accounts 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    accts = d.get("accounts", [])
    live_ok = any(str(a.get("account")) == "452009427" and a.get("connected") and (a.get("seconds_ago") or 999) <= 120 for a in accts)
    any_ok = any(a.get("connected") and (a.get("seconds_ago") or 999) <= 120 for a in accts)
    sys.exit(0 if (live_ok or any_ok) else 1)
except Exception:
    sys.exit(1)
'; then
  mkdir -p "$(dirname "$BEAT")"
  touch "$BEAT"
  exit 0
fi

[[ -r "$LOG" ]] || exit 0
last_line=$(tail -n 500 "$LOG" | grep -E "POST /api/v1/tencent/mt5/(telemetry|deals).* 200 " | tail -n 1 || true)
[[ -n "$last_line" ]] || exit 0
ts_str=$(echo "$last_line" | sed -n "s/.*\[\([^]]*\)\].*/\1/p")
[[ -n "$ts_str" ]] || exit 0
ts_iso=$(echo "$ts_str" | awk '{gsub("/"," ",$1); sub(":"," ",$1); print $1, $2}')
ts_epoch=$(date -d "$ts_iso" +%s 2>/dev/null || echo 0)
now=$(date +%s)
if (( now - ts_epoch <= 120 )); then
  mkdir -p "$(dirname "$BEAT")"
  touch "$BEAT"
fi
