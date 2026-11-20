from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

MarketType = Literal["forex", "crypto", "idx", "polymarket"]


@dataclass
class StrategySignal:
    """Sinyal trading deterministik yang dihasilkan oleh strategi modular."""

    symbol: str
    direction: Literal["BUY", "SELL", "NEUTRAL"]
    confidence: float
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """Kontrak standar (plug-and-play) untuk seluruh strategi quant War Room."""

    id: str = "base"
    name: str = "Base Strategy"
    market: MarketType = "forex"
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True

    @abstractmethod
    def generate_signal(self, market_data: dict[str, Any]) -> list[StrategySignal]:
        """Menghasilkan sinyal trading deterministik dari data pasar."""

    @abstractmethod
    def backtest(
        self, candles: list[dict[str, Any]], params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Menjalankan backtest anti-lookahead dan mengembalikan metrik performa."""

    def to_dict(self) -> dict[str, Any]:
        """Serialisasi metadata strategi untuk API dan UI."""
        return {
            "id": self.id,
            "name": self.name,
            "market": self.market,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }
