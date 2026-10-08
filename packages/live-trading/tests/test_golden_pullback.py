import pytest

from live_trading.signals.golden_pullback import (
    GoldenPullbackConfig,
    build_pullback_setup,
    retracement_zone,
)


def test_bullish_golden_zone_and_setup_are_deterministic():
    zone = retracement_zone(100, 120, "long")
    assert zone[0] == pytest.approx(104.28)
    assert zone[1] == pytest.approx(107.64)
    setup = build_pullback_setup(
        direction="long", swing_low=100, swing_high=120, current_price=106,
        structure_bias="bullish", liquidity_swept=True, confirmation=True,
    )
    assert setup is not None
    assert setup["entry"] == 106
    assert setup["stop"] == 100
    assert setup["target"] == 118


def test_bearish_zone_mirrors_bullish_zone():
    low, high = retracement_zone(100, 120, "short")
    assert low == pytest.approx(112.36)
    assert high == pytest.approx(115.72)


def test_any_missing_smc_confirmation_blocks_setup():
    common = dict(
        direction="long", swing_low=100, swing_high=120, current_price=106,
        structure_bias="bullish", liquidity_swept=True, confirmation=True,
    )
    assert build_pullback_setup(**{**common, "structure_bias": "bearish"}) is None
    assert build_pullback_setup(**{**common, "liquidity_swept": False}) is None
    assert build_pullback_setup(**{**common, "confirmation": False}) is None


def test_golden_zone_config_is_validated():
    with pytest.raises(ValueError):
        GoldenPullbackConfig(zone_start=.8, zone_end=.7)
    with pytest.raises(ValueError):
        GoldenPullbackConfig(minimum_rr=0)
