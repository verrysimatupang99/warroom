#!/usr/bin/env python3
"""Pasang header keamanan di server block 443 domain bawaan Webdock.

Vhost lama (0xgunsl1ng3r.xyz) punya 7 header keamanan; server block baru tidak
punya satu pun setelah migrasi domain. Script ini mengembalikannya.

Catatan nginx: `add_header` di dalam `location` MENGGANTIKAN (bukan menambah)
`add_header` di level server. Location yang punya add_header sendiri
(`/api/v1/` -> Cache-Control) karena itu tidak ikut mendapat header ini —
itu disengaja: respons API memang `no-store` dan tidak di-cache.

Aman diulang. Pakai: sudo python3 ops/pasang-header-keamanan.py [--dry-run]
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONF = Path("/etc/nginx/sites-enabled/webdock")
BACKUP_DIR = Path("/var/backups/nginx")
DOMAIN = "polywarroom.vps.webdock.cloud"
MARK = "# [20261109] header keamanan (dibawa dari vhost 0xgunsl1ng3r.xyz saat migrasi)."

HEADERS = f"""
    {MARK}
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=()" always;
    add_header Cross-Origin-Opener-Policy "same-origin" always;
    add_header Cross-Origin-Resource-Policy "same-origin" always;
"""


def fail(msg: str) -> None:
    print(f"GAGAL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    dry = "--dry-run" in sys.argv
    text = CONF.read_text()
    if MARK in text:
        print("Sudah diterapkan — tidak ada perubahan.")
        return

    for m in re.finditer(r"(?m)^server\s*\{", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        block = text[m.start():i]
        if f"server_name {DOMAIN};" in block and "listen 443 ssl" in block:
            start, end = m.start(), i
            break
    else:
        fail(f"server block 443 {DOMAIN} tidak ditemukan")

    # Sisipkan tepat setelah kurung kurawal pembuka blok.
    open_brace = text.index("{", start)
    text = text[:open_brace + 1] + "\n" + HEADERS + text[open_brace + 1:]

    print(f"kurawal seimbang: {text.count('{')}/{text.count('}')}")
    if dry:
        print("[dry-run] tidak menulis.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}-pre-header"
    shutil.copy2(CONF, backup)
    CONF.write_text(text)

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        shutil.copy2(backup, CONF)
        print(test.stderr, file=sys.stderr)
        fail("nginx -t gagal — dikembalikan")
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print(f"backup: {backup}\nnginx direload.")


if __name__ == "__main__":
    main()