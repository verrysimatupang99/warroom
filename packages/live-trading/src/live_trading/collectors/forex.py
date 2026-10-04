"""Kolektor forex — XAUUSD (TVC:GOLD).

Diwarisi dari ``xauusd_smc_data.py`` (Tencent). Data dibaca dari dua jalur
TradingView:

* **quote** — endpoint HTTP ``scanner.tradingview.com`` (cepat, cukup untuk
  harga & range harian);
* **candles** — websocket chart TradingView lewat ``tv_feed.py`` (dipanggil
  sebagai subprocess karena butuh koneksi websocket berumur pendek).

Sengaja memakai **TVC:GOLD** (spot gold CFD) dan bukan futures COMEX: futures
membawa premi contango 50–60 poin, yang menggeser level struktur.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from . import make_client

SYMBOL = "TVC:GOLD"
_QUOTE_FIELDS = [
    "close",
    "open",
    "high",
    "low",
    "change",
    "description",
    "price_52_week_high",
    "price_52_week_low",
]
TV_FEED = Path(__file__).with_name("tv_feed.py")


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
    """ATR Wilder sederhana dari deret OHLC yang sejajar."""
    if len(closes) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


@dataclass
class ForexCollector:
    settings: Settings
    symbol: str = SYMBOL
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        self._client = self.client or make_client()

    # -------------------------------------------------------------- quote HTTP
    def quote(self) -> dict[str, Any]:
        url = (
            f"{self.settings.tradingview_scanner}/symbol"
            f"?symbol={self.symbol.replace(':', '%3A')}"
            f"&fields={','.join(_QUOTE_FIELDS)}&no_404=true"
        )
        r = self._client.get(url)
        r.raise_for_status()
        data = r.json()
        data["symbol"] = self.symbol
        return data

    # ---------------------------------------------------------- candles (WS)
    def candles(self, resolution: str = "60", bars: int = 120) -> list[dict[str, Any]]:
        """OHLC dari websocket TradingView via ``tv_feed.py``."""
        proc = subprocess.run(  # noqa: S603 — skrip internal, argumen terkontrol
            [sys.executable, str(TV_FEED), self.symbol, resolution, str(bars)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise RuntimeError(f"tv_feed gagal: {(proc.stderr or 'kosong').strip()[-200:]}")
        return json.loads(proc.stdout)

    # ----------------------------------------------------------------- struktur
    def structure(self, resolution: str = "60", bars: int = 120) -> dict[str, Any]:
        """Ringkas struktur dari candle: harga, EMA20/50, ATR14, bias.

        ``tv_feed`` mengembalikan bar ringkas ``{t,o,h,l,c,v}`` — bukan nama panjang.
        """
        rows = self.candles(resolution, bars)
        if not rows:
            raise RuntimeError("tv_feed tidak mengembalikan candle")
        closes = [float(r["c"]) for r in rows]
        highs = [float(r["h"]) for r in rows]
        lows = [float(r["l"]) for r in rows]

        e20, e50 = ema(closes, 20), ema(closes, 50)
        a14 = atr(highs, lows, closes, 14)
        last = closes[-1] if closes else None

        bias = "netral"
        if e20 is not None and e50 is not None and last is not None:
            if last > e20 > e50:
                bias = "bullish"
            elif last < e20 < e50:
                bias = "bearish"

        return {
            "symbol": self.symbol,
            "resolution": resolution,
            "bars": len(rows),
            "close": last,
            "ema20": round(e20, 2) if e20 else None,
            "ema50": round(e50, 2) if e50 else None,
            "atr14": round(a14, 2) if a14 else None,
            "atr_pct": round(a14 / last * 100, 2) if a14 and last else None,
            "bias": bias,
        }
