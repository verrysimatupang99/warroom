from datetime import UTC, datetime

from live_trading.demo_ab_backtest import (
    Bar15m,
    simulate_bounded_averaging,
    simulate_martingale_2x,
    simulate_trend_bounded_averaging,
    simulate_trend_twin_order,
)


def _mk_bars(closes: list[float], start_hour: int = 8) -> list[Bar15m]:
    base_ts = int(datetime(2026, 11, 10, start_hour, 0, tzinfo=UTC).timestamp() * 1000)
    bars: list[Bar15m] = []
    for idx, c in enumerate(closes):
        bars.append(
            Bar15m(
                ts_ms=base_ts + idx * 900_000,
                open=c,
                high=c + 1.5,
                low=c - 1.5,
                close=c,
            )
        )
    return bars


def test_martingale_blows_up_on_one_way_crash():
    # Naik stabil agar EMA50 bullish -> lalu crash -$120 satu arah tanpa pullback
    closes = [3900.0 + (i * 0.2) for i in range(65)] + [3913.0 - (i * 4.0) for i in range(35)]
    res = simulate_martingale_2x(_mk_bars(closes), deposit=1000.0, grid_step=6.0)
    assert res.blown_up is True
    assert res.final_equity <= 150.0


def test_bounded_averaging_caps_loss_at_hard_basket_sl():
    # Crash terus menerus setelah RSI oversold -> harus stop di hard_basket_sl_usd ($60) tanpa blowup
    closes = [3900.0 for _ in range(45)] + [3900.0 - (i * 3.0) for i in range(40)]
    res = simulate_bounded_averaging(_mk_bars(closes, start_hour=6), deposit=1000.0, hard_basket_sl_usd=60.0)
    assert res.blown_up is False
    assert res.max_dd_usd < 120.0
    if res.losses > 0:
        assert res.avg_loss == -60.0


def test_trend_bounded_avg_respects_ema200_and_never_blows_up():
    closes = [3900.0 + (i * 0.3) for i in range(220)] + [3966.0 - (i * 2.5) for i in range(30)]
    res = simulate_trend_bounded_averaging(_mk_bars(closes, start_hour=8), deposit=1000.0, hard_basket_sl_usd=45.0)
    assert res.blown_up is False
    assert res.max_layers_used <= 4


def test_trend_twin_order_runs_with_bounded_risk():
    closes = [3880.0 + (i * 0.5) for i in range(70)] + [3915.0, 3918.0, 3922.0, 3926.0, 3930.0, 3920.0, 3910.0]
    res = simulate_trend_twin_order(_mk_bars(closes, start_hour=8), deposit=1000.0)
    assert res.blown_up is False
    assert res.max_layers_used == 2
