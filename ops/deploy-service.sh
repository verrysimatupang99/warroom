#!/usr/bin/env bash
# Deploy satu service sumber (api/worker): set-build-id -> restart -> health gate.
# Gate gagal -> rollback otomatis ke commit sebelum-deploy lalu restart + gate ulang.
# Web punya jalur sendiri: ops/deploy-web.sh (gate-nya membuktikan aset build baru).
# Rollback manual ke commit tertentu: ops/rollback-service.sh <api|worker> <commit>.
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$OPS_DIR/.." && pwd)"
REKAM_DIR=/home/admin/warroom/backups
DRY_RUN="${WARROOM_DEPLOY_DRY_RUN:-0}"
TIMEOUT_S="${WARROOM_DEPLOY_TIMEOUT:-60}"
INTERVAL_S=2

svc="${1:-}"
case "$svc" in
	api | worker) ;;
	web)
		echo "web punya skrip sendiri: bash ops/deploy-web.sh (gate aset build baru)."
		exit 2
		;;
	*)
		echo "pakai: ops/deploy-service.sh <api|worker>"
		exit 2
		;;
esac
unit="warroom-$svc"

die() {
	echo "GAGAL: $*"
	exit 1
}

pre_rev="$(git -C "$ROOT" rev-parse HEAD)"
pre_commit="$(git -C "$ROOT" rev-parse --short HEAD)"

if [[ "$DRY_RUN" == "1" ]]; then
	echo "DRY-RUN svc=$svc commit=$pre_commit rev=$pre_rev"
	echo "DRY-RUN: ops/set-build-id.sh <head>-<stempel>, sudo -n systemctl restart $unit, gate ${TIMEOUT_S}s"
	echo "DRY-RUN: gagal -> git reset --hard $pre_commit + set-build-id + restart + gate ulang"
	exit 0
fi

# Rollback bekerja di atas commit bersih; tree kotor membuat reset --hard merusak kerja lain.
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || \
	die "tree git tidak bersih — commit/stash dulu di tree live"

BUILD_ID="$(git -C "$ROOT" rev-parse --short HEAD)-$(date -u +%Y%m%dT%H%M%SZ)"

# Rekam jejak untuk rollback manual jika dicatat sebelum restart.
source "$OPS_DIR/deploy-lib.sh"
mkdir -p "$REKAM_DIR"
printf '%s\n' "$pre_rev" > "$REKAM_DIR/deploy-terakhir-$svc.txt"

bash "$OPS_DIR/set-build-id.sh" "$BUILD_ID"
sudo -n systemctl restart "$unit"

if gate; then
	echo "$unit ok (build_id=$BUILD_ID, kode=$pre_commit); rollback bila perlu: ops/rollback-service.sh $svc"
	exit 0
fi

echo "HEALTH GATE GAGAL setelah ${TIMEOUT_S}s — rollback ke $pre_commit"
rollback_dan_restart "$pre_rev"
if gate; then
	echo "rollback selesai — $unit kembali sehat pada $pre_commit (deploy GAGAL)"
else
	echo "rollback DIJALANKAN tetapi $unit belum sehat: sudo journalctl -u $unit -n 50 --no-pager"
	echo "bila deploy tadi menjalankan migrasi Postgres, skema bisa lebih baru dari kode lama."
fi
exit 1
