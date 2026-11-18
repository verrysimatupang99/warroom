"""Account reference definitions and schemas for the 3 MT5 production & test accounts."""

from __future__ import annotations

from typing import Any

ACCOUNT_LIVE_CENT = "452009427"
ACCOUNT_DEMO_1 = "434446792"
ACCOUNT_DEMO_2 = "464202979"
ACCOUNT_AZURE_VM2 = "36525553"  # Retired/quarantined VM2 account

ACCOUNTS_METADATA: dict[str, dict[str, Any]] = {
    ACCOUNT_LIVE_CENT: {
        "account": ACCOUNT_LIVE_CENT,
        "broker": "Exness Technologies Ltd",
        "currency": "USC",
        "cent_factor": 100.0,
        "primary": True,
        "strategy": "GOLD_Reaper_Hexa",
        "symbol": "XAUUSDc",
        "timeframe": "M5",
        "initial_deposit": 1084.84,
        "fixed_lot": 0.01,
        "sandbox": "box-2aacb3",
    },
    ACCOUNT_DEMO_1: {
        "account": ACCOUNT_DEMO_1,
        "broker": "Exness Technologies Ltd",
        "currency": "USD",
        "cent_factor": 1.0,
        "primary": False,
        "strategy": "WarRoom_DemoA_TwinLayering",
        "symbol": "XAUUSDm",
        "timeframe": "M15",
        "initial_deposit": 1005.00,
        "magic": 434446,
        "fixed_lot": 0.02,
        "daily_max_loss_usd": 30.00,
        "sandbox": "mt5-paper-1",
    },
    ACCOUNT_DEMO_2: {
        "account": ACCOUNT_DEMO_2,
        "broker": "Exness Technologies Ltd",
        "currency": "USD",
        "cent_factor": 1.0,
        "primary": False,
        "strategy": "WarRoom_DemoB_TrendBoundedAvg",
        "symbol": "XAUUSDm",
        "timeframe": "M15",
        "initial_deposit": 1000.00,
        "magic": 464202,
        "fixed_lot": 0.01,
        "max_layers": 4,
        "basket_tp_usd": 12.00,
        "hard_basket_sl_usd": 45.00,
        "daily_max_loss_usd": 45.00,
        "sandbox": "mt5-paper-2",
    },
    ACCOUNT_AZURE_VM2: {
        "account": ACCOUNT_AZURE_VM2,
        "broker": "Vantage International",
        "currency": "USC",
        "cent_factor": 100.0,
        "primary": False,
        "quarantined": True,
        "strategy": "Legacy",
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "initial_deposit": 500.00,
        "fixed_lot": 0.01,
        "sandbox": "none",
    },
}


def get_account_meta(account_id: str) -> dict[str, Any]:
    """Retrieve reference metadata for a specific account."""
    if account_id not in ACCOUNTS_METADATA:
        raise KeyError(f"Unknown account: {account_id}")
    return dict(ACCOUNTS_METADATA[account_id])


def get_all_active_account_ids() -> list[str]:
    """Return list of the three active platform accounts."""
    return [ACCOUNT_LIVE_CENT, ACCOUNT_DEMO_1, ACCOUNT_DEMO_2]
