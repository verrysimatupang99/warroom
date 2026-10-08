from datetime import UTC, datetime, timedelta

from warroom_core.paper import PaperExecutor
from warroom_core.signal import MarketData, RiskPolicy, Signal


def signal(signal_id="s1"):
    now = datetime.now(UTC)
    return Signal(
        signal_id=signal_id, market="crypto", venue="mexc", instrument="BTCUSDT",
        strategy="smc", direction="long", entry=100, stop=98, target=104,
        risk_reward=2, confidence=.8, created_at=now,
        expires_at=now + timedelta(minutes=5), freshness_s=1, reason="test",
    )


def data():
    return MarketData("crypto", "mexc", "BTCUSDT", datetime.now(UTC), 100, 2, 100_000, {})


def test_paper_executor_deduplicates_and_records_fill():
    executor = PaperExecutor(RiskPolicy(max_spread_bps=10))
    first = executor.submit(signal(), data())
    second = executor.submit(signal(), data())
    assert first.status == "filled"
    assert first.price == 100
    assert second.status == "duplicate"
    assert len(executor.records) == 1


def test_paper_executor_records_rejections_without_filling():
    executor = PaperExecutor(RiskPolicy(kill_switch=True))
    result = executor.submit(signal(), data())
    assert result.status == "rejected"
    assert result.reason == "kill_switch"
    assert len(executor.records) == 1
