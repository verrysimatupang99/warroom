"""Small, market-neutral adapter boundary for paper signal generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from warroom_core.signal import MarketData

__all__ = ["Adapter", "normalize_market_data"]


class Adapter(ABC):
    """Fetch one normalized market snapshot; adapters never execute orders."""

    @abstractmethod
    def fetch(self, instrument: str) -> MarketData:
        raise NotImplementedError


def normalize_market_data(
    market: str,
    venue: str,
    instrument: str,
    observed_at: datetime,
    price: float,
    spread_bps: float | None,
    liquidity_usd: float | None,
    payload: dict[str, Any],
) -> MarketData:
    if observed_at.tzinfo is None:
        raise ValueError("observed_at wajib timezone-aware")
    if price <= 0:
        raise ValueError("price wajib positif")
    if spread_bps is not None and spread_bps < 0:
        raise ValueError("spread_bps tidak boleh negatif")
    if liquidity_usd is not None and liquidity_usd < 0:
        raise ValueError("liquidity_usd tidak boleh negatif")
    return MarketData(
        market=market,
        venue=venue,
        instrument=instrument,
        observed_at=observed_at,
        price=price,
        spread_bps=spread_bps,
        liquidity_usd=liquidity_usd,
        payload=dict(payload),
    )
