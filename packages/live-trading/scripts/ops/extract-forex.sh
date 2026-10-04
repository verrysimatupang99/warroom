#!/bin/bash
set -u
KEY=/etc/poly-pilot/backup_ed25519
SRC=/home/ubuntu/.hermes/scripts
DST=/home/admin/live-trading/vendor/forex
mkdir -p "$DST"

for f in xauusd_smc_data.py multi_pair_signal.py multipair_journal.py trade_journal.py plot_outlook.py; do
  sudo scp -q -i "$KEY" "ubuntu@43.155.219.37:$SRC/$f" "$DST/" && echo "  ok $f" || echo "  GAGAL $f"
done
sudo chown -R admin:admin "$DST"
echo; echo "=== URL TradingView yang dipakai script Tencent ==="
grep -n -A4 "scanner.tradingview.com" "$DST/xauusd_smc_data.py" | head -12
