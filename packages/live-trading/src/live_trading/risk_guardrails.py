from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuardrailStatus:
    """Status evaluasi pengaman risiko sebelum entry posisi baru."""

    allowed: bool
    reason: str = "OK"


def calculate_risk_position_size(
    equity: float,
    sl_distance: float,
    risk_pct: float = 0.015,
    min_size: float = 0.01,
    max_size: float = 10.0,
) -> float:
    """Hitung ukuran posisi berbasis risiko tetap (1%-2% ekuitas per trade)."""
    if equity <= 0 or sl_distance <= 0:
        return min_size
    clamped_risk = min(max(risk_pct, 0.01), 0.02)
    risk_amount = equity * clamped_risk
    raw_size = risk_amount / sl_distance
    return round(min(max(raw_size, min_size), max_size), 2)


def evaluate_entry_guardrails(
    *,
    kill_switch_active: bool,
    daily_pnl_pct: float,
    max_daily_loss_pct: float,
    open_positions: int,
    max_open_positions: int,
    minutes_to_high_impact_news: int | None = None,
    stand_down_minutes: int = 45,
    spread_points: float | None = None,
    max_spread_points: float | None = None,
) -> GuardrailStatus:
    """Evaluasi seluruh guardrail sebelum bot membuka posisi baru."""
    if kill_switch_active:
        return GuardrailStatus(allowed=False, reason="GLOBAL_KILL_SWITCH_ACTIVE")
    if daily_pnl_pct <= -abs(max_daily_loss_pct):
        return GuardrailStatus(allowed=False, reason="MAX_DAILY_LOSS_REACHED")
    if open_positions >= max_open_positions:
        return GuardrailStatus(allowed=False, reason="MAX_OPEN_POSITIONS_REACHED")
    if (
        minutes_to_high_impact_news is not None
        and abs(minutes_to_high_impact_news) <= stand_down_minutes
    ):
        return GuardrailStatus(allowed=False, reason="HIGH_IMPACT_NEWS_STAND_DOWN")
    if (
        spread_points is not None
        and max_spread_points is not None
        and spread_points > max_spread_points
    ):
        return GuardrailStatus(allowed=False, reason="EXTREME_SPREAD_BLOCKED")
    return GuardrailStatus(allowed=True, reason="OK")
