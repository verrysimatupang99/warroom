"""Indikator dasar — dipakai bersama oleh forex dan mesin sinyal.

Dulu `ema`/`atr` hanya ada di `collectors/forex.py`. Begitu mesin SMC membutuhkannya
juga, menyalinnya berarti dua definisi ATR yang bisa berbeda diam-diam. Semua di sini.
"""

from __future__ import annotations


def ema(values: list[float], period: int) -> float | None:
    """EMA klasik. ``None`` kalau data kurang — bukan menebak dengan data parsial."""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """ATR Wilder sederhana. TR = max(range, |high-prevClose|, |low-prevClose|)."""
    if len(closes) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(closes)):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return sum(trs[-period:]) / period


def atr_pct(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """ATR sebagai persen harga terakhir — satuan yang dipakai aturan lapangan."""
    a = atr(highs, lows, closes, period)
    if a is None or not closes or closes[-1] <= 0:
        return None
    return a / closes[-1] * 100.0
