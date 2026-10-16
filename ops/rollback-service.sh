#!/usr/bin/env bash
# Rollback satu service sumber ke commit tertentu:
#   ops/rollback-service.sh <api|worker> [commit]
# Tanpa argumen commit: kembali ke commit yang direkam deploy-service.sh terakhir.
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$OPS_DIR/.." && pwd)"
REKAM_DIR=/home/admin/warroom/backups
DRY_RUN="${WARROOM_DEPLOY_DRY_RUN:-0}"
TIMEOUT_S="${WARROOM_DEPLOY_TIMEOUT:-60}"
INTERVAL_S=2

svc="${1:-}"
rev="${2:-}"
case "$svc" in
	api | worker) ;;
	*)
		echo "pakai: ops/rollback-service.sh <api|worker> [commit]"
		exit 2
		;;
esac
unit="warroom-$svc"

die() {
	echo "GAGAL: $*"
	exit 1
}

[[ -n "$rev" || -f "$REKAM_DIR/deploy-terakhir-$svc.txt" ]] || \
	die "tidak ada commit tujuan: beri commit, atau rekam deploy lebih dulu"
rev="${rev:-$(cat "$REKAM_DIR/deploy-terakhir-$svc.txt")}"
git -C "$ROOT" cat-file -e "$rev^{commit}" 2>/dev/null || die "commit tidak dikenal: $rev"

if [[ "$DRY_RUN" == "1" ]]; then
	echo "DRY-RUN svc=$svc tujuan=$(git -C "$ROOT" rev-parse --short "$rev")"
	echo "DRY-RUN: git reset --hard + set-build-id + sudo -n systemctl restart $unit + gate ${TIMEOUT_S}s"
	exit 0
fi

[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || \
	die "tree git tidak bersih — reset --hard akan membuang perubahan; commit/stash dulu"

if [[ "$(git -C "$ROOT" rev-parse HEAD)" == "$(git -C "$ROOT" rev-parse "$rev")" ]]; then
	echo "sudah di $rev — tidak ada yang di-rollback"
	exit 0
fi

source "$OPS_DIR/deploy-lib.sh"
rollback_dan_restart "$rev"

if gate; then
	echo "$unit sehat pada $(git -C "$ROOT" rev-parse --short "$rev")"
else
	echo "gate belum hijau: sudo journalctl -u $unit -n 50 --no-pager"
	echo "bila skema DB lebih baru dari kode ini, unit tidak mau start — downgrade skema adalah keputusan owner."
	exit 1
fi
