"""Base Interface untuk Plug-and-Play (PNP) Trading Strategy War Room.

Setiap strategi Forex (Scalping, Trend Following, SMC, Laya AI Filter)
mengimplementasikan interface ini sehingga dapat dibongkar-pasang (PNP)
secara modular dan user-friendly tanpa mengubah core engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    """Kelas dasar strategi trading modular."""

    def __init__(self, name: str, timeframe: str = "5m", rrr_min: float = 1.5):
        self.name = name
        self.timeframe = timeframe
        self.rrr_min = rrr_min
        self.enabled = True

    @abstractmethod
    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        """Evaluasi kondisi pasar dan kembalikan sinyal order jika kondisi terpenuhi.
        
        Returns:
            dict dengan format {
                "side": "BUY" | "SELL",
                "entry": float,
                "sl": float,
                "tp1": float,
                "tp2": float,
                "reason": str,
                "confidence": float (0.0 - 1.0)
            } atau None jika tidak ada sinyal.
        """
        pass
