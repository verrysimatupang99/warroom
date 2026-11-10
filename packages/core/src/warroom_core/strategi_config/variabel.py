"""Indikator teknikal untuk layer konfigurasi strategy (crypto & umum).

Semua fungsi menerima daftar candle (dict dengan kunci open/high/low/close/volume)
dan mengembalikan daftar float sepanjang candle. Nilai yang belum bisa dihitung
(mis. EMA butuh periode awal) diisi None agar sejajar indeks candle.

Desain: murni fungsi, tanpa state, tanpa I/O. Dipakai VariableProvider untuk
menghitung variabel yang dirujuk formula strategy.
"""
from __future__ import annotations

from typing import Any

Candle = dict[str, Any]


def _closes(candles: list[Candle]) -> list[float]:
    return [float(c["close"]) for c in candles]


def sma(candles: list[Candle], period: int) -> list[float | None]:
    """Simple Moving Average dari close."""
    closes = _closes(candles)
    out: list[float | None] = [None] * len(closes)
    if period <= 0:
        return out
    jumlah = 0.0
    for i, c in enumerate(closes):
        jumlah += c
        if i >= period:
            jumlah -= closes[i - period]
        if i >= period - 1:
            out[i] = jumlah / period
    return out


def ema(candles: list[Candle], period: int) -> list[float | None]:
    """Exponential Moving Average dari close. Seed = SMA periode pertama."""
    closes = _closes(candles)
    out: list[float | None] = [None] * len(closes)
    if period <= 0 or len(closes) < period:
        return out
    k = 2.0 / (period + 1.0)
    # seed dengan SMA periode pertama
    seed = sum(closes[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(closes)):
        prev = closes[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def _rsi_wilder(candles: list[Candle], period: int) -> list[float | None]:
    """RSI metode Wilder (standar)."""
    closes = _closes(candles)
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_dari(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_dari(avg_gain, avg_loss)
    return out


def _rsi_dari(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
    """Average True Range (metode Wilder). Butuh high/low/close."""
    out: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return out
    trs: list[float] = []
    for i in range(len(candles)):
        h = float(candles[i]["high"])
        lo = float(candles[i]["low"])
        if i == 0:
            trs.append(h - lo)
        else:
            pc = float(candles[i - 1]["close"])
            trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    # seed = rata-rata TR periode pertama
    prev = sum(trs[1:period + 1]) / period
    out[period] = prev
    for i in range(period + 1, len(candles)):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def highest(candles: list[Candle], period: int) -> list[float | None]:
    """Highest high dari `period` candle SEBELUM baris ini (mengecualikan baris ini).

    Dipakai untuk breakout: close > highest(N) berarti menembus tertinggi N bar sebelumnya.
    """
    out: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        if i < period:
            continue
        jendela = candles[i - period:i]
        out[i] = max(float(c["high"]) for c in jendela)
    return out


def lowest(candles: list[Candle], period: int) -> list[float | None]:
    """Lowest low dari `period` candle SEBELUM baris ini (mengecualikan baris ini)."""
    out: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        if i < period:
            continue
        jendela = candles[i - period:i]
        out[i] = min(float(c["low"]) for c in jendela)
    return out


# Registry indikator yang boleh dirujuk formula (whitelist).
INDIKATOR = {
    "SMA": sma,
    "EMA": ema,
    "RSI": _rsi_wilder,
    "ATR": atr,
    "HIGHEST": highest,
    "LOWEST": lowest,
}

# Alias publik untuk pemakaian langsung (test / provider).
rsi = _rsi_wilder
