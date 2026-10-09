#!/usr/bin/env bash
# Setel WARROOM_BUILD_ID untuk layanan yang sedang di-deploy.
#
# Menulis /etc/warroom/build.env (dibaca systemd lewat EnvironmentFile di warroom-api
# dan warroom-web). Dipakai skrip deploy supaya proses yang JALAN melaporkan build_id
# yang sama dengan yang baru di-build — menutup insiden 2026-10-08/09 (proses lama
# memegang manifest lama sementara chunk di disk sudah diganti build baru -> HTTP 500).
#
# Pakai:
#   ops/set-build-id.sh [build_id]
# Bila argumen kosong, diturunkan dari git HEAD + stempel waktu.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ID="${1:-}"

if [[ -z "$BUILD_ID" ]]; then
	sha="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo local)"
	stamp="$(date -u +%Y%m%dT%H%M%SZ)"
	BUILD_ID="${sha}-${stamp}"
fi

# Sanitasi: hanya huruf/angka/titik/dash/underscore (nilai masuk ke systemd env).
if [[ ! "$BUILD_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
	echo "build_id tidak valid (hanya A-Za-z0-9._-): $BUILD_ID" >&2
	exit 2
fi

tmp="$(mktemp)"
printf '# Dibuat oleh ops/set-build-id.sh — JANGAN diedit tangan.\nWARROOM_BUILD_ID=%s\n' "$BUILD_ID" > "$tmp"
sudo -n install -m 0644 -o root -g root "$tmp" /etc/warroom/build.env
rm -f "$tmp"

echo "WARROOM_BUILD_ID=$BUILD_ID -> /etc/warroom/build.env"
