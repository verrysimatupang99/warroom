"""Pemetaan support/resistance (SNR) untuk filter penempatan SL.

Latar belakang: level sinyal War Room diturunkan dari jarak ATR, bukan dari struktur
harga. Akibatnya SL bisa mendarat **di dalam** zona likuiditas dan mudah disapu —
pola yang terlihat pada data crypto (`sl-placement` win rate 3,1%, SL rata-rata -1,12R).

Modul ini murni perhitungan: tidak mengubah keputusan apa pun sampai dipakai eksplisit
oleh pemanggil. Tujuannya menyediakan bahan untuk **mengukur** dulu, bukan langsung
memblokir.

Semua fungsi deterministik dan bebas I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Zona:
    """Satu pita support/resistance hasil pengelompokan swing."""

    bawah: float
    atas: float
    sentuhan: int
    jenis: str  # "support" | "resistance"

    @property
    def tengah(self) -> float:
        return (self.bawah + self.atas) / 2

    @property
    def lebar(self) -> float:
        return self.atas - self.bawah


def deteksi_swing(
    candles: Sequence[dict[str, Any]], kiri: int = 3, kanan: int = 3
) -> tuple[list[float], list[float]]:
    """Kembalikan (swing_high, swing_low) memakai aturan fraktal.

    Sebuah titik disebut swing high bila `high`-nya adalah nilai tertinggi pada
    jendela [i-kiri, i+kanan]. Cara yang sama dipakai untuk swing low.
    """
    highs: list[float] = []
    lows: list[float] = []
    n = len(candles)
    if n < kiri + kanan + 1:
        return highs, lows
    for i in range(kiri, n - kanan):
        window = candles[i - kiri : i + kanan + 1]
        h = candles[i]["h"]
        lo = candles[i]["l"]
        if h >= max(c["h"] for c in window):
            highs.append(float(h))
        if lo <= min(c["l"] for c in window):
            lows.append(float(lo))
    return highs, lows


def bangun_zona(
    levels: Sequence[float], toleransi: float, jenis: str
) -> list[Zona]:
    """Kelompokkan level yang berdekatan menjadi zona.

    Level dianggap satu zona bila jaraknya <= `toleransi` dari pusat zona berjalan.
    Zona dengan satu sentuhan tetap dikembalikan (bisa jadi level penting), tapi
    pemanggil bebas menyaring lewat `sentuhan`.
    """
    if not levels:
        return []
    urut = sorted(float(x) for x in levels)
    grup: list[list[float]] = [[urut[0]]]
    for lv in urut[1:]:
        pusat = sum(grup[-1]) / len(grup[-1])
        if abs(lv - pusat) <= toleransi:
            grup[-1].append(lv)
        else:
            grup.append([lv])
    return [
        Zona(bawah=min(g), atas=max(g), sentuhan=len(g), jenis=jenis) for g in grup
    ]


def peta_snr(
    candles: Sequence[dict[str, Any]], atr: float, toleransi_atr: float = 0.6
) -> list[Zona]:
    """Bangun peta zona support/resistance dari candle yang sudah ada."""
    if atr <= 0:
        return []
    highs, lows = deteksi_swing(candles)
    tol = atr * toleransi_atr
    return bangun_zona(highs, tol, "resistance") + bangun_zona(lows, tol, "support")


def zona_mengandung(zona: Zona, harga: float, buffer: float = 0.0) -> bool:
    """True bila `harga` berada di dalam (atau sangat dekat) zona."""
    return (zona.bawah - buffer) <= harga <= (zona.atas + buffer)


def sl_terlindungi(
    entry: float, sl: float, zonas: Sequence[Zona], buffer: float
) -> tuple[bool, str]:
    """Apakah SL berada di sisi aman dari zona terdekat?

    LONG  : SL harus **di bawah** zona support terdekat (dengan buffer).
    SHORT : SL harus **di atas** zona resistance terdekat (dengan buffer).

    Bila SL justru berada di dalam zona, posisi dianggap rentan disapu.
    """
    arah = 1 if sl < entry else -1
    relevan = [
        z
        for z in zonas
        if (arah == 1 and z.bawah < entry) or (arah == -1 and z.atas > entry)
    ]
    if not relevan:
        return True, "tidak ada zona relevan"

    if arah == 1:
        dekat = max(relevan, key=lambda z: z.atas)
        if zona_mengandung(dekat, sl, buffer):
            return False, f"SL di dalam zona support {dekat.bawah:.2f}-{dekat.atas:.2f}"
        if sl > dekat.atas:
            return False, f"SL di atas support {dekat.atas:.2f} (belum tembus zona)"
        return True, f"SL di bawah support {dekat.bawah:.2f}"

    dekat = min(relevan, key=lambda z: z.bawah)
    if zona_mengandung(dekat, sl, buffer):
        return False, f"SL di dalam zona resistance {dekat.bawah:.2f}-{dekat.atas:.2f}"
    if sl < dekat.bawah:
        return False, f"SL di bawah resistance {dekat.bawah:.2f} (belum tembus zona)"
    return True, f"SL di atas resistance {dekat.atas:.2f}"
