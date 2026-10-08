import json
from datetime import UTC, datetime

import pytest
from warroom_core.specs import SPEC_SCHEMA_VERSION, ExecutionSpec, HypothesisSpec, SpecError


def test_hypothesis_spec_requires_falsifiable_research_contract() -> None:
    spec = HypothesisSpec(
        hypothesis_id="crypto-funding-001",
        market="crypto",
        instrument_or_pool="BTCUSDT",
        rule_version="v1",
        input_fields=("funding_rate", "mid_price"),
        lookahead_policy="features_at_or_before_decision_time",
        cost_policy="taker_fee_plus_spread_plus_slippage",
        session_timezone="UTC",
        entry_rule="funding percentile below p05",
        exit_rule="exit after 4h or signal reversal",
        stop_rule="1R invalidation",
        position_sizing="fixed risk fraction / loss per unit",
        baseline="random_entry_matched_horizon",
        split="walk_forward_v1",
        population="all BTCUSDT observations meeting liquidity filter",
        invalidation="net expectancy <= 0 in frozen test",
    )
    assert spec.is_complete() is True
    assert spec.to_dict()["hypothesis_id"] == "crypto-funding-001"


def test_hypothesis_spec_rejects_missing_invalidation() -> None:
    with pytest.raises(SpecError, match="invalidation"):
        HypothesisSpec(
            hypothesis_id="h1", market="crypto", instrument_or_pool="BTCUSDT",
            rule_version="v1", input_fields=("price",),
            lookahead_policy="t<=decision", cost_policy="all-in", session_timezone="UTC",
            entry_rule="x", exit_rule="y", stop_rule="z", position_sizing="risk",
            baseline="buy_hold", split="frozen", population="all", invalidation="",
        )


def test_execution_spec_requires_executable_price_and_fill_policy() -> None:
    spec = ExecutionSpec(
        entry_price_rule="next ask after signal",
        exit_price_rule="next bid after exit trigger",
        stop_rule="stop at invalidation with gap override",
        time_stop="4h",
        fee_policy="venue fee schedule as-of 2026-10-08",
        slippage_policy="depth-aware worst of p95 markout",
        latency_policy="signal-to-submit measured",
        fill_policy="partial fills and no-fill are recorded",
        risk_budget="0.5% equity",
        size_rule="risk budget / loss per unit",
        no_trade_conditions=("stale data", "spread above cap", "insufficient depth"),
        venue="binance",
        mode="paper",
        as_of=datetime(2026, 10, 8, tzinfo=UTC),
    )
    assert spec.is_executable_contract() is True
    assert spec.to_dict()["mode"] == "paper"


def test_execution_spec_rejects_live_without_explicit_grant() -> None:
    with pytest.raises(SpecError, match="live"):
        ExecutionSpec(
            entry_price_rule="ask", exit_price_rule="bid", stop_rule="stop",
            time_stop="none", fee_policy="known", slippage_policy="known",
            latency_policy="known", fill_policy="known", risk_budget="1%",
            size_rule="risk", no_trade_conditions=("stale",), venue="x",
            mode="live", as_of=datetime.now(UTC),
        )


def test_specs_have_canonical_json_and_stable_fingerprint() -> None:
    spec = HypothesisSpec(
        hypothesis_id="h1", market="idx", instrument_or_pool="BBCA",
        rule_version="v1", input_fields=("close", "volume"),
        lookahead_policy="t<=decision", cost_policy="all-in", session_timezone="Asia/Jakarta",
        entry_rule="breakout", exit_rule="reversal", stop_rule="1R",
        position_sizing="risk", baseline="buy_hold", split="frozen",
        population="all", invalidation="negative expectancy",
    )

    payload = json.loads(spec.to_json())
    assert payload["schema_version"] == SPEC_SCHEMA_VERSION
    assert payload["spec_type"] == "HypothesisSpec"
    assert payload["spec"]["input_fields"] == ["close", "volume"]
    assert spec.fingerprint() == spec.fingerprint()
    assert len(spec.fingerprint()) == 64


def test_execution_json_normalizes_timezone_aware_datetime() -> None:
    spec = ExecutionSpec(
        entry_price_rule="ask", exit_price_rule="bid", stop_rule="stop", time_stop="none",
        fee_policy="known", slippage_policy="known", latency_policy="known", fill_policy="known",
        risk_budget="1%", size_rule="risk", no_trade_conditions=("stale",), venue="x",
        mode="paper", as_of=datetime(2026, 10, 8, 1, 2, 3, 456000, tzinfo=UTC),
    )

    payload = json.loads(spec.to_json())
    assert payload["spec"]["as_of"] == "2026-10-08T01:02:03.456000Z"
    assert json.dumps(payload, sort_keys=True, separators=(",", ":")) == spec.to_json()
