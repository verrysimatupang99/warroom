"""Pembatas laju sederhana (in-process, per proses).

Cukup untuk host satu proses (uvicorn tanpa `--workers`). Bila kelak dijalankan
multi-proses, ganti backend hitungan dengan Redis — API-nya sengaja kecil supaya
penggantian itu tetap lokal.

Kenapa jendela geser (bukan penghitung per menit): penghitung per menit bisa
dilewati dengan menembak di batas menit (2N permintaan dalam 2 detik). Jendela
geser menahan laju sebenarnya.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

__all__ = ["Limiter", "batas_dari_env"]


def batas_dari_env(nama: str, bawaan: int) -> int:
    """Baca batas per menit dari env; nilai tak sah → bawaan (jangan pernah matikan)."""
    mentah = (nama and __import__("os").environ.get(nama)) or ""
    try:
        nilai = int(mentah)
    except (TypeError, ValueError):
        return bawaan
    return nilai if nilai > 0 else bawaan


class Limiter:
    """Jendela geser per kunci (mis. per IP atau per username)."""

    def __init__(self, batas: int, jendela_s: float = 60.0) -> None:
        if batas <= 0:
            raise ValueError("batas harus > 0")
        self.batas = batas
        self.jendela_s = jendela_s
        self._kunci: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _bersihkan_kadaluwarsa(self, t: float) -> None:
        batas_bawah = t - self.jendela_s
        kunci_hapus = [k for k, q in self._kunci.items() if not q or q[-1] <= batas_bawah]
        for k in kunci_hapus:
            del self._kunci[k]

    def izinkan(self, kunci: str, *, sekarang: float | None = None) -> bool:
        """True bila permintaan boleh lanjut; catat waktunya bila boleh."""
        t = time.monotonic() if sekarang is None else sekarang
        with self._lock:
            if len(self._kunci) >= 1000:
                self._bersihkan_kadaluwarsa(t)
            q = self._kunci.setdefault(kunci, deque())
            batas_bawah = t - self.jendela_s
            while q and q[0] <= batas_bawah:
                q.popleft()
            if len(q) >= self.batas:
                return False
            q.append(t)
            return True

    def reset(self) -> None:
        with self._lock:
            self._kunci.clear()
