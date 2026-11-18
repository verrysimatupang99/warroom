#!/bin/bash
# Jalankan paper bot untuk SEMUA config strategy di strategi/*.yaml.
# Dipicu systemd user timer (webdock) tiap jam. State & ledger di
# /var/lib/warroom/paper-config/. Kegagalan satu config tak menghentikan lain.
set -u
cd /home/admin/warroom
PY=/home/admin/warroom/.venv/bin/python
LOG=/home/admin/live-trading/logs/paper-bot.log
mkdir -p /home/admin/live-trading/logs /var/lib/warroom/paper-config

echo "===== paper-bot-semua $(date -u +%FT%TZ) =====" >> "$LOG"
for cfg in strategi/*.yaml; do
    [ -f "$cfg" ] || continue
    echo "--- config: $cfg ---" >> "$LOG"
    "$PY" ops/paper-bot.py --config "$cfg" >> "$LOG" 2>&1 || echo "GAGAL: $cfg" >> "$LOG"
done
echo "===== selesai =====" >> "$LOG"
