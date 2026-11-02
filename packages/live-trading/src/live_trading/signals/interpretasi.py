"""Lapisan interpretasi deterministik untuk mengeksekusi Golden Pullback di data historis.

`golden_pullback.build_pullback_setup()` sengaja tidak membaca pasar sendiri: ia menerima
`structure_bias`, `liquidity_swept`, dan `confirmation` sebagai fakta dari pemanggil.
Di trading nyata fakta itu datang dari analis. Untuk riset kita butuh padanan mekanis,
dan modul ini menyediakannya tanpa memilih parameter yang membuat hasilnya bagus.

Aturan (dipilih demi kesederhanaan, bukan demi performa):

- **Impulse**: swing high/low terakhir dari jendela `lookback` candle.
- **structure_bias**: dari hubungan close terhadap EMA `trend_ema`.
- **liquidity_swept**: candle terakhir menembus low/high swing sebelumnya lalu menutup
  kembali ke dalam rentangnya (sweep klasik).
- **confirmation**: candle terakhir menutup searah bias (bullish = close > open).

Modul ini murni fungsi: tanpa jaringan, tanpa efek samping, tanpa penyimpanan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from live_trading.signals.golden_pullback import (
    GoldenPullbackConfig,
    build_pullback_setup,
)

Direction = Literal["long", "short"]


@dataclass(frozen=True, slots=True)
class InterpretasiConfig:
    """Parameter yang boleh diubah — dan untuk uji sensitivitas harus diubah."""

    lookback: int = 40
    trend_ema: int = 50
    warmup: int = 60

    def __post_init__(self) -> None:
        if self.lookback < 5:
            msg = "lookback minimal 5 candle"
            raise ValueError(msg)
        if self.trend_ema < 5:
            msg = "trend_ema minimal 5"
            raise ValueError(msg)
        if self.warmup < max(self.lookback, self.trend_ema):
            msg = "warmup harus >= max(lookback, trend_ema)"
            raise ValueError(msg)


def ema(nilai: list[float], periode: int) -> list[float | None]:
    """EMA klasik; None selama periode belum lengkap supaya tidak menebak."""
    if periode <= 0:
        msg = "periode EMA harus positif"
        raise ValueError(msg)
    hasil: list[float | None] = [None] * len(nilai)
    if len(nilai) < periode:
        return hasil
    k = 2 / (periode + 1)
    acc = sum(nilai[:periode]) / periode
    hasil[periode - 1] = acc
    for i in range(periode, len(nilai)):
        acc = nilai[i] * k + acc * (1 - k)
        hasil[i] = acc
    return hasil


def _swing(high: list[float], low: list[float], i: int, lookback: int) -> tuple[float, float]:
    """Swing dari candle *sebelum* `i`.

    Candle `i` sengaja dikeluarkan: bila ia sendiri yang menembus low, memakai
    low-nya sebagai stop membuat stop menempel di harga entry (jarak nyaris nol)
    sehingga SL kena oleh noise biasa. Level yang benar adalah ekstrem baseline.
    """
    a = max(0, i - lookback)
    if i == 0 or a >= i:
        return low[min(i, len(low) - 1)], high[min(i, len(high) - 1)]
    return min(low[a:i]), max(high[a:i])


def baca_konteks(
    bar: dict[str, Any],
    *,
    high: list[float],
    low: list[float],
    close: list[float],
    open_: list[float],
    ema_garis: list[float | None],
    i: int,
    cfg: InterpretasiConfig,
) -> dict[str, Any]:
    """Terjemahkan state pasar menjadi fakta yang diterima `build_pullback_setup`."""
    e = ema_garis[i]
    bias = "netral"
    if e is not None:
        if close[i] > e:
            bias = "bullish"
        elif close[i] < e:
            bias = "bearish"

    # Swing pembanding: jendela sebelum candle terakhir, agar sweep benar-benar
    # berarti "menembus level lama", bukan menembus dirinya sendiri.
    swing_low, swing_high = _swing(high, low, i, cfg.lookback)

    swept_long = low[i] < swing_low and close[i] > swing_low
    swept_short = high[i] > swing_high and close[i] < swing_high
    konfirmasi_long = close[i] > open_[i]
    konfirmasi_short = close[i] < open_[i]

    return {
        "bias": bias,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "swept_long": swept_long,
        "swept_short": swept_short,
        "konfirmasi_long": konfirmasi_long,
        "konfirmasi_short": konfirmasi_short,
        "bar": bar,
    }


def sinyal_dari_bar(
    ctx: dict[str, Any],
    *,
    cfg_interpretasi: InterpretasiConfig | None = None,
    cfg_golden: GoldenPullbackConfig | None = None,
) -> dict[str, Any] | None:
    """Kembalikan setup lengkap (dengan SL/TP) bila semua gate lolos, selain itu None."""
    ci = cfg_interpretasi or InterpretasiConfig()
    harga = float(ctx["bar"]["close"])
    kandidat: list[Direction] = []
    if ctx["bias"] == "bullish" and ctx["swept_long"] and ctx["konfirmasi_long"]:
        kandidat.append("long")
    if ctx["bias"] == "bearish" and ctx["swept_short"] and ctx["konfirmasi_short"]:
        kandidat.append("short")

    for arah in kandidat:
        setup = build_pullback_setup(
            direction=arah,
            swing_low=float(ctx["swing_low"]),
            swing_high=float(ctx["swing_high"]),
            current_price=harga,
            structure_bias=ctx["bias"],
            liquidity_swept=True,
            confirmation=True,
            config=cfg_golden,
        )
        if setup is not None:
            setup["timeframe_lookback"] = ci.lookback
            return setup
    return None
