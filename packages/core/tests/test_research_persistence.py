from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from warroom_core.db.models import ResearchRecord, ResearchRun
from warroom_core.research import ResearchValidationError, build_research_run_preview
from warroom_core.specs import ExecutionSpec, HypothesisSpec


def _specs() -> tuple[HypothesisSpec, ExecutionSpec]:
    return (
        HypothesisSpec(
            hypothesis_id="h-001", market="crypto", instrument_or_pool="BTCUSDT",
            rule_version="rule-v1", input_fields=("price", "funding_rate"),
            lookahead_policy="at-or-before-decision", cost_policy="all-in",
            session_timezone="UTC", entry_rule="signal", exit_rule="reversal",
            stop_rule="1R", position_sizing="fixed-risk", baseline="buy-hold",
            split="frozen:split-001", population="liquid observations",
            invalidation="net expectancy <= 0",
        ),
        ExecutionSpec(
            entry_price_rule="next ask", exit_price_rule="next bid", stop_rule="gap-aware stop",
            time_stop="4h", fee_policy="recorded venue fee", slippage_policy="recorded spread",
            latency_policy="measured", fill_policy="partial fills recorded", risk_budget="0.5%",
            size_rule="risk / loss per unit", no_trade_conditions=("stale data",),
            venue="research-only", mode="paper", as_of=datetime(2026, 10, 8, tzinfo=UTC),
        ),
    )


def test_preview_versions_both_contracts_and_binds_artifact_provenance() -> None:
    hypothesis, execution = _specs()
    preview = build_research_run_preview(
        research_key="study-001",
        hypothesis=hypothesis,
        execution=execution,
        provenance={"collector": "fixture", "source": "local-test"},
        artifacts=(
            {"kind": "dataset", "uri": "file:///research/data.csv", "sha256": "a" * 64},
        ),
    )

    assert preview["status"] == "draft"
    assert preview["hypothesis_version"] == "rule-v1"
    assert len(preview["hypothesis_hash"]) == 64
    assert len(preview["execution_hash"]) == 64
    assert preview["artifacts"][0]["sha256"] == "a" * 64
    assert preview["provenance"]["source"] == "local-test"


def test_preview_fails_closed_without_provenance_or_artifact_hash() -> None:
    hypothesis, execution = _specs()
    with pytest.raises(ResearchValidationError, match="provenance"):
        build_research_run_preview("study-001", hypothesis, execution, {}, ())
    with pytest.raises(ResearchValidationError, match="sha256"):
        build_research_run_preview(
            "study-001", hypothesis, execution, {"source": "fixture"},
            ({"kind": "dataset", "uri": "file:///data.csv", "sha256": "missing"},),
        )


def test_research_models_keep_contracts_and_artifacts_append_only_shape() -> None:
    run_columns = {column.key for column in inspect(ResearchRun).columns}
    record_columns = {column.key for column in inspect(ResearchRecord).columns}

    assert {
        "hypothesis_json", "execution_json", "hypothesis_hash", "execution_hash", "provenance_json"
    } <= run_columns
    assert {"research_run_id", "uri", "sha256", "provenance_json", "status"} <= record_columns
    assert ResearchRun.__table__.c.status.default.arg == "draft"
    assert ResearchRecord.__table__.c.status.default.arg == "observed"
