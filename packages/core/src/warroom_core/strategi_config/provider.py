"""Provider data candle per market — abstraksi sumber data untuk strategy.

Kenapa: screener & paper bot butuh data TERKINI (bukan hanya CSV historis).
Provider menyembunyikan dari mana candle berasal, sehingga formula engine tetap
market-agnostic: strategy menyebut simbol + timeframe, provider mengambil datanya.

Provider yang tersedia:
- BinanceProvider : crypto & memecoin yang terdaftar di Binance (BTC, ETH, SOL,
  PEPE, WIF, BONK, ...). Sumber: REST klines Binance (spot).

Antarmuka terbuka: market lain (polymarket = odds, memecoin on-chain via GMGN)
bisa ditambah sebagai Provider baru tanpa mengubah engine — asal mengembalikan
list candle OHLCV. Ini kunci "all market" tanpa memaksa satu skema data.
"""
from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod

Candle = dict[str, float]


class DataProvider(ABC):
    """Kontrak provider candle OHLCV."""

    @abstractmethod
    def candles(self, simbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        """Ambil `limit` candle terakhir (tertua -> terbaru)."""


class BinanceProvider(DataProvider):
    """Candle spot Binance. Mendukung simbol crypto & memecoin terdaftar."""

    BASE = "https://api.binance.com/api/v3/klines"

    def candles(self, simbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        url = f"{self.BASE}?symbol={simbol}&interval={timeframe}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "warroom-screener/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        out: list[Candle] = []
        for k in data:
            out.append({
                "time": float(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        return out


def provider_untuk(market: str) -> DataProvider:
    """Pilih provider berdasar market. Fail-closed: market tak dikenal -> error."""
    market = (market or "").lower()
    if market in ("crypto", "memecoin"):
        # memecoin terdaftar di Binance (PEPEUSDT, WIFUSDT, ...) pakai sumber sama.
        return BinanceProvider()
    raise ValueError(f"market belum didukung provider-nya: {market!r}")
