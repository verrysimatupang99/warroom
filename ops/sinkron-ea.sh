#!/usr/bin/env bash
# Satu sumber kebenaran untuk berkas EA MT5.
#
# Masalah yang ditutup: EA pernah tersalin ke 4+ lokasi dan salah satunya
# tertinggal versi lama, sehingga web menyajikan EA 20 KB (pra-InpUseRiskSizing)
# sementara sumbernya sudah 40 KB.
#
# Pakai:
#   ops/sinkron-ea.sh          # salin sumber ke semua target + verifikasi md5
#   ops/sinkron-ea.sh check    # hanya periksa, tidak menulis (exit 1 bila beda)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/apps/web/static/WarRoom_AutoTrader.mq5"
TARGETS=(
	"$ROOT/apps/web/build/client/WarRoom_AutoTrader.mq5"
	"/srv/private/WarRoom_AutoTrader.mq5"
	"/srv/pratinjau/WarRoom_AutoTrader.mq5"
	"$ROOT/ops/docker-mt5/config/WarRoom_AutoTrader.mq5"
)
MODE="${1:-sync}"

[[ -f "$SRC" ]] || { echo "SUMBER TIDAK ADA: $SRC"; exit 1; }
src_md5="$(md5sum "$SRC" | cut -d' ' -f1)"
echo "sumber : $SRC"
echo "         $(stat -c%s "$SRC") byte, md5 ${src_md5:0:10}"
echo

fail=0
if [[ "$MODE" == "check" ]]; then
	for t in "${TARGETS[@]}"; do
		if [[ ! -f "$t" ]]; then
			echo "  HILANG  $t"
			fail=1
			continue
		fi
		m="$(md5sum "$t" | cut -d' ' -f1)"
		if [[ "$m" == "$src_md5" ]]; then
			echo "  ok      $t"
		else
			echo "  BEDA    $t (md5 ${m:0:10})"
			fail=1
		fi
	done
	[[ $fail -eq 0 ]] && echo -e "\nsemua target sinkron." || echo -e "\nada target tidak sinkron."
	exit $fail
fi

for t in "${TARGETS[@]}"; do
	dir="$(dirname "$t")"
	if [[ ! -d "$dir" ]]; then
		echo "  lewati  $t (direktori tidak ada)"
		continue
	fi
	if [[ -w "$dir" ]]; then
		cp -f "$SRC" "$t"
	else
		sudo cp -f "$SRC" "$t"
	fi
	echo "  salin   $t"
done

echo
echo "--- verifikasi ---"
for t in "${TARGETS[@]}"; do
	[[ -f "$t" ]] || continue
	m="$(md5sum "$t" | cut -d' ' -f1)"
	if [[ "$m" == "$src_md5" ]]; then
		echo "  ok      $t"
	else
		echo "  GAGAL   $t (md5 ${m:0:10})"
		fail=1
	fi
done

exit $fail
