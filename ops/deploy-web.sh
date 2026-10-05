#!/usr/bin/env bash
# Deploy web War Room: build → restart → HEALTH GATE → rollback otomatis bila gagal.
#
# Kenapa harus restart: `npm run build` mengganti isi build/ (hash chunk baru).
# Proses node yang masih jalan memegang manifest lama → request berikutnya gagal
# "Cannot find module .../nodes/0.js-*.js" → HTTP 500. Kejadian nyata 3 Okt 2026.
#
# Kenapa health gate ini bukan sekadar `curl /`: cek 200 saja tidak membuktikan proses
# yang JALAN memegang build BARU. Karena itu setelah restart kita ambil satu aset
# `/_app/...` dari HTML yang disajikan dan pastikan aset itu benar-benar ada (200).
# Itu tepat kelas kegagalan manifest-basi di atas.
#
# Perbaikan temuan SRE 5 Okt 2026: dulu skrip hanya `curl -sf /` sekali tanpa timeout,
# tanpa retry, dan tanpa rollback — bad build dilaporkan "web ok".
set -euo pipefail

WEB_DIR="$(dirname "$0")/../apps/web"
cd "$WEB_DIR"

TIMEOUT_S="${WARROOM_DEPLOY_TIMEOUT:-40}"
INTERVAL_S=2
BASE="http://127.0.0.1:3100"
BACKUP_DIR="/home/admin/warroom/backups/web-$(date +%Y%m%d-%H%M%S)"

# 1) Simpan build lama untuk rollback.
if [[ -d build ]]; then
	mkdir -p "$BACKUP_DIR"
	cp -a build "$BACKUP_DIR/"
	echo "backup build lama -> $BACKUP_DIR"
fi

# 2) Build.
npm run build

# 3) Restart.
sudo -n systemctl restart warroom-web

# 4) Health gate: tunggu root 200, lalu buktikan aset build BARU benar-benar tersaji.
lolos=0
elapsed=0
while (( elapsed < TIMEOUT_S )); do
	if ! systemctl is-active --quiet warroom-web; then
		echo "warroom-web tidak aktif (crash?)"
		break
	fi
	if html="$(curl -sf --max-time 3 "$BASE/")"; then
		# Ambil satu jalur aset /_app/... dari HTML yang disajikan.
		aset="$(printf '%s' "$html" | grep -oE '/_app/[A-Za-z0-9._/-]+\.js' | head -n1 || true)"
		if [[ -n "$aset" ]] && curl -sf -o /dev/null --max-time 3 "$BASE$aset"; then
			lolos=1
			break
		fi
	fi
	sleep "$INTERVAL_S"
	elapsed=$(( elapsed + INTERVAL_S ))
done

if (( lolos == 1 )); then
	echo "web ok (build + restart + aset build baru tersaji)"
	exit 0
fi

# 5) Rollback: kembalikan build lama lalu restart lagi.
echo "HEALTH GATE GAGAL setelah ${TIMEOUT_S}s — rollback ke build sebelumnya"
if [[ -d "$BACKUP_DIR/build" ]]; then
	rm -rf build
	cp -a "$BACKUP_DIR/build" build
	sudo -n systemctl restart warroom-web
	sleep "$INTERVAL_S"
	if curl -sf -o /dev/null --max-time 3 "$BASE/"; then
		echo "rollback selesai — web kembali ke build sebelumnya"
	else
		echo "rollback DIJALANKAN tetapi web masih tidak sehat — periksa journalctl -u warroom-web"
	fi
else
	echo "tidak ada backup build untuk di-rollback — periksa journalctl -u warroom-web"
fi
exit 1
