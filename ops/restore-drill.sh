#!/usr/bin/env bash
# Drill restore Postgres: buktikan dump terbaru benar-benar bisa dipulihkan.
#
# Kenapa ada: backup yang tidak pernah diuji bukan backup. Drill 31 Okt 2026
# (docs/audit-ops-20261031.md) dilakukan manual; skrip ini menjadikannya rutin.
#
# Sifat: membuat DB uji `warroom_restore_drill`, memulihkan dump terbaru ke sana,
# menghitung facts/alerts/jobs, menulis bukti JSON, lalu MENGHAPUS DB uji.
# Tidak menyentuh DB produksi, Tencent, Azure, atau /opt/polymarket.
set -euo pipefail

OUT_DIR="${WARROOM_DB_BACKUP_DIR:-/home/admin/backups/postgres}"
BUKTI_DIR="${WARROOM_RESTORE_DRILL_DIR:-/var/lib/warroom/restore-drill}"
DB="warroom_restore_drill"

LATEST="$(ls -1t "$OUT_DIR"/warroom-*.dump 2>/dev/null | head -n1 || true)"
if [[ -z "$LATEST" ]]; then
	echo "GAGAL: tidak ada dump di $OUT_DIR" >&2
	exit 1
fi
if [[ ! -f "$LATEST.sha256" ]] || ! sha256sum -c "$LATEST.sha256" >/dev/null 2>&1; then
	echo "GAGAL: checksum tidak cocok untuk $(basename "$LATEST")" >&2
	exit 1
fi

# Unit berjalan sebagai root; interaktif memakai sudo -n (allowlist admin).
if [[ "${EUID}" -eq 0 ]]; then
	as_postgres=(runuser -u postgres --)
else
	as_postgres=(sudo -n -u postgres --)
fi

dropdb() { "${as_postgres[@]}" dropdb --if-exists "$DB"; }
trap 'dropdb >/dev/null 2>&1 || true' EXIT

dropdb
"${as_postgres[@]}" createdb "$DB"
mkdir -p "$BUKTI_DIR"

mulai="$(date +%s)"
if ! "${as_postgres[@]}" pg_restore --no-owner --no-privileges -d "$DB" \
	<"$LATEST" >"$BUKTI_DIR/pg_restore.log" 2>&1; then
	echo "GAGAL: pg_restore gagal; lihat $BUKTI_DIR/pg_restore.log" >&2
	exit 1
fi
selesai="$(date +%s)"

hitung() {
	"${as_postgres[@]}" psql -d "$DB" -Atc "select count(*) from $1"
}
facts="$(hitung facts)"
alerts="$(hitung alerts)"
jobs="$(hitung jobs)"

if [[ "$facts" -le 0 || "$jobs" -le 0 ]]; then
	echo "GAGAL: hasil restore tidak masuk akal (facts=$facts jobs=$jobs)" >&2
	exit 1
fi

mkdir -p "$BUKTI_DIR"
python3 - "$BUKTI_DIR/last.json" "$LATEST" "$facts" "$alerts" "$jobs" "$((selesai - mulai))" <<'PY'
import json, sys
from datetime import UTC, datetime

path, dump, facts, alerts, jobs, durasi = sys.argv[1:]
json.dump(
    {
        "ok": True,
        "dump": dump,
        "facts": int(facts),
        "alerts": int(alerts),
        "jobs": int(jobs),
        "durasi_detik": int(durasi),
        "selesai_at": datetime.now(UTC).isoformat(),
        "catatan": "DB uji dihapus setelah verifikasi; produksi tidak disentuh",
    },
    open(path, "w", encoding="utf-8"),
    indent=2,
)
PY

echo "drill: ok dump=$(basename "$LATEST") facts=$facts alerts=$alerts jobs=$jobs durasi=$((selesai - mulai))s"
