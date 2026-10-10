from datetime import UTC, datetime

from warroom_core.signal import MarketData

from live_trading.signals.golden_pullback import GoldenPullbackStrategy


def test_strategy_emits_unified_paper_signal_from_deterministic_payload():
    data = MarketData(
        "crypto", "okx", "BTCUSDT", datetime.now(UTC), 106, 2, 100_000,
        {
            "direction": "long", "swing_low": 100, "swing_high": 120,
            "structure_bias": "bullish", "liquidity_swept": True,
            "confirmation": True,
        },
    )
    signals = GoldenPullbackStrategy().scan(data)
    assert len(signals) == 1
    assert signals[0].mode == "paper"
    assert signals[0].entry == 106
    assert GoldenPullbackStrategy().validate(signals[0], {}) .allowed


def test_strategy_emits_no_signal_when_smc_gate_is_missing():
    data = MarketData(
        "crypto", "okx", "BTCUSDT", datetime.now(UTC), 106, 2, 100_000,
        {"direction": "long", "swing_low": 100, "swing_high": 120,
         "structure_bias": "bullish", "liquidity_swept": False, "confirmation": True},
    )
    assert GoldenPullbackStrategy().scan(data) == []
