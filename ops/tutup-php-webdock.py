#!/usr/bin/env python3
"""Tutup permukaan PHP di vhost domain bawaan Webdock.

Dasar (terverifikasi 2026-11-09):
- php8.3-fpm inactive + disabled, /var/run/php kosong -> `location ~ \\.php$`
  selalu 502; 401 yang terlihat hanya basic-auth di level server.
- /var/www/html/index.php = "Webdock Welcome Page - YOU SHOULD DELETE THIS FILE".
- /filemanager.php: 1 hit dalam 39 hari log, dari bot pemindai WordPress (404).
- Certbot domain ini pakai authenticator=nginx (plugin), tidak butuh PHP/webroot.

Aman diulang. Pakai: sudo python3 ops/tutup-php-webdock.py [--dry-run]
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
DOCROOT = Path("/var/www/html")
PARKED = Path("/var/backups/www-html-php-parked")
MARK = "# [20261109] permukaan PHP ditutup: php-fpm inactive, file tak terpakai."


def fail(msg: str) -> None:
    print(f"GAGAL: {msg}", file=sys.stderr)
    sys.exit(1)


def strip_php_location(text: str) -> tuple[str, str]:
    """Buang blok `location ~ \\.php$ { ... }` (kurawal berimbang)."""
    m = re.search(r"(?m)^[ \t]*location\s*~\s*\\\.php\$\s*\{", text)
    if not m:
        return text, ""
    start = m.start()
    i = text.index("{", m.start()) + 1
    depth = 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    removed = text[start:i]
    return text[:start] + MARK + "\n" + text[i:], removed


def main() -> None:
    dry = "--dry-run" in sys.argv
    if not CONF.exists():
        fail(f"{CONF} tidak ada")
    text = CONF.read_text()
    if MARK in text:
        print("Sudah diterapkan sebelumnya — tidak ada perubahan.")
        return

    new, removed = strip_php_location(text)
    if not removed:
        fail("blok `location ~ \\.php$` tidak ditemukan — periksa manual")
    # `error_page 404 /index.php` akan menunjuk file yang tak lagi dilayani.
    before = new
    new = re.sub(r"(?m)^[ \t]*error_page\s+404\s+/index\.php;\s*\n", "", new)
    dropped_errpage = before != new

    print("=== blok PHP yang dibuang ===")
    print(removed.rstrip())
    print(f"\n=== error_page 404 /index.php dibuang: {dropped_errpage} ===")
    print(f"kurawal seimbang: {new.count('{')}/{new.count('}')}")

    if dry:
        print("\n[dry-run] tidak menulis apa pun.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"webdock.bak-{stamp}-pre-php-off"
    shutil.copy2(CONF, backup)
    print(f"backup config: {backup}")

    CONF.write_text(new)
    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        shutil.copy2(backup, CONF)
        print(test.stderr, file=sys.stderr)
        fail("nginx -t gagal — config dikembalikan")

    # Parkir berkas PHP (bukan hapus) supaya bisa dipulihkan.
    PARKED.mkdir(parents=True, exist_ok=True)
    for name in ("filemanager.php", "index.php"):
        src = DOCROOT / name
        if src.exists():
            shutil.move(str(src), str(PARKED / name))
            print(f"diparkir: {src} -> {PARKED / name}")

    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print("nginx direload. Verifikasi yang diharapkan:")
    print("  /filemanager.php -> 404   /index.php -> 404")
    print("  / -> 200   /api/v1/health -> 401   /masuk -> 200")


if __name__ == "__main__":
    main()