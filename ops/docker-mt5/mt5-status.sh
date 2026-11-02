#!/usr/bin/env bash
# mt5-status — status cepat MT5 di container warroom-mt5-node (read-only).
# TIDAK mengirim order, TIDAK menyentuh akun live. Pemantauan saja.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CFG="$DIR/config/.wine/drive_c/Program Files/MetaTrader 5"

echo "== Container =="
docker ps --filter name=warroom-mt5-node --format '{{.Names}}: {{.Status}}' || true

echo; echo "== terminal64.exe =="
docker exec warroom-mt5-node sh -c 'pgrep -f terminal64.exe >/dev/null && echo "RUNNING (pid $(pgrep -f terminal64.exe | head -1))" || echo "TIDAK JALAN"' 2>/dev/null || echo "container tidak jalan"

echo; echo "== Akun tersimpan (dari Bases/, bukan accounts.dat) =="
# accounts.dat terenkripsi machine-key; sumber akun yang terbaca: folder Bases/<Server>/symbols/symbols-<login>.dat
docker exec -i warroom-mt5-node python3 - <<'PY'
import os, datetime
b = "/config/.wine/drive_c/Program Files/MetaTrader 5/Bases"
seen = {}
for d in sorted(os.listdir(b)):
    p = os.path.join(b, d, "symbols")
    if os.path.isdir(p):
        for f in os.listdir(p):
            if f.startswith("symbols-") and f.endswith(".dat"):
                login = f[len("symbols-"):-4]
                ts = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(p, f)), datetime.UTC)
                seen.setdefault((d, login), ts)
for (srv, login), ts in sorted(seen.items(), key=lambda x: -x[1].timestamp()):
    label = "LIVE" if "Real" in srv else "demo"
    print(f"  login {login}  server {srv}  [{label}]  terakhir: {ts:%Y-%m-%d %H:%M UTC}")
PY

echo; echo "== Log terminal terakhir (login/connect) =="
docker exec -i warroom-mt5-node python3 - <<'PY'
import glob, os
logs = sorted(glob.glob("/config/.wine/drive_c/Program Files/MetaTrader 5/logs/*.log"), key=os.path.getmtime)
if logs:
    d = open(logs[-1], "rb").read().decode("utf-16", "ignore")
    hits = [l for l in d.splitlines() if any(k in l.lower() for k in ("login", "authoriz", "connect", "network"))]
    print("\n".join(hits[-8:]) or "  (tidak ada baris login/connect)")
else:
    print("  (belum ada log)")
PY
echo; echo "Web UI MT5: http://127.0.0.1:3300 (ssh -L 3300:127.0.0.1:3300 <host>)"
