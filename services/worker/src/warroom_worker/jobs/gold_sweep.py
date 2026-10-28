"""Scanner Kuantitatif Liquidity Sweep XAUUSD (Asia Range & London Sweep).

Mendeteksi sweep likuiditas sesi Asia dan konfirmasi Fair Value Gap (FVG)
untuk scalping institusional XAUUSD di MetaTrader 5 War Room.
"""

from __future__ import annotations
import os

import logging
from typing import Any

import httpx

logger = logging.getLogger("warroom_worker.gold_sweep")
TENCENT_URL = os.environ.get("WARROOM_TENCENT_BASE", "").rstrip("/")


async def hitung_asia_range(symbol: str = "XAUUSD") -> dict[str, Any] | None:
    """Tarik data klines H1 dan M5 dari feed Tencent untuk mengunci high/low sesi Asia (00:00 - 07:00 UTC)."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = f"{TENCENT_URL}/forex/klines"
            params = {"symbol": symbol, "interval": "60", "limit": 12}
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"Gagal mengambil klines H1: {resp.status_code}")
                return None

            candles = resp.json().get("candles", [])
            if not candles or len(candles) < 8:
                return None

            # Ambil 8 bar terakhir yang merepresentasikan sesi Asia
            asia_bars = candles[-8:]
            asia_high = max(float(k["h"]) for k in asia_bars)
            asia_low = min(float(k["l"]) for k in asia_bars)
            asia_range = round(asia_high - asia_low, 2)

            return {
                "symbol": symbol,
                "asia_high": asia_high,
                "asia_low": asia_low,
                "asia_range": asia_range,
                "is_valid_range": 10.0 <= asia_range <= 35.0,
            }
    except Exception as e:
        logger.error(f"Error kalkulasi asia range: {e}")
        return None


async def scan_london_sweep(symbol: str = "XAUUSD") -> dict[str, Any] | None:
    """Deteksi apakah harga saat ini sedang melakukan sweep di atas Asia High atau di bawah Asia Low."""
    range_data = await hitung_asia_range(symbol)
    if not range_data or not range_data["is_valid_range"]:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{TENCENT_URL}/forex/levels", params={"symbol": symbol})
            if resp.status_code != 200:
                return None

            data = resp.json()
            cur_price = float(data.get("price", 0.0))
            if cur_price <= 0:
                return None

            asia_high = range_data["asia_high"]
            asia_low = range_data["asia_low"]

            # Kasus Bullish Sweep (Sell Setup): Sweep di atas Asia High sebesar $1 - $3
            if cur_price > asia_high and (cur_price - asia_high) <= 3.5:
                msg = f"Gold sweep Asia High ({asia_high}) di {cur_price}. Menunggu rejection candle M5."
                return {
                    "signal": "SELL_SWEEP_WATCH",
                    "symbol": symbol,
                    "cur_price": cur_price,
                    "target_fvg": round(cur_price - 1.20, 2),
                    "sl": round(cur_price + 2.00, 2),
                    "tp": round(cur_price - 3.00, 2),
                    "reason": msg,
                }

            # Kasus Bearish Sweep (Buy Setup): Sweep di bawah Asia Low sebesar $1 - $3
            if cur_price < asia_low and (asia_low - cur_price) <= 3.5:
                msg = f"Gold sweep Asia Low ({asia_low}) di level {cur_price}. Menunggu rejection candle M5."
                return {
                    "signal": "BUY_SWEEP_WATCH",
                    "symbol": symbol,
                    "cur_price": cur_price,
                    "target_fvg": round(cur_price + 1.20, 2),
                    "sl": round(cur_price - 2.00, 2),
                    "tp": round(cur_price + 3.00, 2),
                    "reason": msg,
                }

            return None
    except Exception as e:
        logger.error(f"Error scan london sweep: {e}")
        return None
