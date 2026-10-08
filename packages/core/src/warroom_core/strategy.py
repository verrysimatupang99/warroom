"""Common strategy boundary; strategies produce paper signals only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from warroom_core.signal import Decision, MarketData, Signal


class Strategy(ABC):
    name: str = "unnamed"

    @abstractmethod
    def scan(self, market_data: MarketData) -> list[Signal]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, signal: Signal, context: dict[str, Any]) -> Decision:
        raise NotImplementedError
