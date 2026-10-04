#!/bin/bash
# Bersih-bersih disk Webdock — TIDAK menyentuh apa pun milik poly-*
echo "=== SEBELUM ==="; df -h / | tail -1

echo; echo "=== 1. Hapus container lab DVWA ==="
sudo docker rm -f dvwa-lab 2>&1 | tail -1 || echo "(tidak ada container)"

echo; echo "=== 2. Hapus image Strix sandbox (5.9G) ==="
sudo docker rmi ghcr.io/usestrix/strix-sandbox:1.3.0 2>&1 | tail -2

echo; echo "=== 3. Hapus image DVWA (935M) ==="
sudo docker rmi vulnerables/web-dvwa:latest 2>&1 | tail -2

echo; echo "=== 4. Prune image tak terpakai ==="
sudo docker image prune -af 2>&1 | tail -2

echo; echo "=== 5. Go module cache (~3G) — binary tetap aman di ~/go/bin ==="
export PATH=$PATH:/usr/local/go/bin
BEFORE=$(du -sh ~/go 2>/dev/null | cut -f1)
go clean -modcache 2>&1 | tail -1
echo "~/go: $BEFORE -> $(du -sh ~/go 2>/dev/null | cut -f1)"

echo; echo "=== SESUDAH ==="; df -h / | tail -1
echo "--- containerd ---"; sudo du -sh /var/lib/containerd 2>/dev/null
echo "--- binary recon masih ada? ---"; ls ~/go/bin 2>/dev/null | head -10
