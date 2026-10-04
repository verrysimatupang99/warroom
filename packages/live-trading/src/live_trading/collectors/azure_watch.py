"""Watchdog kesegaran radar Azure (baca-saja, tanpa ubah jadwal di sana)."""

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
