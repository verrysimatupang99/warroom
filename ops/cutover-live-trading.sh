#!/usr/bin/env bash
# Cutover ~/live-trading: migrasi infra-watchdog ke venv warroom, lalu arsipkan kode lama.
#
# AMAN: setiap langkah destruktif minta konfirmasi; langkah hapus di-GUARD oleh
# pemeriksaan bahwa tak ada unit lagi yang menyentuh venv lama.
#
# Jalankan sebagai user `admin` DI SESI LOGIN (agar `systemctl --user` bekerja):
#     bash cutover-live-trading.sh
#
# Tidak menyentuh state/ secrets/ backups/ logs/ index-cache/ (data hidup).
set -uo pipefail

LT="$HOME/live-trading"
WR="$HOME/warroom"
ARSIP="$HOME/arsip"
UNIT="$HOME/.config/systemd/user/infra-watchdog.service"
SKRIP_ASAL="$LT/scripts/ops/infra-watchdog.py"
SKRIP_TUJUAN="$WR/ops/ops-scripts/infra-watchdog.py"

langkah() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$1"; }
ok()      { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
gagal()   { printf '  \033[31mGAGAL\033[0m %s\n' "$1"; }
tanya()   { printf '\n  \033[33m>> %s [y/N] \033[0m' "$1"; read -r j; [[ "$j" == "y" || "$j" == "Y" ]]; }

# --- 0. Prakondisi ---------------------------------------------------------------
langkah "0/4 Prakondisi"
[[ -f "$UNIT" ]]        || { gagal "unit tak ada: $UNIT"; exit 1; }
[[ -f "$SKRIP_ASAL" ]]  || { gagal "skrip tak ada: $SKRIP_ASAL"; exit 1; }
systemctl --user is-system-running >/dev/null 2>&1 || true
if ! systemctl --user status >/dev/null 2>&1; then
  gagal "systemctl --user tidak bisa diakses. Jalankan di sesi login (bukan dari agen/ssh non-login)."
  exit 1
fi
ok "unit & skrip ditemukan; systemctl --user dapat diakses"

# --- 1. Migrasi infra-watchdog ---------------------------------------------------
langkah "1/4 Migrasi infra-watchdog ke venv warroom"
mkdir -p "$(dirname "$SKRIP_TUJUAN")"
cp "$SKRIP_ASAL" "$SKRIP_TUJUAN"
ok "skrip disalin -> $SKRIP_TUJUAN"

python3 - "$UNIT" "$SKRIP_TUJUAN" <<'PY'
import sys
from pathlib import Path
unit, skrip = Path(sys.argv[1]), sys.argv[2]
t = unit.read_text()
lama = "ExecStart=/home/admin/live-trading/.venv/bin/python /home/admin/live-trading/scripts/ops/infra-watchdog.py"
baru = f"ExecStart=/home/admin/warroom/.venv/bin/python {skrip}"
if lama in t:
    unit.write_text(t.replace(lama, baru))
    print("  OK   ExecStart diperbarui")
elif baru in t:
    print("  OK   ExecStart sudah mengarah ke warroom (idempoten)")
else:
    print("  GAGAL pola ExecStart tak cocok — periksa unit manual"); sys.exit(1)
PY

systemctl --user daemon-reload
systemctl --user start infra-watchdog.service || true
sleep 2
if systemctl --user show infra-watchdog.service -p ExecMainStatus --value | grep -q '^0$'; then
  ok "infra-watchdog jalan (exit 0)"
else
  gagal "infra-watchdog exec tidak 0 — cek: journalctl --user -u infra-watchdog.service -n 40"
  printf '  Lanjut tetap? risiko: watchdog mati. [y/N] '; read -r j; [[ "$j" == y ]] || exit 1
fi

# --- 2. GUARD: tak ada unit lagi yang pakai venv lama -----------------------------
langkah "2/4 Guard: cek tak ada unit menyentuh venv lama"
sisa=$(grep -rl "/home/admin/live-trading/.venv" "$HOME/.config/systemd/user/"/*.service /etc/systemd/system/*.service 2>/dev/null || true)
if [[ -n "$sisa" ]]; then
  gagal "MASIH ada unit menyentuh venv lama:"; echo "$sisa" | sed 's/^/    /'
  echo "  STOP. Perbaiki dulu, jangan lanjut hapus."
  exit 1
fi
ok "bersih: tak ada unit yang menyentuh venv lama"

# --- 3. Arsipkan kode lama -------------------------------------------------------
langkah "3/4 Arsipkan kode lama"
mkdir -p "$ARSIP"
TAR="$ARSIP/live-trading-kode-$(date +%Y%m%d).tar.gz"
tanya "Buat arsip $TAR dari src .venv .venv.lama scripts ?"
if [[ -f "$TAR" ]]; then ok "arsip sudah ada (lewati pembuatan)"; else
  tar -czf "$TAR" -C "$LT" src .venv .venv.lama scripts && ok "arsip dibuat"
fi
ls -lh "$TAR"

tanya "Hapus ~/live-trading/.venv.lama (146 MB, venv super lama) ?"
rm -rf "$LT/.venv.lama" && ok ".venv.lama dihapus"

tanya "Hapus ~/live-trading/.venv + ~/live-trading/src (butuh langkah 1 sukses) ?"
rm -rf "$LT/.venv" "$LT/src" && ok ".venv + src dihapus"

# --- 4. Verifikasi ---------------------------------------------------------------
langkah "4/4 Verifikasi"
echo "  state/ (DATA hidup) — harus utuh:"
ls "$LT/state/" 2>/dev/null | head -5 | sed 's/^/    /'
echo "  sisa ukuran ~/live-trading: $(du -sh "$LT" 2>/dev/null | cut -f1)"
echo "  layanan inti:"
for u in warroom-api warroom-worker warroom-web nginx; do
  printf '    %-18s %s\n' "$u" "$(systemctl is-active "$u" 2>/dev/null)"
done
echo "  watchdog timer:"
systemctl --user list-timers 2>/dev/null | grep -i watchdog | sed 's/^/    /' || echo "    (tak ada)"
printf '\n\033[1;32mSelesai.\033[0m state/ TIDAK disentuh. Verifikasi di atas.\n'
