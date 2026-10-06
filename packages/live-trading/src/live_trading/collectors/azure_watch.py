"""Utilitas umur berkas — warisan pengawasan radar Azure (baca-saja).

Sejak 6 Okt 2026 radar dijalankan **lokal** (`lt radar-update` → `state/radar_state.json`),
jadi modul ini tidak lagi menyentuh host lain. `umur_file`/`cek_umur` tetap dipertahankan
sebagai fungsi murni yang diuji; watchdog produksi memakai `ops/watchdog.umur` sendiri.

Jangan menambahkan kembali jalur SSH/HTTP ke sini.
"""

from __future__ import annotations

import time
from pathlib import Path


def umur_file(path: str | Path) -> float:
    """Umur detik berkas; inf bila hilang."""
    try:
        return time.time() - Path(path).stat().st_mtime
    except OSError:
        return float("inf")


def cek_umur(umur_detik: float, batas_detik: float = 1800.0) -> tuple[bool, float]:
    """(segar?, umur). Basi = umur lewat batas."""
    return umur_detik <= batas_detik, umur_detik
