#!/usr/bin/env bash
# Pemantau ARM E — IDX (BSJP saja, ARA dimatikan) & Polymarket (arm E band 0,55-0,75).
#
# Tujuan (arahan pemilik 10 Okt): "pantau hasil arm E IDX/Polymarket beberapa hari
# sampai sampel cukup". Skrip ini HANYA MEMBACA & MELAPOR apa adanya; tidak mengubah
# mesin, tidak menambah ambang. Vonis tetap hak pemilik (n>=30, ci=0.90, ci_low>BE).
#
# Keluaran: satu blok teks jujur + baris di log. Dipakai timer harian.
set -uo pipefail
TS=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
LOG=/home/admin/live-trading/logs/arm_e_monitor.log
mkdir -p "$(dirname "$LOG")"
PY=/home/admin/warroom/.venv/bin/python

# File lengan Polymarket hanya bisa dibaca lewat sudo (pemilik poly-pilot, mode 0600).
# Salin HANYA ke tmp lalu dibaca — tetap baca-saja, tak mengubah apa pun di sana.
TMPPOLY=$(mktemp -d)
trap 'rm -rf "$TMPPOLY"' EXIT
for d in /var/lib/poly-paper /var/lib/poly-paper-candidate /var/lib/poly-paper-favorite \
         /var/lib/poly-paper-fade /var/lib/poly-paper-verify /var/lib/poly-paper-cheap; do
  arm=$(basename "$d")
  sudo -n cat "$d/execution-paper-shadow-summary.json" >"$TMPPOLY/$arm.json" 2>/dev/null || true
done

OUT=$("$PY" - "$TMPPOLY" <<'PY'
import json, sqlite3, glob, os, sys
from datetime import datetime, UTC

polydir = sys.argv[1]
print(f"== REKAP ARM E == {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")

# ---------- IDX: BSJP (yg dipertahankan) vs ARA (yg dimatikan) ----------
db = "/home/admin/live-trading/state/idx616_signal_ledger.db"
try:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    print("\n[IDX] setup / tuntas / mean_r  (perhatian: ARA harus BERHENTI nambah)")
    rows = c.execute(
        "SELECT setup, COUNT(*), SUM(net_r) FROM signals WHERE status='CLOSED' GROUP BY setup ORDER BY 1"
    ).fetchall()
    live = c.execute(
        "SELECT setup, COUNT(*) FROM signals WHERE status='CREATED' GROUP BY setup"
    ).fetchall()
    for setup, n, tot in rows:
        mean = (tot / n) if n else 0.0
        print(f"  {setup:12s} tuntas={n:4d}  mean_r={mean:+.4f}  total_r={tot:+.2f}")
    print("  (CREATED, belum tuntas): " + ", ".join(f"{s}={n}" for s, n in live))
    print("  Catatan: pakem butuh n>=30 & ci90_low>BE; ARA sudah dimatikan (tak nambah).")
except Exception as e:
    print(f"\n[IDX] ERR {e}")

# ---------- Polymarket: semua lengan, utamakan arm E ----------
print("\n[POLYMARKET] lengan / band / n / W-L / pnl / WR / BE-WR")
for f in sorted(glob.glob(os.path.join(polydir, "*.json"))) :
    try:
        d = json.load(open(f))
        arm = os.path.basename(f)[:-5].replace("poly-paper-cheap", "arm E").replace("poly-paper-candidate", "arm B") \
              .replace("poly-paper-favorite", "arm D").replace("poly-paper-verify", "arm V") \
              .replace("poly-paper-fade", "arm C").replace("poly-paper", "arm A")
        st = d.get("strategy") or {}
        lo, hi = st.get("entryLo"), st.get("entryHi")
        n = int(d.get("entries") or 0)
        w = int(d.get("wins") or 0); l = int(d.get("losses") or 0)
        pnl = d.get("pnl")
        wr = (100.0 * w / n) if n else None
        # BE-WR ~= harga beli rata-rata band (pasar biner adil; rumus sudah dipakai UI)
        bewr = (100.0 * (lo + hi) / 2) if (lo is not None and hi is not None) else None
        tag = ""
        if n and wr is not None and bewr is not None:
            tag = "LOLOS" if wr > bewr else "BELUM"
        wr_s = f"{wr:5.1f}%" if wr is not None else "  -  "
        be_s = f"{bewr:5.1f}%" if bewr is not None else "  -  "
        print(f"  {arm:14s} band=[{lo},{hi}] n={n:4d} W/L={w}/{l} pnl={pnl} WR={wr_s} BE={be_s} {tag}")
    except Exception as e:
        print(f"  ERR {f}: {e}")
print("  Arm E = band 0,55-0,75 (BARU 10 Okt). Sampel masih kecil -> jangan divonis dulu.")

# ---------- FOREX (pengukur baru) ----------
try:
    import sys
    sys.path.insert(0, "/home/admin/warroom/packages/live-trading/src")
    from pathlib import Path
    from live_trading.pasar import _akurasi_forex
    ak = _akurasi_forex(Path("/home/admin/live-trading/state"))
    print("\n[FOREX] setup / n / WR / mean_r / tingkat")
    for nama, s in (ak.get("per_setup") or {}).items():
        print(f"  {nama}: n={s.get('n')} hari={s.get('n_hari')} WR={s.get('winrate_pct')}% "
              f"meanR={s.get('mean_r')} totalR={s.get('total_r')} tingkat={s.get('tingkat')}")
except Exception as e:
    print(f"\n[FOREX] ERR {e}")
PY
)
echo "$OUT"
echo "---" >> "$LOG"
echo "[$TS]" >> "$LOG"
echo "$OUT" >> "$LOG"
