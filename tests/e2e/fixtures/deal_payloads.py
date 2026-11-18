"""Deal payloads for testing MT5 deal ingestion, net calculations, and deduplication."""

from __future__ import annotations

import time
from typing import Any


def make_deal_payload(
    ticket: int,
    account: str = "452009427",
    symbol: str = "XAUUSDc",
    side: str = "BUY",
    volume: float = 0.01,
    open_price: float = 2700.50,
    close_price: float = 2705.50,
    profit: float = 0.50,
    swap: float = -0.02,
    commission: float = -0.08,
    magic: int = 0,
    comment: str = "e2e-test",
    currency: str = "USC",
    cent_factor: float = 100.0,
    strategy_version: str = "v3.0",
) -> dict[str, Any]:
    """Synthesize a valid MT5 deal payload dictionary."""
    now_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    net = round(profit + swap + commission, 2)
    return {
        "ticket": ticket,
        "position": ticket,
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "open_time": now_iso,
        "open_price": open_price,
        "close_time": now_iso,
        "close_price": close_price,
        "profit": profit,
        "swap": swap,
        "commission": commission,
        "net": net,
        "magic": magic,
        "comment": comment,
        "account": account,
        "strategy_version": strategy_version,
        "currency": currency,
        "cent_factor": cent_factor,
    }


def sample_live_cent_deal(ticket: int = 6639264) -> dict[str, Any]:
    """Deal payload for Live Cent #452009427."""
    return make_deal_payload(
        ticket=ticket,
        account="452009427",
        symbol="XAUUSDc",
        side="BUY",
        volume=0.01,
        profit=0.50,
        swap=-0.02,
        commission=-0.08,
        currency="USC",
        cent_factor=100.0,
        magic=0,
    )


def sample_demo1_deal(ticket: int = 7781001) -> dict[str, Any]:
    """Deal payload for Demo 1 Twin Layering #434446792."""
    return make_deal_payload(
        ticket=ticket,
        account="434446792",
        symbol="XAUUSDm",
        side="BUY",
        volume=0.01,
        profit=12.50,
        swap=0.0,
        commission=-0.15,
        currency="USD",
        cent_factor=1.0,
        magic=434446,
    )


def sample_demo2_deal(ticket: int = 8892002) -> dict[str, Any]:
    """Deal payload for Demo 2 Trend Bounded Avg #464202979."""
    return make_deal_payload(
        ticket=ticket,
        account="464202979",
        symbol="XAUUSDm",
        side="SELL",
        volume=0.01,
        profit=-15.00,
        swap=-0.10,
        commission=-0.15,
        currency="USD",
        cent_factor=1.0,
        magic=464202,
    )


def invalid_ticket_zero_deal() -> dict[str, Any]:
    """Invalid deal payload with ticket = 0."""
    return make_deal_payload(ticket=0)


def invalid_ticket_negative_deal() -> dict[str, Any]:
    """Invalid deal payload with ticket < 0."""
    return make_deal_payload(ticket=-99)


def corrupt_deal_non_numeric_profit() -> dict[str, Any]:
    """Corrupt deal with string instead of float for profit."""
    payload = make_deal_payload(ticket=999999)
    payload["profit"] = "not-a-number"
    return payload


def large_int64_deal(ticket: int = 9223372036854775807) -> dict[str, Any]:
    """Valid deal payload with 64-bit integer ticket boundary."""
    return make_deal_payload(
        ticket=ticket,
        account="434446792",
        symbol="XAUUSDm",
        currency="USD",
        cent_factor=1.0,
    )
