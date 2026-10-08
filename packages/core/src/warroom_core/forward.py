"""Small forward-validation ledger for paper signals."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from warroom_core.signal import Signal


@dataclass(frozen=True, slots=True)
class ForwardRecord:
    signal: Signal
    status: str
    entry_price: float
    created_at: datetime
    exit_price: float | None = None
    closed_at: datetime | None = None
    fee_bps: float = 0.0

    @property
    def gross_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        direction = -1 if self.signal.direction in {"short", "no"} else 1
        return (self.exit_price - self.entry_price) * direction

    @property
    def net_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        fee = (self.entry_price + self.exit_price) * self.fee_bps / 10_000
        return round(self.gross_pnl - fee, 8)


class ForwardLedger:
    def __init__(self) -> None:
        self.records: list[ForwardRecord] = []
        self._index: dict[str, int] = {}

    def record_signal(
        self, signal: Signal, *, observed_price: float, now: datetime | None = None
    ) -> ForwardRecord:
        if signal.signal_id in self._index:
            return self.records[self._index[signal.signal_id]]
        timestamp = now or datetime.now(UTC)
        record = ForwardRecord(signal, "open", observed_price, timestamp)
        self._index[signal.signal_id] = len(self.records)
        self.records.append(record)
        return record

    def close(
        self, signal_id: str, exit_price: float, closed_at: datetime, *, fee_bps: float = 0.0
    ) -> ForwardRecord:
        if signal_id not in self._index:
            raise KeyError(signal_id)
        index = self._index[signal_id]
        current = self.records[index]
        if current.status == "closed":
            return current
        updated = replace(
            current, status="closed", exit_price=exit_price,
            closed_at=closed_at, fee_bps=fee_bps,
        )
        self.records[index] = updated
        return updated


def outcome_summary(records: list[ForwardRecord]) -> dict[str, int | float]:
    closed = [record for record in records if record.status == "closed"]
    net = round(sum(record.net_pnl for record in closed), 8)
    return {
        "total": len(records), "open": len(records) - len(closed), "closed": len(closed),
        "wins": sum(record.net_pnl > 0 for record in closed),
        "losses": sum(record.net_pnl <= 0 for record in closed), "net_pnl": net,
    }
