#!/bin/bash
# Verifikasi Arjum API key dari Webdock (nilai key tidak pernah ditampilkan)
KEY=$(cat /home/admin/live-trading/secrets/arjum_api_key)
U="https://stock.arjum.com"

echo "=== /api/health ==="
curl -s -m 20 -o /tmp/arj_health.json -D /tmp/arj_h.txt \
  -H "X-API-Key: $KEY" -H "User-Agent: hermes-idx/1.0" "$U/api/health" \
  -w "HTTP %{http_code} (%{time_total}s)\n"
head -c 300 /tmp/arj_health.json; echo; echo

echo "=== /api/screener/latest?limit=3 ==="
curl -s -m 25 -o /tmp/arj_scr.json -D /tmp/arj_s.txt \
  -H "X-API-Key: $KEY" -H "User-Agent: hermes-idx/1.0" "$U/api/screener/latest?limit=3" \
  -w "HTTP %{http_code} (%{time_total}s)\n"
head -c 500 /tmp/arj_scr.json; echo; echo

echo "=== kuota (dari header) ==="
for f in /tmp/arj_h.txt /tmp/arj_s.txt; do
  grep -i "ratelimit" "$f" 2>/dev/null | head -3
done
