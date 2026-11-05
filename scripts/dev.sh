#!/usr/bin/env bash
# Jalankan seluruh War Room di mesin lokal: API + worker + web (dev).
#
# Kenapa ada: sebelumnya menjalankan proyek berarti menghafal empat perintah di
# dua direktori berbeda, dan mudah lupa salah satunya (worker lupa dinyalakan →
# Home kosong tanpa penjelasan). Skrip ini menyalakan ketiganya dan mematikan
# semuanya bila salah satu dihentikan.
#
# Yang dibutuhkan: uv, node/npm, dan Postgres yang sudah bisa dihubungi lewat
# WARROOM_DB_URL. Tanpa Postgres, gunakan `docker compose -f docker-compose.dev.yml up`.
#
# Penggunaan:  scripts/dev.sh [--tanpa-web]
set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"

TANPA_WEB=0
[[ "${1:-}" == "--tanpa-web" ]] && TANPA_WEB=1

if [[ ! -f .env ]]; then
	echo "dev: .env belum ada — menyalin dari .env.example (isi nilainya dulu)" >&2
	cp .env.example .env
	echo "dev: .env dibuat. Sesuaikan WARROOM_DB_URL lalu jalankan ulang." >&2
	exit 1
fi

# Muat .env tanpa menimpa variabel yang sudah diset di shell.
set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${WARROOM_DB_URL:-}" ]]; then
	echo "dev: WARROOM_DB_URL kosong di .env — API butuh database" >&2
	exit 1
fi

echo "dev: menyiapkan environment (uv sync --frozen)"
uv sync --frozen

pids=()
bersihkan() {
	trap - INT TERM EXIT
	echo
	echo "dev: mematikan proses…"
	for pid in "${pids[@]:-}"; do
		[[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
	done
	wait 2>/dev/null || true
}
trap bersihkan INT TERM EXIT

echo "dev: API    → http://127.0.0.1:8800"
uv run uvicorn warroom_api.app:app --port 8800 --reload &
pids+=("$!")

echo "dev: worker → siklus 30 detik"
uv run python -m warroom_worker.run --every 30 &
pids+=("$!")

if [[ "$TANPA_WEB" -eq 0 ]]; then
	echo "dev: web    → http://127.0.0.1:5173"
	( cd apps/web && npm run dev ) &
	pids+=("$!")
fi

wait
