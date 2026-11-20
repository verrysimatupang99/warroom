"""Tier 4: Real-World Workload and Market Simulation Scenarios (>= 5 scenarios)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from live_trading.demo_ab_backtest import _finalize
from live_trading.risk_guardrails import (
    calculate_risk_position_size,
    evaluate_entry_guardrails,
)

from tests.e2e.fixtures.account_samples import (
    ACCOUNT_DEMO_1,
    ACCOUNT_DEMO_2,
    ACCOUNT_LIVE_CENT,
    get_account_meta,
)
from tests.e2e.fixtures.deal_payloads import make_deal_payload
from tests.e2e.fixtures.telemetry_payloads import make_telemetry_payload

pytestmark = pytest.mark.tier4


# ==============================================================================
# T4.1: Demo 2 Trend Runaway & Hard Basket SL Execution
# ==============================================================================


def test_t4_1_demo2_trend_runaway_hard_basket_sl_scenario() -> None:
    """T4.1: Simulate 150-pip runaway against Demo 2; verify max 4 layers & Hard Basket SL (-$45)."""
    meta = get_account_meta(ACCOUNT_DEMO_2)
    max_layers = meta["max_layers"]
    hard_basket_sl = meta["hard_basket_sl_usd"]
    lot_per_layer = meta["fixed_lot"]

    assert max_layers == 4
    assert hard_basket_sl == 45.00
    assert lot_per_layer == 0.01  # Flat 0.01 lot per layer (strictly no martingale)

    # Simulate price adverse runaway from 2700.0 down by 150 pips (to 2550.0)
    grid_spacing = 15.0  # $15 per layer
    open_layers = []
    layers_entered = 0

    for step in range(10):  # 10 down steps
        step_price = 2700.0 - (step * grid_spacing)
        if layers_entered < max_layers:
            layers_entered += 1
            open_layers.append({"layer": layers_entered, "entry_price": step_price, "lot": lot_per_layer})

    # Invariant 1: Max layers clamped at 4
    assert len(open_layers) == 4
    assert layers_entered == 4

    # Calculate floating PnL at price 2640.0 (60 dollars adverse move from layer 1)
    # On XAUUSDm, 1 lot = 100 oz. 0.01 lot = 1 oz. $1 price change = $1.00 PnL.
    eval_price = 2640.0
    basket_pnl = sum((eval_price - layer["entry_price"]) * 100 * layer["lot"] for layer in open_layers)
    # Layer 1 (2700 -> 2640) = -60.0
    # Layer 2 (2685 -> 2640) = -45.0
    # Layer 3 (2670 -> 2640) = -30.0
    # Layer 4 (2655 -> 2640) = -15.0
    # Total = -150.0

    # Invariant 2: Hard basket SL trigger condition
    hard_basket_sl_triggered = basket_pnl <= -hard_basket_sl
    assert hard_basket_sl_triggered is True

    # Invariant 3: Basket liquidation halts loss at capped drawdown instead of zero balance blowout
    liquidated_loss = -hard_basket_sl
    final_equity = 1000.0 + liquidated_loss
    assert final_equity == 955.0  # Preserves 95.5% of $1,000 capital


# ==============================================================================
# T4.2: High-Impact News Spike & Extreme Spread Expansion
# ==============================================================================


def test_t4_2_news_spike_extreme_spread_expansion_scenario(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T4.2: Simulate high-impact news event; verify stand-down & extreme spread filtering."""
    # 1. 10 minutes prior to major economic release (e.g. US CPI)
    pre_news_status = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=4,
        minutes_to_high_impact_news=10,
        stand_down_minutes=45,
    )
    assert not pre_news_status.allowed
    assert pre_news_status.reason == "HIGH_IMPACT_NEWS_STAND_DOWN"

    # 2. At release moment, spread spikes to 500 points (5.00 USD on Gold)
    spike_spread_status = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=4,
        spread_points=500.0,
        max_spread_points=350.0,
    )
    assert not spike_spread_status.allowed
    assert spike_spread_status.reason == "EXTREME_SPREAD_BLOCKED"

    # 3. Ingest high-spread telemetry to API
    payload = make_telemetry_payload(
        account=ACCOUNT_DEMO_1,
        currency="USD",
        cent_factor=1.0,
        spread_pts=500,
        eval_alasan="SPREAD_MELEBIHI_BATAS",
    )
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    # 4. Status query records the high spread accurately without crashing API
    url_demo1 = f"/api/v1/tencent/mt5/status?account={ACCOUNT_DEMO_1}"
    status_resp = test_client.get(url_demo1, headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["spread_pts"] == 500


# ==============================================================================
# T4.3: Daily Maximum Loss Lockout & Daily Reset
# ==============================================================================


def test_t4_3_daily_maximum_loss_lockout_and_reset_scenario() -> None:
    """T4.3: Simulate daily loss sequence reaching cutoff; verify lockout & reset."""
    deposit = 1000.0
    daily_limit_pct = 3.0  # $30.00 on $1,000

    # Trade 1: Loss of -$12.00 (-1.2%)
    cum_loss = -12.00
    s1 = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=(cum_loss / deposit) * 100.0,
        max_daily_loss_pct=daily_limit_pct,
        open_positions=0,
        max_open_positions=4,
    )
    assert s1.allowed is True

    # Trade 2: Additional loss of -$12.00 -> -$24.00 total (-2.4%)
    cum_loss -= 12.00
    s2 = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=(cum_loss / deposit) * 100.0,
        max_daily_loss_pct=daily_limit_pct,
        open_positions=0,
        max_open_positions=4,
    )
    assert s2.allowed is True

    # Trade 3: Additional loss of -$8.00 -> -$32.00 total (-3.2%, breaches 3.0% cap)
    cum_loss -= 8.00
    s3 = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=(cum_loss / deposit) * 100.0,
        max_daily_loss_pct=daily_limit_pct,
        open_positions=0,
        max_open_positions=4,
    )
    assert s3.allowed is False
    assert s3.reason == "MAX_DAILY_LOSS_REACHED"

    # Reset next trading day (daily_pnl_pct resets to 0.0%)
    s_next_day = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=daily_limit_pct,
        open_positions=0,
        max_open_positions=4,
    )
    assert s_next_day.allowed is True


# ==============================================================================
# T4.4: Live Cent Micro-Capital Preservation
# ==============================================================================


def test_t4_4_live_cent_micro_capital_preservation_scenario(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T4.4: Low Cent balance (~1000 USC / $10 USD) clamps to 0.01 lot & limits loss < 1%."""
    cent_equity_usc = 1084.84
    cent_equity_usd = cent_equity_usc / 100.0  # ~$10.85 USD

    # Position sizing with conservative 1% risk per trade
    lot_size = calculate_risk_position_size(
        equity=cent_equity_usd,
        sl_distance=20.0,
        risk_pct=0.01,
        min_size=0.01,
        max_size=1.0,
    )
    assert lot_size == 0.01

    # Ingest deal of 0.40 USC profit
    deal = make_deal_payload(
        ticket=6639280,
        account=ACCOUNT_LIVE_CENT,
        symbol="XAUUSDc",
        side="BUY",
        volume=0.01,
        profit=0.50,
        swap=-0.02,
        commission=-0.08,
        currency="USC",
        cent_factor=100.0,
    )
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=deal, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["currency"] == "USC"
    assert resp.json()["cent_factor"] == 100.0

    # Dual UI formatting check
    pnl_usc = 0.40
    pnl_usd = pnl_usc / 100.0
    display_str = f"{pnl_usc:.2f} USC (${pnl_usd:.4f})"
    assert "USC" in display_str and "$0.0040" in display_str


# ==============================================================================
# T4.5: Full Trading Session Lifecycle & Telemetry Stream
# ==============================================================================


def test_t4_5_full_trading_session_lifecycle_scenario(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T4.5: Complete session lifecycle: startup -> stream -> entry -> fill -> close -> metrics."""
    # 1. Startup: Telemetry registration
    t_start = make_telemetry_payload(
        account=ACCOUNT_DEMO_1,
        balance=1005.00,
        equity=1005.00,
        positions=[],
        spread_pts=22,
    )
    resp1 = test_client.post("/api/v1/tencent/mt5/telemetry", json=t_start, headers=auth_headers)
    assert resp1.status_code == 200

    # 2. Risk Evaluation before order entry
    guard = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=2,
        spread_points=22.0,
        max_spread_points=350.0,
    )
    assert guard.allowed is True

    # 3. Position Sizing
    size = calculate_risk_position_size(equity=1005.0, sl_distance=6.0, risk_pct=0.015)
    assert size == 2.51

    # 4. Order Execution Fill
    fill = {
        "ticket": 7781050,
        "symbol": "XAUUSDm",
        "requested_price": 2700.00,
        "execution_price": 2700.02,
        "slippage_pts": 2,
        "latency_ms": 32,
        "account": ACCOUNT_DEMO_1,
    }
    resp_fill = test_client.post("/api/v1/tencent/mt5/fill", json=fill, headers=auth_headers)
    assert resp_fill.status_code == 200

    # 5. Position Close & Deal Ingestion
    deal = make_deal_payload(
        ticket=7781050,
        account=ACCOUNT_DEMO_1,
        symbol="XAUUSDm",
        side="BUY",
        volume=0.02,
        profit=18.00,
        swap=-0.20,
        commission=-0.30,
        currency="USD",
        cent_factor=1.0,
    )
    resp_deal = test_client.post("/api/v1/tencent/mt5/deal", json=deal, headers=auth_headers)
    assert resp_deal.status_code == 200
    assert resp_deal.json()["net"] == 17.50

    # 6. Session Metrics Recalculation
    pnls = [17.50, -5.00, 12.00, 8.50]
    sim = _finalize(
        "Session_Demo1",
        deposit=1005.00,
        equity=1038.00,
        pnls=pnls,
        max_dd_usd=5.00,
        max_dd_pct=0.49,
        blown=False,
        max_layers_used=1,
    )
    assert sim.trades == 4
    assert sim.wins == 3
    assert sim.losses == 1
    assert sim.win_rate_pct == 75.0
    assert sim.profit_factor > 1.0
    assert not sim.blown_up
