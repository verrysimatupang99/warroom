from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from warroom_core.signal import (
    Decision,
    MarketData,
    RiskPolicy,
    Signal,
    evaluate_risk,
)


def _signal(**overrides):
    values = {
        "signal_id": "sig-1", "market": "crypto", "venue": "paper",
        "instrument": "BTCUSDT", "strategy": "smc", "direction": "long",
        "entry": 100.0, "stop": 98.0, "target": 104.0, "risk_reward": 2.0,
        "confidence": 0.7, "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
        "freshness_s": 10, "reason": "test", "mode": "paper",
    }
    values.update(overrides)
    return Signal(**values)


def test_signal_rejects_invalid_direction_and_live_mode():
    with pytest.raises(ValueError):
        _signal(direction="maybe")
    with pytest.raises(ValueError):
        _signal(mode="live")


def test_signal_market_data_and_risk_allow_fresh_paper_signal():
    data = MarketData(
        market="crypto", venue="okx", instrument="BTCUSDT",
        observed_at=datetime.now(UTC), price=100.0, spread_bps=3.0,
        liquidity_usd=100_000.0, payload={"source": "test"},
    )
    decision = evaluate_risk(_signal(), data, RiskPolicy(max_spread_bps=10, min_liquidity_usd=10_000))
    assert decision == Decision(True, "allowed", 50.0)


def test_risk_rejects_stale_spread_liquidity_expiry_and_kill_switch():
    now = datetime.now(UTC)
    data = MarketData(
        market="crypto", venue="okx", instrument="BTCUSDT",
        observed_at=now - timedelta(minutes=10), price=100.0,
        spread_bps=30, liquidity_usd=100, payload={},
    )
    assert not evaluate_risk(
        _signal(created_at=now, expires_at=now + timedelta(minutes=1)),
        data,
        RiskPolicy(max_age_s=60),
    ).allowed
    fresh_data = replace(data, observed_at=now)
    assert evaluate_risk(
        _signal(), fresh_data, RiskPolicy(max_spread_bps=10)
    ).reason == "spread_too_wide"
    assert evaluate_risk(
        _signal(), replace(fresh_data, spread_bps=None), RiskPolicy(min_liquidity_usd=10_000)
    ).reason == "liquidity_too_low"
    expired = _signal(expires_at=now + timedelta(seconds=1))
    assert evaluate_risk(
        expired, fresh_data, RiskPolicy(), now=now + timedelta(seconds=2)
    ).reason == "signal_expired"
    assert evaluate_risk(_signal(), fresh_data, RiskPolicy(kill_switch=True)).reason == "kill_switch"
