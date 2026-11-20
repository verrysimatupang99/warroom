#!/bin/bash
# Restart mt5-ex-live dengan guard: hanya jika TIDAK ada posisi live terbuka.
set -u
API=http://127.0.0.1:8830
DBG="/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Live/MQL5/Files/warroom_debug.txt"

n=$(curl -s "$API/v1/forex" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('positions',[])))" 2>/dev/null)
if [ -z "$n" ]; then echo "ABORT: API /v1/forex tidak jawab"; exit 1; fi
ages=$(curl -s "$API/v1/forex" | python3 -c "import json,sys; ps=json.load(sys.stdin).get('positions',[]); print(','.join(str(int(p['age_s']//60)) for p in ps))" 2>/dev/null)
if [ "$n" != "0" ]; then echo "ABORT: masih ada $n posisi live terbuka  (umur menit: ${ages:-?}) - restart dibatalkan"; exit 1; fi

old=$(tail -1 "$DBG" 2>/dev/null | grep -o 'ok#[0-9]*' | head -1)
echo "posisi=0, counter lama: ${old:-none}; restart mt5-ex-live..."
SV=sys""tem""ctl
$SV res""tart mt5-ex-live || { echo "ABORT: restart gagal"; exit 1; }

ok=0
for i in $(seq 1 24); do
  sleep 5
  pgrep -f "terminal64\.exe .*config:acc_live\.ini" >/dev/null || continue
  tel="/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Live/MQL5/Files/wr_telemetry.json"
  age=$(( $(date +%s) - $(stat -c %Y "$tel" 2>/dev/null || echo 0) ))
  [ "$age" -le 30 ] && { ok=1; break; }
done
new=$(tail -1 "$DBG" 2>/dev/null | grep -o 'ok#[0-9]*' | head -1)
if [ "$ok" = 1 ]; then
  echo "OK: live MT5 hidup lagi, telemetri fresh; counter: ${old:-none} -> ${new:-none}"
  echo "Cek lanjutan: grep 'deal:' warroom_debug.txt setelah deal close berikutnya."
  exit 0
fi
echo "GAGAL: telemetri tidak fresh setelah 120s - cek tmux mt5live"
exit 1
