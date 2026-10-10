#!/bin/bash
cd /home/admin/live-trading/crypto/scripts

echo "=== crypto_equity.py (statistik dari ledger) ==="
timeout 90 python3 crypto_equity.py 2>&1 | head -25

echo; echo "=== crypto_watch_eval.py (uji degradasi tanpa okx_client) ==="
timeout 90 python3 crypto_watch_eval.py 2>&1 | head -15

echo; echo "=== crypto_dashboard.py (start, cek port, stop) ==="
timeout 25 python3 crypto_dashboard.py > /tmp/dash.log 2>&1 &
sleep 8
printf "  HTTP /crypto -> "; curl -s -o /tmp/dash.html -w "%{http_code} (%{size_download} byte)\n" -m 10 http://127.0.0.1:8771/crypto
head -c 200 /tmp/dash.log
sleep 20
echo "  (dashboard dihentikan)"
