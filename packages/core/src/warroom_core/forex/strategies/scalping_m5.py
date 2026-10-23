"""Strategi Scalping M5 Break-Retest & Momentum EMA (PNP Strategy 1)."""

from __future__ import annotations

from typing import Any
from .base import BaseStrategy


class ScalpingM5Strategy(BaseStrategy):
    """Strategi scalping berbasis momentum EMA9/EMA21 dan volatilitas ATR14."""

    def __init__(self):
        super().__init__(name="Scalping M5 Momentum", timeframe="5m", rrr_min=1.5)

    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        price = market_data.get("price", 0.0)
        ema9 = market_data.get("ema9", 0.0)
        ema21 = market_data.get("ema21", 0.0)
        atr14 = market_data.get("atr14", 3.0)

        if price <= 0 or ema9 <= 0:
            return None

        risk = round(max(atr14 * 1.2, 2.0), 2)
        reward = round(risk * 1.6, 2)  # RRR = 1.6:1

        if price >= ema9 and ema9 >= ema21:
            # Bullish Scalp Setup
            return {
                "side": "LONG",
                "entry": price,
                "sl": round(price - risk, 2),
                "tp1": round(price + reward, 2),
                "tp2": round(price + (reward * 1.5), 2),
                "reason": f"M5 Bullish Alignment: Price ({price}) >= EMA9 ({ema9}) >= EMA21 ({ema21})",
                "confidence": 0.82,
                "strategy": self.name,
            }
        elif price <= ema9 and ema9 <= ema21:
            # Bearish Scalp Setup
            return {
                "side": "SHORT",
                "entry": price,
                "sl": round(price + risk, 2),
                "tp1": round(price - reward, 2),
                "tp2": round(price - (reward * 1.5), 2),
                "reason": f"M5 Bearish Alignment: Price ({price}) <= EMA9 ({ema9}) <= EMA21 ({ema21})",
                "confidence": 0.80,
                "strategy": self.name,
            }

        return None
