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

# Jalur absolut skrip ops — WAJIB dihitung SEBELUM `cd`, karena setelah pindah ke apps/web
# jalur relatif "ops/..." tidak lagi menunjuk ke tempat yang benar (bug nyata 7 Okt:
# csp-enforce.sh selalu "gagal dipasang" saat dipanggil dari deploy, padahal jalan manual).
OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$OPS_DIR/../apps/web"
cd "$WEB_DIR"

TIMEOUT_S="${WARROOM_DEPLOY_TIMEOUT:-40}"
INTERVAL_S=2
BASE="http://127.0.0.1:3100"
API_BASE="http://127.0.0.1:8800"
BACKUP_DIR="/home/admin/warroom/backups/web-$(date +%Y%m%d-%H%M%S)"

# Identitas build untuk verifikasi build<->proses.
# Sumber utama: /etc/warroom/build.env yang ditulis ops/set-build-id.sh — HARUS dipakai
# agar build_id web sama persis dengan yang dilaporkan API (EnvironmentFile unit yang sama).
# Dulu skrip ini jatuh ke `git rev-parse --short HEAD` sehingga build-id.txt berisi "b1efa03"
# sementara API melaporkan "b1efa03-20261018T102646Z" — peringatan palsu di setiap deploy.
if [[ -z "${WARROOM_BUILD_ID:-}" && -r /etc/warroom/build.env ]]; then
	# shellcheck disable=SC1091
	WARROOM_BUILD_ID="$(sed -nE 's/^WARROOM_BUILD_ID=(.*)$/\1/p' /etc/warroom/build.env | tail -n1)"
fi
BUILD_ID="${WARROOM_BUILD_ID:-$(git -C "$WEB_DIR" rev-parse --short HEAD 2>/dev/null || echo local)}"
export WARROOM_BUILD_ID="$BUILD_ID"
echo "build_id: $BUILD_ID"

# 1) Simpan build lama untuk rollback.
if [[ -d build ]]; then
	mkdir -p "$BACKUP_DIR"
	cp -a build "$BACKUP_DIR/"
	echo "backup build lama -> $BACKUP_DIR"
fi
# Retensi backup: simpan 10 terbaru agar disk tak penuh (prune 2026-10-13).
find /home/admin/warroom/backups -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -r | tail -n +11 | xargs -r rm -rf

# 2) Build. Skrip npm juga menulis build/build-id.txt + build-id.js (identitas build).
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

# 4b) VERIFIKASI build<->proses: proses yang JALAN harus melaporkan build_id yang sama
#     dengan yang baru di-build. Ini menutup tepat insiden 2026-10-08/09 (proses lama
#     memegang manifest lama sementara chunk di disk sudah diganti -> HTTP 500).
if (( lolos == 1 )); then
	id_disk="$(cat "$WEB_DIR/build/build-id.txt" 2>/dev/null | tr -d '\n' || true)"
	# API melaporkan build_id proses (WARROOM_BUILD_ID di-inject lewat systemd EnvironmentFile).
	id_api="$(curl -sf --max-time 3 "$API_BASE/api/v1/build" 2>/dev/null | grep -oE '"build_id"\s*:\s*"[^"]*"' | head -n1 | sed -E 's/.*"([^"]*)"$/\1/' || true)"
	if [[ -n "$id_disk" && -n "$id_api" && "$id_disk" != "$id_api" ]]; then
		echo "PERINGATAN: build_id disk ($id_disk) != build_id API ($id_api)"
		echo "  API mungkin belum di-restart. Jalankan: sudo systemctl restart warroom-api"
		# Web sendiri sudah lolos health gate; ini peringatan lintas-layanan, bukan kegagalan web.
	fi
fi

if (( lolos == 1 )); then
	# 2b) Pasang CSP ENFORCE dengan hash skrip bootstrap build BARU (audit QA putaran 2).
	# Dilakukan setelah health gate supaya HTML yang di-hash memang yang tersaji; kalau
	# gagal, web tetap hidup dengan CSP report-only dari nginx (fail-safe, bukan fail-open
	# tanpa kabar — pesannya dicetak).
	if ! bash "$OPS_DIR/csp-enforce.sh"; then
		echo "PERINGATAN: CSP enforce gagal dipasang — masih report-only"
	fi
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
