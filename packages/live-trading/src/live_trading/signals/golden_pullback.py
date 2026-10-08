"""Deterministic SMC + Fibonacci Smart Golden Pullback rules.

This module contains no discretionary ranking and no network/execution side effects.
The default 0.618-0.786 zone is configuration, not a performance claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from warroom_core.signal import Decision, MarketData, Signal
from warroom_core.strategy import Strategy

Direction = Literal["long", "short"]


@dataclass(frozen=True, slots=True)
class GoldenPullbackConfig:
    zone_start: float = 0.618
    zone_end: float = 0.786
    minimum_rr: float = 2.0

    def __post_init__(self) -> None:
        if not 0 < self.zone_start < self.zone_end < 1:
            raise ValueError("golden zone harus 0 < start < end < 1")
        if self.minimum_rr <= 0:
            raise ValueError("minimum_rr harus positif")


def retracement_zone(
    swing_low: float,
    swing_high: float,
    direction: Direction,
    config: GoldenPullbackConfig | None = None,
) -> tuple[float, float]:
    """Return the inclusive price zone as (low, high) for the impulse retracement."""
    cfg = config or GoldenPullbackConfig()
    if swing_low <= 0 or swing_high <= swing_low:
        raise ValueError("swing impulse tidak valid")
    distance = swing_high - swing_low
    if direction == "long":
        a = swing_high - distance * cfg.zone_end
        b = swing_high - distance * cfg.zone_start
    else:
        a = swing_low + distance * cfg.zone_start
        b = swing_low + distance * cfg.zone_end
    return (min(a, b), max(a, b))


def build_pullback_setup(
    *,
    direction: Direction,
    swing_low: float,
    swing_high: float,
    current_price: float,
    structure_bias: str,
    liquidity_swept: bool,
    confirmation: bool,
    config: GoldenPullbackConfig | None = None,
) -> dict[str, float | str] | None:
    """Build a setup only when every deterministic SMC/Golden-Pullback gate passes."""
    cfg = config or GoldenPullbackConfig()
    expected_bias = "bullish" if direction == "long" else "bearish"
    if structure_bias != expected_bias or not liquidity_swept or not confirmation:
        return None
    zone_low, zone_high = retracement_zone(swing_low, swing_high, direction, cfg)
    if not zone_low <= current_price <= zone_high:
        return None
    if direction == "long":
        stop = swing_low
        risk = current_price - stop
        target = current_price + risk * cfg.minimum_rr
    else:
        stop = swing_high
        risk = stop - current_price
        target = current_price - risk * cfg.minimum_rr
    if risk <= 0:
        return None
    return {
        "direction": direction,
        "entry": current_price,
        "stop": stop,
        "target": target,
        "risk_reward": cfg.minimum_rr,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "reason": "SMC structure + liquidity sweep + Fibonacci Smart Golden Pullback",
    }


class GoldenPullbackStrategy(Strategy):
    """Core strategy adapter; payload supplies already-normalized deterministic inputs."""

    name = "smc-fibonacci-smart-golden-pullback-v1"

    def __init__(self, config: GoldenPullbackConfig | None = None) -> None:
        self.config = config or GoldenPullbackConfig()

    def scan(self, market_data: MarketData) -> list[Signal]:
        p = market_data.payload
        direction = p.get("direction")
        if direction not in {"long", "short"}:
            return []
        setup = build_pullback_setup(
            direction=direction,
            swing_low=float(p["swing_low"]),
            swing_high=float(p["swing_high"]),
            current_price=market_data.price,
            structure_bias=str(p.get("structure_bias", "")),
            liquidity_swept=bool(p.get("liquidity_swept", False)),
            confirmation=bool(p.get("confirmation", False)),
            config=self.config,
        )
        if setup is None:
            return []
        now = datetime.now(UTC)
        return [
            Signal(
                signal_id=f"{self.name}:{market_data.instrument}:{int(now.timestamp())}",
                market=market_data.market,
                venue=market_data.venue,
                instrument=market_data.instrument,
                strategy=self.name,
                direction=direction,
                entry=float(setup["entry"]),
                stop=float(setup["stop"]),
                target=float(setup["target"]),
                risk_reward=float(setup["risk_reward"]),
                confidence=None,
                created_at=now,
                expires_at=now + timedelta(minutes=int(p.get("expiry_minutes", 15))),
                freshness_s=max(0.0, (now - market_data.observed_at).total_seconds()),
                reason=str(setup["reason"]),
            )
        ]

    def validate(self, signal: Signal, context: dict[str, Any]) -> Decision:
        if signal.strategy != self.name:
            return Decision(False, "strategy_mismatch")
        if signal.risk_reward is None or signal.risk_reward < self.config.minimum_rr:
            return Decision(False, "risk_reward_below_strategy_minimum")
        return Decision(True, "strategy_valid")
