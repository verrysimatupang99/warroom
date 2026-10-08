from datetime import UTC, datetime, timedelta

from warroom_core.signal import Signal
from warroom_notifier.signal_alert import format_signal_alert


def test_signal_alert_contains_only_signal_fields_and_paper_label():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    signal = Signal(
        "sig-1", "crypto", "mexc", "BTCUSDT", "smc", "long",
        100, 98, 104, 2, .8, now, now + timedelta(minutes=5), 3,
        "breakout + volume",
    )
    subject, message, payload = format_signal_alert(signal)
    assert subject == "Paper signal · crypto · BTCUSDT"
    assert "PAPER" in message
    assert "100" in message and "breakout + volume" in message
    assert payload["signal_id"] == "sig-1"
    assert payload["mode"] == "paper"
    assert "token" not in str(payload).lower()
