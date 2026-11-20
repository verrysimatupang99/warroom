#!/usr/bin/env bash
# War Room Instabox Keep-Alive & Auto-Wake Watchdog
# Prevents Free-Tier 30m idle auto-pause and auto-wakes boxes if suspended.
set -u

BOXES=(
  "m_agqxjpubmx445g2lsfcvhkw2ee" # box-2aacb3 (Live Cent #452009427)
  "m_agqyovj5ktzhjzc6bekolqsmpe" # mt5-paper-1 (Paper 1 #434446792)
  "m_agqyovj6swircvr5x6zpcxtaxq" # mt5-paper-2 (Paper 2 #464202979)
)

for box in "${BOXES[@]}"; do
  echo "[$(date -Is)] Checking & keeping alive $box..."
  timeout 60 /usr/local/bin/instabox ssh "$box" -- '
    if ! pgrep -f watchdog_daemon.sh >/dev/null 2>&1; then
      setsid bash /data/home/watchdog_daemon.sh >/dev/null 2>&1 < /dev/null &
    fi
    bash /data/home/watchdog_mt5.sh >/dev/null 2>&1 < /dev/null
  ' </dev/null
  rc=$?
  echo "[$(date -Is)] Box $box keepalive exit code: $rc"
done
