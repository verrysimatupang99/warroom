#!/usr/bin/env bash
# Deploy web War Room: build lalu RESTART service.
#
# Kenapa harus restart: `npm run build` mengganti isi build/ (hash chunk baru).
# Proses node yang masih jalan memegang manifest lama → request berikutnya gagal
# "Cannot find module .../nodes/0.js-*.js" → HTTP 500. Kejadian nyata 3 Okt 2026.
set -euo pipefail
cd "$(dirname "$0")/../apps/web"
npm run build
sudo -n systemctl restart warroom-web
sleep 2
curl -sf -o /dev/null http://127.0.0.1:3100/ && echo "web ok (build + restart)"
