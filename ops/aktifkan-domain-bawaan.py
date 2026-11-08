#!/usr/bin/env python3
"""Aktifkan app War Room (:3100) + API (:8800) di domain bawaan Webdock.

Kenapa script, bukan sed: `location /` harus DIUBAH di tempat, bukan ditambah.
Dua blok `location /` dalam satu server block = nginx menolak config.

Aman diulang: kalau sudah diterapkan, keluar tanpa perubahan.
Pakai:
    sudo python3 /home/admin/warroom/ops/aktifkan-domain-bawaan.py --dry-run
    sudo python3 /home/admin/warroom/ops/aktifkan-domain-bawaan.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONF = Path("/etc/nginx/sites-enabled/webdock")
# Backup HARUS di luar sites-enabled: nginx memuat `include sites-enabled/*`,
# jadi file .bak di sana ikut terbaca dan memicu "duplicate listen options".
BACKUP_DIR = Path("/var/backups/nginx")
MARK_APP = "# --- War Room app (dipasang oleh aktifkan-domain-bawaan.py) ---"
DOMAIN = "polywarroom.vps.webdock.cloud"

API_BLOCK = f"""        {MARK_APP}
        # API + SSE. proxy_buffering off wajib: tanpa itu /api/v1/stream menggantung.
        # auth_basic off: EA MT5 tidak bisa basic auth; dia pakai X-Warroom-Token
        # + allowlist IP (lihat services/api/src/warroom_api/auth_ea.py).
        location /api/v1/ {{
            auth_basic off;
            proxy_pass http://127.0.0.1:8800;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            add_header Cache-Control "no-store" always;
        }}

        # Sinyal Telegram (trading-engine :8088) — dipindah dari vhost lama.
        location /signals {{
            auth_basic off;
            proxy_pass http://127.0.0.1:8088/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        # Web terminal (ttyd :7681) — dipindah dari vhost lama.
        location ^~ /term/ {{
            auth_basic off;
            proxy_pass http://127.0.0.1:7681;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }}
"""

NEW_ROOT = """        # Sisa permintaan -> app War Room hidup (SvelteKit adapter-node :3100).
        # Login di aplikasi (cookie sesi HttpOnly + RBAC), bukan basic-auth proxy,
        # jadi basic auth di level server dimatikan di sini.
        # Snapshot statis lama (/var/www/html) kini tidak dilayani root lagi;
        # poly-dashboard-sync.timer tetap jalan tapi hasilnya menganggur.
        location / {
            auth_basic off;
            proxy_pass http://127.0.0.1:3100;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
"""


def fail(msg: str) -> None:
    print(f"GAGAL: {msg}", file=sys.stderr)
    sys.exit(1)


def server_block(text: str, domain: str) -> tuple[int, int]:
    """Rentang (start, end) server block 443 yang melayani `domain`."""
    for m in re.finditer(r"(?m)^server\s*\{", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        block = text[m.start():i]
        if f"server_name {domain};" in block and "listen 443 ssl" in block:
            return m.start(), i
    fail(f"server block 443 untuk {domain} tidak ditemukan")


def main() -> None:
    dry = "--dry-run" in sys.argv
    if not CONF.exists():
        fail(f"{CONF} tidak ada")
    text = CONF.read_text()

    if MARK_APP in text:
        print("Sudah diterapkan sebelumnya — tidak ada perubahan.")
        subprocess.run(["nginx", "-t"], check=False)
        return

    start, end = server_block(text, DOMAIN)
    block = text[start:end]

    # Ganti `location / { ... }` pertama (yang try_files ke index.php).
    m = re.search(r"(?m)^[ \t]*location / \{\n(?:.*?\n)*?[ \t]*\}\n", block)
    if not m:
        fail("`location /` tidak ditemukan di server block; periksa manual")
    old_root = m.group(0)
    if "3100" in old_root:
        fail("`location /` sudah mengarah ke :3100 — periksa manual")

    new_block = block[:m.start()] + NEW_ROOT + "\n" + API_BLOCK + "\n" + block[m.end():]
    new_text = text[:start] + new_block + text[end:]

    print("=== `location /` lama ===")
    print(old_root.rstrip())
    print("\n=== akan menjadi ===")
    print((NEW_ROOT + API_BLOCK).rstrip())

    if dry:
        print("\n[dry-run] tidak menulis apa pun.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}"
    shutil.copy2(CONF, backup)
    print(f"\nbackup: {backup}")

    CONF.write_text(new_text)
    print(f"ditulis: {CONF}")

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        shutil.copy2(backup, CONF)
        print(test.stderr, file=sys.stderr)
        fail("nginx -t gagal — config dikembalikan dari backup")

    print(test.stderr.strip())
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print("nginx direload. Verifikasi:")
    print("  curl -s -o /dev/null -w '%{http_code}\\n' https://polywarroom.vps.webdock.cloud/api/v1/health")
    print("  curl -s -o /dev/null -w '%{http_code}\\n' https://polywarroom.vps.webdock.cloud/")


if __name__ == "__main__":
    main()