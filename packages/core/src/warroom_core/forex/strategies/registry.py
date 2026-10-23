"""Manajer Strategi Plug-and-Play (PNP Registry) War Room.

Memungkinkan user dan operator memilih, menambah, atau menonaktifkan
strategi trading secara dinamis (User-Friendly).
"""

from __future__ import annotations

from typing import Any
from .base import BaseStrategy
from .scalping_m5 import ScalpingM5Strategy
from .laya_judge import LayaForexJudgeStrategy
from .multi_session_laya import MultiSessionLayaScalperStrategy


class StrategyRegistry:
    """Registry modular untuk strategi trading PNP."""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}
        self._active_strategy_key: str = "multi_session_laya"
        self._register_defaults()

    def _register_defaults(self):
        # 1. Daftarkan strategi bawaan
        self.register("scalping_m5", ScalpingM5Strategy())
        self.register("laya_judge", LayaForexJudgeStrategy())
        self.register("multi_session_laya", MultiSessionLayaScalperStrategy(lot_size=0.10, min_rrr=1.8))

    def register(self, key: str, strategy: BaseStrategy):
        """Daftarkan strategi baru ke dalam ekosistem PNP."""
        self._strategies[key] = strategy

    def get_active_strategy(self) -> BaseStrategy:
        """Ambil strategi yang sedang aktif dipilih."""
        return self._strategies.get(self._active_strategy_key, self._strategies["scalping_m5"])

    def set_active_strategy(self, key: str) -> bool:
        """Ganti strategi aktif (Plug-and-Play)."""
        if key in self._strategies:
            self._active_strategy_key = key
            return True
        return False

    def list_strategies(self) -> list[dict[str, Any]]:
        """Daftar seluruh strategi yang tersedia untuk UI / Dashboard."""
        return [
            {
                "key": k,
                "name": s.name,
                "timeframe": s.timeframe,
                "rrr_min": s.rrr_min,
                "is_active": (k == self._active_strategy_key),
            }
            for k, s in self._strategies.items()
        ]


# Singleton instance untuk seluruh engine War Room
pnp_registry = StrategyRegistry()
