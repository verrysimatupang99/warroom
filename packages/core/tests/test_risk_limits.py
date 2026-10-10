from datetime import UTC, datetime, timedelta

from warroom_core.signal import MarketData, RiskPolicy, Signal, evaluate_risk


def _signal():
    now = datetime.now(UTC)
    return Signal(
        "risk-1", "crypto", "okx", "BTCUSDT", "smc", "long",
        100, 98, 104, 2, .8, now, now + timedelta(minutes=5), 1, "test",
    )


def _data():
    return MarketData("crypto", "okx", "BTCUSDT", datetime.now(UTC), 100, 2, 100_000, {})


def test_risk_rejects_daily_loss_open_exposure_and_position_caps():
    base = dict(max_spread_bps=10, min_liquidity_usd=10_000)
    assert evaluate_risk(
        _signal(), _data(), RiskPolicy(**base, max_daily_loss_usd=100, daily_loss_usd=100)
    ).reason == "daily_loss_limit"
    assert evaluate_risk(
        _signal(), _data(),
        RiskPolicy(**base, max_open_exposure_usd=1000, open_exposure_usd=1000),
    ).reason == "open_exposure_limit"
    assert evaluate_risk(
        _signal(), _data(), RiskPolicy(**base, max_position_usd=40)
    ).reason == "position_size_limit"


def test_risk_rejects_correlated_exposure_cap():
    policy = RiskPolicy(max_correlated_exposure_usd=500, correlated_exposure_usd=500)
    decision = evaluate_risk(_signal(), _data(), policy)
    assert decision.reason == "correlated_exposure_limit"
