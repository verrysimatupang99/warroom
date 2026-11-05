#!/usr/bin/env bash
# rewrite-history-telegram.sh — hapus API hash Telegram lama dari SELURUH git history.
#
# ⚠️  OPERASI DESTRUKTIF — baca semua sebelum menjalankan.
#
# Kapan dijalankan: SETELAH rotasi API hash baru selesai (my.telegram.org) dan semua
# sesi lama dicabut. Lihat SECURITY-telegram-hash.md.
#
# Kenapa: gitleaks (CI `secrets — gitleaks`) memindai seluruh history (`fetch-depth: 0`).
# Nilai lama di commit `7cd6b09` membuat CI merah meski README di HEAD sudah bersih.
#
# Dampak:
#   - SEMUA commit ditulis ulang (SHA berubah sejak `7cd6b09`).
#   - `git push --force` ke `main` — melanggar aturan repo; jalankan hanya atas
#     persetujuan owner, dan beri tahu setiap clone agar `git fetch && git reset --hard`.
#   - Tidak ada tag di repo (diverifikasi 5 Nov) → tidak perlu rewrite tag.
#
# Pakai:
#   bash ops/rewrite-history-telegram.sh <hash-lama> <workdir>
# contoh:
#   bash ops/rewrite-history-telegram.sh ea452b7e3d112a9c3f418d5bf6fb4d71 /home/admin/warroom
set -euo pipefail

OLD_HASH="${1:?argumen 1: API hash lama (32 hex)}"
WORKDIR="${2:-/home/admin/warroom}"

echo "== Gerbang prasyarat =="
if [[ ! "$OLD_HASH" =~ ^[0-9a-f]{32}$ ]]; then
  echo "GAGAL: hash lama harus 32 karakter hex." >&2; exit 1
fi
cd "$WORKDIR"
[[ -d .git ]] || { echo "GAGAL: $WORKDIR bukan repo git." >&2; exit 1; }

echo "REPO      : $(pwd)"
echo "BRANCH    : $(git rev-parse --abbrev-ref HEAD)"
echo "COMMITS   : $(git rev-list --count HEAD)"
echo "HASH LAMA : (disembunyikan, 32 hex)"
echo
echo "Konfirmasi rotasi dulu: sudah ganti api_hash di my.telegram.org dan cabut sesi lama?"
read -r -p "Ketik 'ROTASI-SELESAI' untuk lanjut: " KONFIRM
[[ "$KONFIRM" == "ROTASI-SELESAI" ]] || { echo "Dibatalkan."; exit 1; }

echo "== 1. Backup mirror (wajib) =="
BK=/home/admin/backups/warroom-pre-rewrite-$(date -u +%Y%m%d-%H%M%S).git
git clone --mirror "$(pwd)" "$BK"
echo "backup: $BK"
echo "sha sebelum: $(git rev-parse HEAD)"

echo "== 2. Siapkan git-filter-repo =="
if ! command -v git-filter-repo >/dev/null; then
  echo "git-filter-repo tidak ada — memasang ke venv sementara..."
  python3 -m pip install --quiet --user git-filter-repo || {
    echo "GAGAL memasang git-filter-repo. Pasang manual lalu ulangi." >&2; exit 1; }
fi

echo "== 3. Tulis replacement file + jalankan filter-repo =="
# filter-repo --replace-text mengganti literal string di seluruh isi history.
RF=$(mktemp)
printf '%s==>ROTATED-TELEGRAM-HASH\n' "$OLD_HASH" > "$RF"
# Jangan timpa backup yang dibuat filter-repo? filter-repo simpan ke .git/filter-repo
git filter-repo --force --replace-text "$RF"
rm -f "$RF"

echo "== 4. Verifikasi: hash lama hilang dari history? =="
if git log --all -S"$OLD_HASH" --oneline | grep -q .; then
  echo "GAGAL: hash lama masih muncul. JANGAN push. Periksa manual." >&2
  echo "Backup ada di: $BK" >&2
  exit 1
fi
echo "OK: hash lama tidak ditemukan lagi di history."

echo "== 5. (Opsional) verifikasi gitleaks bila biner tersedia =="
if command -v gitleaks >/dev/null; then
  gitleaks git . --redact --no-banner || echo "(gitleaks masih menemukan sesuatu — periksa)"
else
  echo "(gitleaks tidak terpasang; CI akan memverifikasi saat push)"
fi

cat <<EOF

== SELESAI — langkah push (manual, butuh izin owner) ==
  cd $(pwd)
  git remote add origin https://github.com/verrysimatupang99/warroom.git   # filter-repo menghapus origin
  git push --force origin main
  # lalu beri tahu semua clone: git fetch && git reset --hard origin/main

Backup sebelum rewrite: $BK
sha lama: lihat output langkah 1 di atas.
EOF
