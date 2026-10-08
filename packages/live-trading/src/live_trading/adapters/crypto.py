"""Production data adapter boundary for crypto paper signals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from warroom_core.adapters import Adapter, normalize_market_data
from warroom_core.signal import MarketData


class CryptoSnapshotCollector(Protocol):
    def pair_snapshot(self, pair: str, klines: int = 24) -> dict[str, Any]: ...


class CryptoAdapter(Adapter):
    """Normalize the existing public crypto collector; never submits orders."""

    market = "crypto"
    venue = "binance-fapi"

    def __init__(self, collector: CryptoSnapshotCollector) -> None:
        self.collector = collector

    def fetch(self, instrument: str) -> MarketData:
        snapshot = self.collector.pair_snapshot(instrument)
        try:
            price = float(snapshot["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"crypto snapshot price invalid for {instrument}") from exc
        observed_ms = snapshot.get("observed_at_ms")
        try:
            if observed_ms is None:
                raise ValueError("source timestamp missing")
            observed_at = datetime.fromtimestamp(float(observed_ms) / 1000, tz=UTC)
        except (TypeError, ValueError, OSError, OverflowError) as exc:
            raise ValueError(f"crypto source timestamp invalid for {instrument}") from exc
        return normalize_market_data(
            self.market,
            self.venue,
            instrument,
            observed_at,
            price,
            spread_bps=None,
            liquidity_usd=None,
            payload={"source": "CryptoCollector", **snapshot},
        )
