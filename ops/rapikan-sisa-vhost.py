#!/usr/bin/env python3
"""Rapikan sisa vhost domain bawaan Webdock setelah app jadi root.

1. Tambah `location ^~ /legacy/` -> alias /var/www/html dengan basic auth.
   Docroot lama tetap berisi snapshot dashboard (index.html, war-room.js,
   data.json, analytics.json, wallet-info.json, ea_files/) yang disegarkan
   poly-dashboard-sync.timer tiap 2 menit. Tanpa ini, data itu jadi 404 padahal
   masih diproduksi.
2. Nonaktifkan route yang upstream-nya sudah mati (502): /9router/ -> :20128,
   /agent/ -> :8790. Dikomentari, bukan dihapus, dengan catatan tanggal.

Aman diulang. Pakai: sudo python3 ops/rapikan-sisa-vhost.py [--dry-run]
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
MARK = "# [20261109] /legacy/ = snapshot statis lama, ber-basic-auth."

LEGACY_BLOCK = f"""        {MARK}
        # Snapshot dashboard lama (dulu jadi root). Masih disegarkan
        # poly-dashboard-sync.timer, jadi tetap disajikan di path eksplisit.
        location ^~ /legacy/ {{
            auth_basic "War Room";
            auth_basic_user_file /etc/nginx/.htpasswd-warroom;
            alias /var/www/html/;
            autoindex off;
            try_files $uri $uri/ =404;
        }}
"""


def fail(msg: str) -> None:
    print(f"GAGAL: {msg}", file=sys.stderr)
    sys.exit(1)


def block_span(text: str, pattern: str) -> tuple[int, int] | None:
    m = re.search(pattern, text)
    if not m:
        return None
    i = text.index("{", m.start()) + 1
    depth = 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return m.start(), i


def main() -> None:
    dry = "--dry-run" in sys.argv
    text = CONF.read_text()
    changed = []

    if MARK not in text:
        span = block_span(text, r"(?m)^[ \t]*location / \{\n")
        if not span:
            fail("`location /` tidak ditemukan")
        _, end = span
        text = text[:end] + "\n" + LEGACY_BLOCK + text[end:]
        changed.append("tambah /legacy/")
    else:
        print("  /legacy/ sudah ada")

    # Komentari route mati. Blok berbentuk `location /9router/ {` dan `location /agent/ {`.
    for name, pat in (("/9router/", r"(?m)^[ \t]*location /9router/ \{\n"),
                      ("/agent/", r"(?m)^[ \t]*location\s+/agent/\s*\{\n")):
        span = block_span(text, pat)
        if not span:
            print(f"  {name}: tidak ditemukan (mungkin sudah dikomentari)")
            continue
        start, end = span
        if text[max(0, start - 40):start].count("#"):
            print(f"  {name}: sudah dikomentari")
            continue
        body = text[start:end]
        commented = "# [20261109] dinonaktifkan: upstream sudah tidak listen -> 502.\n" + "\n".join(
            ("# " + ln) if ln.strip() else ln for ln in body.rstrip().split("\n")
        ) + "\n"
        text = text[:start] + commented + text[end:]
        changed.append(f"komentari {name}")

    if not changed:
        print("Tidak ada perubahan.")
        return
    print("Perubahan:", ", ".join(changed))
    print(f"kurawal seimbang: {text.count('{')}/{text.count('}')}")

    if dry:
        print("[dry-run] tidak menulis apa pun.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}-pre-rapikan"
    shutil.copy2(CONF, backup)
    CONF.write_text(text)

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        shutil.copy2(backup, CONF)
        print(test.stderr, file=sys.stderr)
        fail("nginx -t gagal — config dikembalikan")
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print(f"backup: {backup}\nnginx direload.")


if __name__ == "__main__":
    main()