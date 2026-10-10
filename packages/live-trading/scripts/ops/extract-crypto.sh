#!/bin/bash
# Ekstraksi crypto pipeline Tencent -> Webdock
# ATURAN: crypto_auto_exec.py (jalur order milik kawan) TIDAK disalin sebagai modul aktif.
set -u
KEY=/etc/poly-pilot/backup_ed25519
SRC=/home/ubuntu/.hermes/scripts
DST=/home/admin/live-trading/crypto

mkdir -p "$DST/scripts" "$DST/state" "$DST/journal" "$DST/reference"

FILES="crypto_signal_collect.py crypto_pipeline_collect.py crypto_watch_eval.py crypto_equity.py \
crypto_dashboard.py crypto_signal_format.py crypto_signal_journal.py crypto_orderflow_collect.py \
crypto_outlook_chart.py crypto_outlook_chart_v2.py crypto_outlook_collect.py whale_scan.py"

echo "=== 1. Copy script inti ==="
for f in $FILES; do
  sudo scp -q -i "$KEY" "ubuntu@43.155.219.37:$SRC/$f" "$DST/scripts/" && echo "  ok  $f" || echo "  GAGAL $f"
done

echo; echo "=== 2. Copy state & journal (lanjutin histori) ==="
sudo scp -q -i "$KEY" ubuntu@43.155.219.37:/home/ubuntu/.hermes/state/crypto_equity.jsonl "$DST/state/" && echo "  ok  crypto_equity.jsonl (ledger)"
sudo scp -q -i "$KEY" ubuntu@43.155.219.37:/home/ubuntu/.hermes/scripts/crypto-watchlist.json "$DST/state/" 2>/dev/null && echo "  ok  crypto-watchlist.json"
sudo scp -q -i "$KEY" ubuntu@43.155.219.37:/home/ubuntu/.hermes/crypto-journal/crypto_journal.xlsx "$DST/journal/" 2>/dev/null && echo "  ok  crypto_journal.xlsx"

echo; echo "=== 3. Reference (NON-AKTIF, tanpa klien privat) ==="
sudo scp -q -i "$KEY" "ubuntu@43.155.219.37:$SRC/crypto_auto_exec.py" "$DST/reference/crypto_auto_exec.py.REFERENCE" && echo "  ok  crypto_auto_exec.py (reference only)"

sudo chown -R admin:admin "$DST"
echo; echo "=== HASIL ==="
ls -la "$DST/scripts/" | awk '{print $5, $9}' | tail -15
echo "--- state ---"; ls -la "$DST/state/" | awk '{print $5, $9}' | tail -5
echo "--- reference ---"; ls -la "$DST/reference/" | awk '{print $5, $9}' | tail -3
echo; echo "=== cek tidak ada kredensial terbawa ==="
grep -rl -i -E "okx_client|mexc_client|api_key|secret" "$DST/scripts/" 2>/dev/null | head -5 || echo "  bersih: tidak ada referensi kredensial di scripts/"
