#!/usr/bin/env bash
# Dump harian Postgres War Room (format custom + checksum + rotasi terbatas).
# Kredensial DB disuntik systemd (root) dari /etc/warroom/db.env; berkas itu tetap
# 600 root dan tidak pernah dibuka proses ini.
set -euo pipefail

OUT_DIR="${WARROOM_DB_BACKUP_DIR:-/home/admin/backups/postgres}"
KEEP="${WARROOM_DB_BACKUP_KEEP:-14}"

: "${WARROOM_DB_URL:?WARROOM_DB_URL tidak ada — jalankan lewat unit systemd yang memuat /etc/warroom/db.env}"
command -v pg_dump >/dev/null || {
	echo "GAGAL: pg_dump tidak ditemukan"
	exit 1
}

# WARROOM_DB_URL memakai format SQLAlchemy (postgresql+psycopg://...). libpq tidak
# mengenal akhiran driver "+psycopg", sehingga pg_dump mengabaikan URL dan jatuh ke
# koneksi default (socket lokal, user OS "admin") → FATAL: role "admin" does not exist.
# Dump 17 & 18 Okt 2026 gagal karena ini; buang akhiran drivernya sebelum dipakai.
PG_URL="$(echo "$WARROOM_DB_URL" | sed -E 's#^(postgresql|postgres)\+[A-Za-z0-9_]+://#\1://#')"

umask 077
mkdir -p "$OUT_DIR"
pas="$OUT_DIR/warroom-$(date -u +%Y%m%d-%H%M%S).dump"

# Tulis ke berkas sementara lalu pindahkan: dump gagal tidak boleh meninggalkan
# berkas 0-byte yang tampak seperti backup sah (persis yang terjadi 17-18 Okt).
pas_tmp="$pas.part"
trap 'rm -f "$pas_tmp"' EXIT

pg_dump --format=custom --file="$pas_tmp" "$PG_URL"

# pg_dump bisa keluar 0 dengan berkas kosong pada kegagalan tertentu; ukuran nol
# berarti tidak ada yang bisa di-restore, jadi perlakukan sebagai gagal.
if [[ ! -s "$pas_tmp" ]]; then
	echo "GAGAL: dump kosong (0 byte) — periksa koneksi/kredensial DB"
	exit 1
fi

mv -f "$pas_tmp" "$pas"
trap - EXIT

# Header/TOC terbaca = dump benar-benar berformat; bukan pengganti drill restore.
pg_restore --list "$pas" >/dev/null
# Checksum disimpan dengan path RELATIF (basename) supaya verifikasi tetap
# valid setelah dump disalin ke tujuan offsite. Dengan path absolut, `sha256sum -c`
# akan memeriksa file ASLI dan memberi "OK" hijau palsu pada salinan yang rusak.
( cd "$OUT_DIR" && sha256sum "$(basename "$pas")" > "$(basename "$pas").sha256" )
echo "dump: $pas ($(du -h "$pas" | cut -f1)) + .sha256"

# Rotasi: sisakan $KEEP dump terbaru; checksum ikut terhapus bersama dumpnya.
ls -1t "$OUT_DIR"/warroom-*.dump 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r f; do
	rm -f "$f" "$f.sha256"
	echo "rotasi: hapus $(basename "$f")"
done

# Sisa dump gagal (0 byte, `.part` yang tak sempat di-mv). Glob rotasi di atas hanya
# cocok dengan `*.dump`, jadi berkas ini tidak pernah ikut terhapus sendiri.
rm -f "$OUT_DIR"/warroom-*.dump.invalid "$OUT_DIR"/warroom-*.dump.part
