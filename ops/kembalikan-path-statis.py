#!/usr/bin/env python3
"""Kembalikan dua path statis yang dulu dilayani vhost 0xgunsl1ng3r.xyz.

- /komuter/   -> alias /srv/komuter/   (aplikasi web Komuter, dulu publik)
- /pratinjau/ -> alias /srv/pratinjau/ (halaman pratinjau + unduhan EA, dulu publik)

Di vhost lama keduanya dilayani tanpa basic auth (autentikasi ada di aplikasi).
Perilaku itu dipertahankan supaya tidak ada yang putus saat domain pindah.

Aman diulang. Pakai: sudo python3 ops/kembalikan-path-statis.py [--dry-run]
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
MARK = "# [20261109] path statis yang dulu dilayani vhost 0xgunsl1ng3r.xyz."

BLOCK = f"""        {MARK}
        location = /komuter {{ return 301 /komuter/; }}
        location ^~ /komuter/ {{
            auth_basic off;
            alias /srv/komuter/;
            index index.html;
            try_files $uri $uri/ /komuter/index.html;
        }}
        location = /pratinjau {{ return 302 /pratinjau/opsi-tampilan.html; }}
        location ^~ /pratinjau/ {{
            auth_basic off;
            alias /srv/pratinjau/;
            autoindex off;
            try_files $uri =404;
        }}
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

    m = re.search(r"(?m)^[ \t]*location / \{\n", text)
    if not m:
        fail("`location /` tidak ditemukan")
    i = text.index("{", m.start()) + 1
    depth = 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    text = text[:i] + "\n" + BLOCK + text[i:]

    print(f"kurawal seimbang: {text.count('{')}/{text.count('}')}")
    if dry:
        print("[dry-run] tidak menulis.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}-pre-statis"
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