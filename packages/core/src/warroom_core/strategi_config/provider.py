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
import os
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime

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



class OpenMarketProvider(DataProvider):
    """Candle via OpenMarket unified API (lintas 40+ venue).

    Satu API key -> akses Binance, Bybit, OKX, Hyperliquid, Coinbase, CME, dll
    lewat satu skema. Butuh OPENMARKET_API_KEY (dari openmarket.xyz/api --
    berbeda dari token MCP chart). Endpoint: api.kiyotaka.ai/v1/points

    Format candle (terverifikasi): series[0].columns = [t,open,high,low,close,volume],
    series[0].rows = [[ISO8601, o, h, l, c, v], ...].
    """

    BASE = "https://api.kiyotaka.ai/v1/points"
    INTERVAL = {
        "1m": "MINUTE", "5m": "FIVE_MINUTES", "15m": "FIFTEEN_MINUTES",
        "30m": "THIRTY_MINUTES", "1h": "HOUR", "4h": "FOUR_HOURS",
        "1d": "DAY", "1w": "WEEK",
    }
    TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60,
              "4h": 240, "1d": 1440, "1w": 10080}

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENMARKET_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OPENMARKET_API_KEY belum di-set (ambil di openmarket.xyz/api)"
            )

    def candles(self, simbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        tf = (timeframe or "1h").lower()
        interval = self.INTERVAL.get(tf, "HOUR")
        coin = self._coin(simbol)
        lookback = self._lookback(tf, limit)
        url = (
            f"{self.BASE}?type=TRADE_SIDE_AGNOSTIC_AGG&coin={coin}"
            f"&interval={interval}&lookback={lookback}"
        )
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "warroom-screener/1.0",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        series = data.get("series") or []
        if not series:
            return []
        cols = series[0].get("columns") or []
        rows = series[0].get("rows") or []
        ix = {c: i for i, c in enumerate(cols)}
        out: list[Candle] = []
        for row in rows:
            out.append({
                "time": self._epoch(row[ix["t"]]),
                "open": float(row[ix["open"]]),
                "high": float(row[ix["high"]]),
                "low": float(row[ix["low"]]),
                "close": float(row[ix["close"]]),
                "volume": float(row[ix["volume"]]),
            })
        return out[-limit:]

    @staticmethod
    def _coin(simbol: str) -> str:
        # "BTC" / "BTCUSDT" / "BTC-USDT" -> "BTC"
        s = (simbol or "").upper().split("-")[0]
        for q in ("USDT", "USD", "USDC"):
            if s.endswith(q):
                return s[: -len(q)]
        return s

    def _lookback(self, tf: str, limit: int) -> str:
        mins = self.TF_MIN.get(tf, 60) * max(limit, 1)
        return f"{mins}m" if mins < 1440 else f"{mins // 1440}d"

    @staticmethod
    def _epoch(iso: str) -> float:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()



def provider_untuk(market: str) -> DataProvider:
    """Pilih provider berdasar market. Fail-closed: market tak dikenal -> error."""
    market = (market or "").lower()
    if market in ("crypto", "memecoin"):
        # memecoin terdaftar di Binance (PEPEUSDT, WIFUSDT, ...) pakai sumber sama.
        return BinanceProvider()
    if market == "openmarket":
        # Unified API lintas 40+ venue (butuh OPENMARKET_API_KEY).
        return OpenMarketProvider()
    raise ValueError(f"market belum didukung provider-nya: {market!r}")
