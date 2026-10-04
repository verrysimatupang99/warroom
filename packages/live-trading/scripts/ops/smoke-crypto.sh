#!/bin/bash
cd /home/admin/live-trading/crypto/scripts

echo "=== 1. reachability sumber data dari Webdock ==="
for u in "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT" \
         "https://contract.mexc.com/api/v1/contract/ticker?symbol=BTC_USDT" \
         "https://api.alternative.me/fng/?limit=1" \
         "https://api.coingecko.com/api/v3/global"; do
  printf "  %-62s " "$(echo $u | cut -c1-62)"
  curl -s -o /tmp/rc.json -w "HTTP %{http_code} (%{time_total}s)\n" -m 15 "$u"
done

echo; echo "=== 2. smoke test: crypto_signal_collect.py ==="
timeout 240 python3 crypto_signal_collect.py > /tmp/sig_out.txt 2>/tmp/sig_err.txt
echo "exit: $?"
echo "--- stderr (10 baris) ---"; tail -10 /tmp/sig_err.txt
echo "--- stdout: $(( $(wc -l < /tmp/sig_out.txt) )) baris, 35 pertama ---"
head -35 /tmp/sig_out.txt
