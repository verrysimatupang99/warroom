#!/bin/bash
set -u
KEY=/etc/poly-pilot/backup_ed25519
DST=/home/admin/live-trading/crypto

echo "=== copy watchlist (lokasinya di ~/.hermes, bukan scripts/) ==="
sudo scp -q -i "$KEY" ubuntu@43.155.219.37:/home/ubuntu/.hermes/crypto-watchlist.json "$DST/state/" \
  && echo "  ok crypto-watchlist.json" || echo "  GAGAL"

echo "=== versi terbaru watchlist (kalau ada yang lebih baru) ==="
sudo ssh -i "$KEY" -o BatchMode=yes ubuntu@43.155.219.37 \
  'ls -la /home/ubuntu/.hermes/crypto-watchlist.json; wc -l /home/ubuntu/.hermes/crypto-watchlist.json'

sudo chown admin:admin "$DST/state/"* 2>/dev/null
echo; echo "=== isi singkat watchlist ==="
python3 -c "
import json
d=json.load(open('/home/admin/live-trading/crypto/state/crypto-watchlist.json'))
if isinstance(d,dict):
    print('keys:', list(d.keys())[:8])
    for k,v in list(d.items())[:6]:
        print(f'  {k}:', str(v)[:80])
else:
    print('jumlah entri:', len(d)); print(str(d[:3])[:300])
" 2>&1 | head -15
