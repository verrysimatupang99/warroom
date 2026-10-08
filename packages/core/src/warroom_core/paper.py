"""Deterministic in-memory paper executor for the signal pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from warroom_core.signal import MarketData, RiskPolicy, Signal, evaluate_risk


@dataclass(frozen=True, slots=True)
class PaperRecord:
    signal_id: str
    status: str
    reason: str
    recorded_at: datetime
    price: float | None = None
    risk_usd: float | None = None


class PaperExecutor:
    """Paper-only executor; it has no venue client and cannot place orders."""

    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy
        self.records: list[PaperRecord] = []
        self._seen: set[str] = set()

    def submit(self, signal: Signal, data: MarketData, *, now: datetime | None = None) -> PaperRecord:
        recorded_at = now or datetime.now(UTC)
        if signal.signal_id in self._seen:
            return PaperRecord(signal.signal_id, "duplicate", "signal_already_seen", recorded_at)
        self._seen.add(signal.signal_id)
        decision = evaluate_risk(signal, data, self.policy, now=recorded_at)
        if not decision.allowed:
            record = PaperRecord(signal.signal_id, "rejected", decision.reason, recorded_at)
        else:
            record = PaperRecord(
                signal.signal_id, "filled", "paper_fill", recorded_at,
                price=data.price, risk_usd=decision.size_usd,
            )
        self.records.append(record)
        return record
