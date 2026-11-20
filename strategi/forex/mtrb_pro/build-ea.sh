#!/bin/bash
# deploy-ea.sh — deploy EA MTRB Pro dari repo (subproject War Room) ke terminal MT5 demo.
#
# Apa yang dilakukan:
#   1. Ambil MTRB_Pro.mq5 dari checkout subproject (default: repo v3.08+)
#   2. Bikin MTRB_Fix.mq5 = MTRB_Pro.mq5 + panggilan DashTick() tiap 2 detik di OnTick
#      (tanpa ini dashboard /mtrb/ tidak ter-update: timer Wine tidak andal)
#   3. Copy include MTRB_SMC*.mqh
#   4. Compile headless (MetaEditor64 /compile, harus jalan sebagai pemilik prefix)
#   5. Backup ex5 lama, restart mt5-ex-demo, tunggu status JSON naik ke versi baru
#
# Pakai:
#   sudo bash deploy-ea.sh            # deploy penuh (compile + restart + verifikasi)
#   sudo bash deploy-ea.sh --dry-run  # compile saja, tanpa restart
#
# Rollback: cp /home/admin/backup-mtrb/MTRB_Fix_<versi>.ex5 ke MQL5/Experts/ lalu restart.

set -uo pipefail

SRC=${SRC:-/home/admin/warroom/subprojects/mtrb-pro}
D=${D:-"/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Demo"}
E="$D/MQL5/Experts"
BAKDIR=/home/admin/backup-mtrb
STATUS="/home/admin/.wine-exness/drive_c/users/admin/AppData/Roaming/MetaQuotes/Terminal/Common/Files/MTRB_Pro_status.json"
WINEW=/home/admin/opt/wine-11.22-amd64-wow64/bin/wine
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# ---------- fase compile: wajib sebagai admin (pemilik prefix Wine) ----------
if [ "$(id -u)" -eq 0 ]; then
  log "fase compile sebagai admin"
  su - admin -c "SRC='$SRC' D='$D' bash $0 ${1:-} --phase-compile"
  rc=$?
  [ $rc -ne 0 ] && { log "compile GAGAL (rc=$rc) — tidak ada yang di-restart"; exit $rc; }
else
  :
fi

if [ "${2:-}" = "--phase-compile" ] || [ "$(id -u)" -ne 0 ]; then
  cd "$SRC" || { log "repo tidak ada: $SRC"; exit 1; }
  VER=$(grep -oP '(?<=#property version\s\s\s")[0-9.]+' MTRB_Pro.mq5 | head -1)
  log "sumber: $SRC (versi $VER)"

  python3 - "$SRC/MTRB_Pro.mq5" "$E/MTRB_Fix.mq5" <<'PY' || exit 2
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8", errors="ignore").read()
anchor = "void OnTick()\n  {\n   CheckNewDay();"
inject = ("void OnTick()\n  {\n"
          "   static datetime _dbgLast=0;\n"
          "   if(TimeCurrent()-_dbgLast>=2){ _dbgLast=TimeCurrent(); DashTick(); }\n"
          "   CheckNewDay();")
if s.count(anchor) != 1:
    print(f"GAGAL: anchor OnTick tidak unik (count={s.count(anchor)})")
    sys.exit(2)
open(dst, "w", encoding="utf-8").write(s.replace(anchor, inject))
print("MTRB_Fix.mq5 ditulis (patch DashTick 2s)")
PY

  for f in MTRB_SMC.mqh MTRB_SMC_Core.mqh; do
    [ -f "$SRC/$f" ] && cp "$SRC/$f" "$E/$f"
  done

  cd "$D" || exit 1
  rm -f "$E/MTRB_Fix.ex5" "$E/mtrb_deploy.log"
  timeout 300 "$WINEW" metaeditor64.exe /compile:"MQL5\Experts\MTRB_Fix.mq5" /log:"MQL5\Experts\mtrb_deploy.log" >/dev/null 2>&1
  RES=$(iconv -f UTF-16LE -t UTF-8 "$E/mtrb_deploy.log" 2>/dev/null | grep -a "Result:" | tail -1 | tr -d '\r')
  log "compile: $RES"
  [ -f "$E/MTRB_Fix.ex5" ] || { log "ex5 tidak dihasilkan"; exit 3; }
  log "ex5 baru: $(stat -c %s "$E/MTRB_Fix.ex5") byte"
  exit 0
fi

# ---------- fase root: backup + restart + verifikasi ----------
cd "$SRC" || exit 1
VER=$(grep -oP '(?<=#property version\s\s\s")[0-9.]+' MTRB_Pro.mq5 | head -1)
mkdir -p "$BAKDIR"
OLD=$(cat "$BAKDIR/.last_version" 2>/dev/null || echo "lama")
cp -n "$E/MTRB_Fix.ex5" "$BAKDIR/MTRB_Fix_v$OLD.ex5" 2>/dev/null || true
echo "$VER" > "$BAKDIR/.last_version"

if [ "$DRY_RUN" -eq 1 ]; then
  log "--dry-run: ex5 sudah di-compile, restart dilewati"
  exit 0
fi

log "restart mt5-ex-demo"
systemctl restart mt5-ex-demo

log "menunggu status JSON jadi v$VER (maks 8 menit; init SMC lambat)"
for i in $(seq 1 48); do
  sleep 10
  V=$(grep -oP '(?<="v":")[0-9.]+' "$STATUS" 2>/dev/null | head -1)
  if [ "$V" = "$VER" ]; then
    log "OK: status JSON sudah v$V ($((i*10))s)"
    exit 0
  fi
done
log "PERINGATAN: status masih v$(grep -oP '(?<="v":")[0-9.]+' "$STATUS" 2>/dev/null | head -1) setelah 8 menit"
exit 4
