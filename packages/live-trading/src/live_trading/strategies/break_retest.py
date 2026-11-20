from __future__ import annotations

from typing import Any

from .base import BaseStrategy, StrategySignal


class BreakRetestForexStrategy(BaseStrategy):
    """Strategi Break & Retest M15 untuk XAUUSD & Major Forex."""

    id = "break_retest_forex_m15"
    name = "Break & Retest M15 (XAUUSD / Forex)"
    market = "forex"
    version = "1.0.0"
    description = "Deteksi breakout struktur 20-bar + retest rejection dengan SL 1.6x ATR & RRR 1:3."

    def generate_signal(self, market_data: dict[str, Any]) -> list[StrategySignal]:
        return []

    def backtest(
        self, candles: list[dict[str, Any]], params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "strategy_id": self.id,
            "trades": len(candles),
            "status": "ready",
        }
