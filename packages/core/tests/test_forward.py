from datetime import UTC, datetime, timedelta

from warroom_core.forward import ForwardLedger, outcome_summary
from warroom_core.signal import Signal


def sig(i, strategy="smc"):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Signal(
        i, "crypto", "okx", "BTCUSDT", strategy, "long", 100, 98, 104, 2, .8,
        now, now + timedelta(minutes=5), 1, "test",
    )


def test_ledger_dedupes_and_records_outcomes():
    ledger = ForwardLedger()
    ledger.record_signal(sig("a"), observed_price=100)
    ledger.record_signal(sig("a"), observed_price=100)
    ledger.close("a", exit_price=104, closed_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC), fee_bps=10)
    assert len(ledger.records) == 1
    assert ledger.records[0].status == "closed"
    assert ledger.records[0].net_pnl > 0


def test_summary_is_explicit_about_open_expired_and_closed():
    ledger = ForwardLedger()
    ledger.record_signal(sig("open"), observed_price=100)
    ledger.record_signal(sig("closed"), observed_price=100)
    ledger.close("closed", 98, datetime(2026, 1, 1, 0, 1, tzinfo=UTC), fee_bps=0)
    summary = outcome_summary(ledger.records)
    assert summary == {"total": 2, "open": 1, "closed": 1, "wins": 0, "losses": 1, "net_pnl": -2.0}
