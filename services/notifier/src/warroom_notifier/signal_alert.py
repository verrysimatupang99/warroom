"""Render unified paper signals for existing alert transports."""

from __future__ import annotations

from warroom_core.signal import Signal


def format_signal_alert(signal: Signal) -> tuple[str, str, dict[str, object]]:
    """Return subject/message/payload without credentials or live claims."""
    subject = f"Paper signal · {signal.market} · {signal.instrument}"
    message = (
        f"[PAPER] {signal.strategy} {signal.direction.upper()} {signal.instrument}\n"
        f"Entry: {signal.entry} | Stop: {signal.stop} | Target: {signal.target}\n"
        f"Confidence: {signal.confidence} | Freshness: {signal.freshness_s}s\n"
        f"Reason: {signal.reason}\n"
        f"Expires: {signal.expires_at.isoformat()}"
    )
    payload: dict[str, object] = {
        "signal_id": signal.signal_id,
        "market": signal.market,
        "venue": signal.venue,
        "instrument": signal.instrument,
        "strategy": signal.strategy,
        "direction": signal.direction,
        "entry": signal.entry,
        "stop": signal.stop,
        "target": signal.target,
        "confidence": signal.confidence,
        "freshness_s": signal.freshness_s,
        "mode": "paper",
    }
    return subject, message, payload
