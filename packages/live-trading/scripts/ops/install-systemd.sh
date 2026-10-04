#!/bin/bash
# Pasang unit systemd untuk dashboard + snapshot timer.
set -e
SRC=/home/admin/live-trading/scripts/systemd

echo "=== 1. pasang unit ==="
sudo cp "$SRC/live-trading-dashboard.service" "$SRC/live-trading-snapshot.service" "$SRC/live-trading-snapshot.timer" /etc/systemd/system/
sudo systemctl daemon-reload

echo "=== 2. nyalakan ==="
sudo systemctl enable --now live-trading-dashboard.service 2>&1 | tail -2
sudo systemctl enable --now live-trading-snapshot.timer 2>&1 | tail -2

echo "=== 3. status ==="
systemctl is-active live-trading-dashboard.service
systemctl is-active live-trading-snapshot.timer
systemctl list-timers live-trading-snapshot.timer --no-pager 2>/dev/null | head -3

echo "=== 4. cek dashboard lewat systemd ==="
sleep 6
curl -s -o /tmp/d3.html -w "  HTTP %{http_code} (%{size_download} byte)\n" -m 60 http://127.0.0.1:8799/
grep -oE "\+3\.844R" /tmp/d3.html | head -1

echo "=== 5. jalankan snapshot sekali lewat systemd (bukti timer bisa) ==="
sudo systemctl start live-trading-snapshot.service && echo "  snapshot service: selesai tanpa error"
journalctl -u live-trading-snapshot.service -n 5 --no-pager 2>/dev/null | tail -5
