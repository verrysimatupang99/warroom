#!/usr/bin/env bash
# Penyegar jurnal FOREX (War Room, lokal).
#
# MASALAH: mesin ukur FOREX (`pasar.py:_akurasi_forex`) sudah jalan, tapi sumbernya
# `state/forex_journal.json` BEKU sejak impor 6 Okt — sementara jurnal Tencent terus
# bertambah (bukti 10 Okt: 2 trade XAUUSD + 1 NAS100 baru, belum masuk lokal).
# Jadi "pengukur" yang benar bukan mesin baru: cukup TARIK jurnal Tencent (baca-saja),
# tulis ke salinan lokal, lalu mesin yang sudah ada menghitung ulang pakem.
#
# SIFAT: baca-saja dari Tencent; menulis HANYA salinan lokal state/forex_journal.json.
# TIDAK menyentuh Tencent, TIDAK menyentuh gerbang live. Reversibel (file lokal).
set -uo pipefail
TS=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
STATE=/home/admin/live-trading/state
LOKAL="$STATE/forex_journal.json"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
LOG=/home/admin/live-trading/logs/forex_refresh.log
mkdir -p "$(dirname "$LOG")"

log(){ echo "[$TS] $*" >> "$LOG"; }

SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 -i /etc/warroom/tencent_ed25519 ubuntu@43.155.219.37"
JAR="~/.hermes/trading-journal"

# 1. tarik mentah (baca-saja)
if ! $SSH "cat $JAR/xauusd_journal.json" >"$TMP/xau.json" 2>"$TMP/err"; then
  log "GAGAL tarik xauusd: $(head -c 200 "$TMP/err" | tr '\n' ' ')"; exit 1
fi
if ! $SSH "cat $JAR/multipair_journal.json" >"$TMP/mp.json" 2>>"$TMP/err"; then
  log "GAGAL tarik multipair: $(head -c 200 "$TMP/err" | tr '\n' ' ')"; exit 1
fi

# 2. rakit ke bentuk lokal (xauusd objek {trades,meta}, multipair list) + sidik jari
/home/admin/warroom/.venv/bin/python - "$TMP/xau.json" "$TMP/mp.json" "$LOKAL" <<'PY' >>"$LOG" 2>&1
import hashlib, json, sys, datetime, pathlib
xau_p, mp_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3]
xau = json.load(open(xau_p))
mp = json.load(open(mp_p))
# multipair Tencent bisa list atau dict; normalkan ke list (bentuk lokal)
if isinstance(mp, dict):
    mp = mp.get('trades') or mp.get('multipair') or []
# xauusd Tencent bisa dict{trades,meta} atau list; normalkan ke dict
if isinstance(xau, list):
    xau = {'trades': xau, 'meta': {}}
sidik = hashlib.sha256((json.dumps(xau, sort_keys=True) + json.dumps(mp, sort_keys=True)).encode()).hexdigest()

lama = {}
try:
    lama = json.load(open(out_p))
except Exception:
    pass
if (lama.get('impor') or {}).get('sha256') == sidik:
    print(f"[{datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}] tidak berubah (sha {sidik[:12]}) xau={len(xau.get('trades',[]))} mp={len(mp)}")
    sys.exit(0)

baru = {
    'xauusd': xau,
    'multipair': mp,
    'impor': {
        'sumber': 'tencent:43.155.219.37 ~/.hermes/trading-journal/{xauusd_journal,multipair_journal}.json',
        'sha256': sidik,
        'diimpor': datetime.datetime.now(datetime.UTC).isoformat(),
        'catatan': 'Disalin APA ADANYA dari Tencent oleh forex-refresh.timer (baca-saja). '
                   'Tidak ada angka yang diubah; mesin pasar.py yang menghitung pakem.',
    },
}
pathlib.Path(out_p).write_text(json.dumps(baru, indent=2, ensure_ascii=False))
n_x = len(xau.get('trades', [])); n_m = len(mp)
lama_x = len((lama.get('xauusd') or {}).get('trades') or []); lama_m = len(lama.get('multipair') or [])
print(f"[{datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}] SEGAR sha={sidik[:12]} "
      f"xau {lama_x}->{n_x} mp {lama_m}->{n_m}")
PY
rc=$?
[ $rc -eq 0 ] && log "selesai rc=0" || log "selesai rc=$rc"
exit $rc
