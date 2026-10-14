#!/usr/bin/env python3
"""Pastikan skema DB sudah di revisi head alembic.

Mencegah kejadian 14 Okt 2026: kode (kolom `users.totp_last_counter`, rename job)
sudah merge TAPI migrasi belum diterapkan -> produksi tertinggal 3 revisi selama
berhari-hari.

Pakai:
    python ops/check-db-head.py            # bandingkan saja (gagal bila tertinggal)
    python ops/check-db-head.py --upgrade  # jalankan `alembic upgrade head` lalu cek

Butuh env WARROOM_DB_URL. Bila tak ada -> keluar 0 dengan catatan (skenario CI
tanpa DB), supaya tidak berpura-pura lulus DAN tidak memblok CI tanpa DB.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "packages" / "core" / "alembic.ini"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def main() -> int:
    if not os.environ.get("WARROOM_DB_URL"):
        print("LEWAT: WARROOM_DB_URL tidak diset — cek head dilewati (bukan lulus).")
        return 0

    if "--upgrade" in sys.argv:
        up = _run(["upgrade", "head"])
        if up.returncode != 0:
            print("GAGAL: alembic upgrade head error:\n" + (up.stderr or up.stdout))
            return 1
        print(up.stderr.strip().splitlines()[-1] if up.stderr else "upgrade ok")

    cur = _run(["current"])
    heads = _run(["heads"])
    # 'alembic current' mencetak baris "[alembic] target: ..." ke stdout — buang.
    cur_rev = "(kosong)"
    for line in reversed((cur.stdout or "").splitlines()):
        s = line.strip()
        if s and not s.startswith("[alembic]") and not s.startswith("INFO"):
            cur_rev = s.split()[0]
            break
    head_rev = ""
    for line in (heads.stdout or "").splitlines():
        s = line.strip()
        if s and not s.startswith("[alembic]") and not s.startswith("INFO") and not s.startswith("Rev:"):
            head_rev = s.split()[0]
            break

    if not head_rev:
        print("GAGAL: tak bisa menentukan head alembic.")
        return 1
    if cur_rev != head_rev:
        print(f"GAGAL: DB di {cur_rev}, bukan head {head_rev} — migrasi belum diterapkan.")
        print("  Jalankan: bash ops/check-db-head.py --upgrade")
        return 1
    print(f"OK: DB di head {head_rev}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
