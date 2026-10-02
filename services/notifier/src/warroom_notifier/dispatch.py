"""Pengiriman alert + jejak audit (P1-T8).

Kontrak:

- Alert **selalu** ada di DB sebelum dikirim (DB = sumber kebenaran, bukan transport).
- Setiap percobaan kirim menulis event `alert.sent` dengan `ok` dan `detail`. Kegagalan
  **tidak** diubah menjadi "terkirim"; juga tidak langsung diulang tanpa batas (max 3 percobaan).
- Alert yang tidak bisa dikirim tetap terlihat sebagai `alerts_terbuka` di /metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event

from warroom_notifier.transport import Transport, transport_from_env

__all__ = ["MAX_PERCOBAAN", "kirim_tertunda", "tandai_terkirim"]

MAX_PERCOBAAN = 3
_JEDA = timedelta(minutes=5)


def _jumlah_percobaan(s: SASession, alert_id: int) -> int:
    baris = s.execute(
        select(Event.payload_json).where(Event.type == "alert.sent")
    ).all()
    return sum(1 for (p,) in baris if isinstance(p, dict) and p.get("alert_id") == alert_id)


def kirim_tertunda(
    s: SASession,
    transport: Transport | None = None,
    *,
    limit: int = 10,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Kirim alert terbuka yang belum pernah sukses dikirim. Kembalikan ringkasan percobaan."""
    tr = transport or transport_from_env()
    terbuka = s.scalars(
        select(Alert).where(Alert.ack_at.is_(None)).order_by(Alert.created_at.asc()).limit(limit)
    ).all()

    hasil: list[dict[str, object]] = []
    for a in terbuka:
        if _jumlah_percobaan(s, a.id) >= MAX_PERCOBAAN:
            hasil.append({"alert_id": a.id, "ok": False, "detail": "batas percobaan tercapai"})
            continue
        res = tr.send(
            a.subject,
            a.message,
            a.severity,
            {"suggested_action": a.suggested_action, "fact_ids": a.fact_ids},
        )
        s.add(
            Event(
                type="alert.sent",
                actor="notifier",
                payload_json={
                    "alert_id": a.id,
                    "subject": a.subject,
                    "transport": tr.name,
                    "ok": res.ok,
                    "detail": res.detail,
                },
                fact_ids=list(a.fact_ids or []),
                severity="info" if res.ok else "warning",
            )
        )
        hasil.append({"alert_id": a.id, "ok": res.ok, "detail": res.detail})
    s.flush()
    return hasil


def tandai_terkirim(s: SASession, alert_id: int, *, kapan: datetime | None = None) -> bool:
    """Tandai alert selesai (ack) — dipakai setelah transport mengembalikan sukses."""
    a = s.get(Alert, alert_id)
    if a is None:
        return False
    a.ack_at = kapan or datetime.now(UTC)
    return True