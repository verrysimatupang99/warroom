#!/usr/bin/env python3
"""Buka /bus/ di vhost domain bawaan Webdock -> warroom-bus :8810.

Terpisah dari blok lain karena sengaja TIDAK memakai basic auth: kliennya
agent di mesin lain yang tidak punya kredensial nginx. Auth memakai header
X-Bus-Token (dicek server), dan hanya path /bus/ yang terbuka.

Aman diulang. Pakai: sudo python3 ops/buka-bus.py [--dry-run]
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
MARK = "# [20261109] bus diskusi lintas agent: /bus/ -> :8810, auth header bukan basic."

BLOCK = f"""        {MARK}
        location ^~ /bus/ {{
            auth_basic off;
            proxy_pass http://127.0.0.1:8810;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
            client_max_body_size 2m;
        }}
"""


def fail(m: str) -> None:
    print(f"GAGAL: {m}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    dry = "--dry-run" in sys.argv
    text = CONF.read_text()
    if MARK in text:
        print("Sudah diterapkan — tidak ada perubahan.")
        return
    m = re.search(r"(?m)^[ \t]*location /api/v1/ \{\n", text)
    if not m:
        fail("`location /api/v1/` tidak ditemukan sebagai jangkar")
    text = text[:m.start()] + BLOCK + "\n" + text[m.start():]
    print(f"kurawal: {text.count('{')}/{text.count('}')}")
    if dry:
        print("[dry-run] tidak menulis.")
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    b = BACKUP_DIR / f"webdock.bak-{stamp}-pre-bus"
    shutil.copy2(CONF, b)
    CONF.write_text(text)
    t = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if t.returncode != 0:
        shutil.copy2(b, CONF)
        print(t.stderr, file=sys.stderr)
        fail("nginx -t gagal — dikembalikan")
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print(f"backup: {b}\nnginx direload.")


if __name__ == "__main__":
    main()