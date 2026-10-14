#!/usr/bin/env python3
"""Cek anggaran baris per berkas Python — cegah file raksasa muncul lagi.

Ambang: 800 baris (warning) / 1000 (gagal). Kecualikan berkas yang SUDAH besar &
sengaja dibiarkan (page_parts.py = string HTML dashboard lama), dengan catatan.

Pakai: python ops/check-file-size.py
Keluar 1 bila ada berkas > BATAS_GAGAL (dan tidak dikecualikan).
"""
from __future__ import annotations

from pathlib import Path

BATAS_GAGAL = 1000
BATAS_PERINGATAN = 800

# Berkas yang sudah besar & sengaja dibiarkan (dicatat, bukan disembunyikan).
DIKECUALIKAN = {
    "packages/live-trading/src/live_trading/dashboard/page_parts.py": (
        "string HTML dashboard lama; pemecahan lanjut = utang terpisah (Poin 1)"
    ),
    "packages/live-trading/src/live_trading/cli.py": (
        "kumpulan handler argparse cmd_* (satu fungsi per subperintah); "
        "pecah = PR tersendiri, bukan mendesak"
    ),
}

ROOT = Path(__file__).resolve().parents[1]

# Kode warisan yang juga dikecualikan dari ruff (vendor/crypto = Tencent).
DILEWATI_BAGIAN = {"idx616", "vendor", "crypto", "__pycache__", ".venv"}


def iter_py():
    for base in ("packages", "services", "ops"):
        for p in (ROOT / base).rglob("*.py"):
            if DILEWATI_BAGIAN.intersection(p.parts):
                continue
            yield p


def main() -> int:
    gagal: list[tuple[Path, int]] = []
    peringatan: list[tuple[Path, int]] = []
    for p in iter_py():
        rel = p.relative_to(ROOT).as_posix()
        n = len(p.read_text(encoding="utf-8").splitlines())
        if rel in DIKECUALIKAN:
            continue
        if n > BATAS_GAGAL:
            gagal.append((p.relative_to(ROOT), n))
        elif n > BATAS_PERINGATAN:
            peringatan.append((p.relative_to(ROOT), n))

    for p, n in sorted(peringatan, key=lambda x: -x[1]):
        print(f"  PERINGATAN {n:>5} baris: {p}")
    for p, n in sorted(gagal, key=lambda x: -x[1]):
        print(f"  GAGAL      {n:>5} baris: {p}")

    if gagal:
        print(
            f"\n{len(gagal)} berkas lewat {BATAS_GAGAL} baris — "
            "pecah atau tambahkan ke DIKECUALIKAN dengan alasan."
        )
        return 1
    print(f"\nAnggaran baris OK (peringatan: {len(peringatan)}, gagal: 0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
