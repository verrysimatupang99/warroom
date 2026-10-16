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

umask 077
mkdir -p "$OUT_DIR"
pas="$OUT_DIR/warroom-$(date -u +%Y%m%d-%H%M%S).dump"

pg_dump --format=custom --file="$pas" "$WARROOM_DB_URL"

# Header/TOC terbaca = dump benar-benar berformat; bukan pengganti drill restore.
pg_restore --list "$pas" >/dev/null
sha256sum "$pas" > "$pas.sha256"
echo "dump: $pas ($(du -h "$pas" | cut -f1)) + .sha256"

# Rotasi: sisakan $KEEP dump terbaru; checksum ikut terhapus bersama dumpnya.
ls -1t "$OUT_DIR"/warroom-*.dump 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r f; do
	rm -f "$f" "$f.sha256"
	echo "rotasi: hapus $(basename "$f")"
done
