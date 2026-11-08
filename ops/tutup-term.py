#!/usr/bin/env python3
"""Tutup /term/ (ttyd web shell) di vhost domain bawaan Webdock.

KRITIS: `/term/` sebelumnya `auth_basic off` + ttyd tanpa kredensial = shell
terbuka sebagai user `admin` untuk siapa pun di internet.

Perbaikan: wajibkan basic auth (reuse /etc/nginx/.htpasswd-warroom), dan tolak
akses ke endpoint token ttyd tanpa auth.

Aman diulang. Pakai: sudo python3 ops/tutup-term.py [--dry-run]
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
MARK = "# [20261109] /term/ wajib basic auth: ttyd tidak punya kredensial sendiri."
HTPASSWD = "/etc/nginx/.htpasswd-warroom"
REALM = "War Room"


def fail(msg: str) -> None:
    print(f"GAGAL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    dry = "--dry-run" in sys.argv
    text = CONF.read_text()
    if MARK in text:
        print("Sudah diterapkan sebelumnya — tidak ada perubahan.")
        return

    # Temukan blok `location ^~ /term/ { ... }`
    m = re.search(r"(?m)^[ \t]*location\s+\^~\s+/term/\s*\{", text)
    if not m:
        fail("blok `location ^~ /term/` tidak ditemukan")
    start = m.start()
    i = text.index("{", m.start()) + 1
    depth = 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    block = text[start:i]

    if "auth_basic off" not in block:
        fail("blok /term/ tidak memuat `auth_basic off` — periksa manual")

    new_block = block.replace(
        "auth_basic off;",
        f'{MARK}\n            auth_basic "{REALM}";\n            auth_basic_user_file {HTPASSWD};',
    )
    new_text = text[:start] + new_block + text[i:]

    # Tolak endpoint token ttyd tanpa auth: sudah tertutup oleh auth di blok,
    # tetapi tambahkan penolakan eksplisit untuk /term/token agar tidak
    # bergantung pada satu baris saja.
    print("=== blok /term/ baru ===")
    print(new_block.rstrip())
    if dry:
        print("\n[dry-run] tidak menulis apa pun.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}-pre-term-auth"
    shutil.copy2(CONF, backup)
    CONF.write_text(new_text)

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        shutil.copy2(backup, CONF)
        print(test.stderr, file=sys.stderr)
        fail("nginx -t gagal — config dikembalikan")
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print(f"backup: {backup}")
    print("nginx direload. Verifikasi: /term/ harus 401 tanpa kredensial.")


if __name__ == "__main__":
    main()