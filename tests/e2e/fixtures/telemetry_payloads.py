"""Telemetry payloads for testing MT5 telemetry ingestion, state caching, and SSE streaming."""

from __future__ import annotations

import time
from typing import Any


def make_telemetry_payload(
    account: str = "452009427",
    broker: str = "Exness Technologies Ltd",
    currency: str = "USC",
    cent_factor: float = 100.0,
    balance: float = 1084.84,
    equity: float = 1084.84,
    margin: float = 0.0,
    free_margin: float = 1084.84,
    floating_pnl: float = 0.0,
    positions: list[dict[str, Any]] | None = None,
    pending_orders: list[dict[str, Any]] | None = None,
    spread_pts: int = 240,
    atr_m5: float = 4.16,
    bid: float = 2700.50,
    ask: float = 2700.74,
    server_time: int | None = None,
    eval_alasan: str = "OK",
    eval_sesi: bool = True,
    eval_tren: str = "BULLISH",
) -> dict[str, Any]:
    """Synthesize a full MT5 telemetry payload dictionary."""
    return {
        "account": account,
        "broker": broker,
        "currency": currency,
        "cent_factor": cent_factor,
        "balance": balance,
        "equity": equity,
        "margin": margin,
        "free_margin": free_margin,
        "floating_pnl": floating_pnl,
        "positions": positions or [],
        "pending_orders": pending_orders or [],
        "total_trades_today": 0,
        "win_rate_pct": 0.0,
        "wins_today": 0,
        "losses_today": 0,
        "bid": bid,
        "ask": ask,
        "spread_pts": spread_pts,
        "digits": 3,
        "atr_m5": atr_m5,
        "server_time": server_time or int(time.time()),
        "eval_alasan": eval_alasan,
        "eval_sesi": eval_sesi,
        "eval_tren": eval_tren,
    }


def sample_live_cent_telemetry() -> dict[str, Any]:
    """Telemetry payload for Live Cent #452009427 (Gold Reaper, USC)."""
    return make_telemetry_payload(
        account="452009427",
        broker="Exness Technologies Ltd",
        currency="USC",
        cent_factor=100.0,
        balance=1084.84,
        equity=1084.84,
        margin=0.0,
        free_margin=1084.84,
        floating_pnl=0.0,
        spread_pts=240,
        atr_m5=4.16,
    )


def sample_demo1_telemetry() -> dict[str, Any]:
    """Telemetry payload for Demo 1 #434446792 (Twin Layering, USD)."""
    return make_telemetry_payload(
        account="434446792",
        broker="Exness Technologies Ltd",
        currency="USD",
        cent_factor=1.0,
        balance=1005.00,
        equity=1005.00,
        margin=0.0,
        free_margin=1005.00,
        floating_pnl=0.0,
        spread_pts=25,
        atr_m5=3.50,
    )


def sample_demo2_telemetry() -> dict[str, Any]:
    """Telemetry payload for Demo 2 #464202979 (Trend Bounded Avg, USD)."""
    return make_telemetry_payload(
        account="464202979",
        broker="Exness Technologies Ltd",
        currency="USD",
        cent_factor=1.0,
        balance=1000.00,
        equity=1000.00,
        margin=0.0,
        free_margin=1000.00,
        floating_pnl=0.0,
        spread_pts=25,
        atr_m5=3.50,
    )


def azure_vm2_telemetry() -> dict[str, Any]:
    """Telemetry payload for retired Azure VM2 #36525553 (must be quarantined)."""
    return make_telemetry_payload(
        account="36525553",
        broker="Vantage",
        currency="USC",
        cent_factor=100.0,
        balance=500.00,
        equity=500.00,
        margin=0.0,
        free_margin=500.00,
        floating_pnl=0.0,
    )


def zero_balance_telemetry(account: str = "452009427") -> dict[str, Any]:
    """Boundary telemetry payload with 0 balance and 0 equity."""
    return make_telemetry_payload(
        account=account,
        balance=0.0,
        equity=0.0,
        margin=0.0,
        free_margin=0.0,
        floating_pnl=0.0,
    )


def missing_mandatory_fields_telemetry() -> dict[str, Any]:
    """Invalid telemetry missing broker, balance, equity, margin, etc."""
    return {"account": "452009427"}


def extreme_spread_telemetry(spread_pts: int = 500) -> dict[str, Any]:
    """Telemetry with extreme spread condition for volatility testing."""
    return make_telemetry_payload(
        account="434446792",
        currency="USD",
        cent_factor=1.0,
        spread_pts=spread_pts,
        eval_alasan="SPREAD_MELEBIHI_BATAS",
    )
