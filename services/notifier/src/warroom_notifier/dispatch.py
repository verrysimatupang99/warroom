"""Pengiriman alert + jejak audit (P1-T8).

Kontrak:

- Alert **selalu** ada di DB sebelum dikirim (DB = sumber kebenaran, bukan transport).
- Setiap percobaan kirim menulis event `alert.sent` dengan `ok` dan `detail`. Kegagalan
  **tidak** diubah menjadi "terkirim"; juga tidak langsung diulang tanpa batas (max 3 percobaan).
- Alert yang tidak bisa dikirim tetap terlihat sebagai `alerts_terbuka` di /metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event

from warroom_notifier.transport import Transport, transport_from_env

__all__ = ["MAX_PERCOBAAN", "kirim_tertunda", "tandai_terkirim"]

MAX_PERCOBAAN = 3


def kirim_tertunda(
    s: SASession,
    transport: Transport | None = None,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Kirim alert terbuka yang belum lewat batas percobaan. Kembalikan ringkasan.

    Alert yang sudah mencapai ``MAX_PERCOBAAN`` **dilewati** dan **tidak** menghabiskan jatah
    ``limit``: dulu ia ikut dihitung, sehingga ketika cukup banyak alert lama macet, alert
    BARU tidak pernah terkirim sama sekali (bug nyata yang ditemukan 3 Okt).
    """
    tr = transport or transport_from_env()
    kandidat = s.scalars(
        select(Alert)
        .where(Alert.ack_at.is_(None))
        .order_by(Alert.created_at.asc())
        .limit(max(limit * 20, 50))
    ).all()

    hasil: list[dict[str, object]] = []
    dicoba = 0
    dilewati = 0
    for a in kandidat:
        if (a.attempts or 0) >= MAX_PERCOBAAN:
            dilewati += 1
            continue
        if dicoba >= limit:
            break
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
        # Catat percobaan di baris alert (bukan hanya di event) supaya batas terlihat di UI.
        a.attempts = (a.attempts or 0) + 1
        a.last_error = None if res.ok else str(res.detail)[:200]
        # Auto-ack tier INFO yang TERKIRIM sukses (Keputusan 15 Okt, rekomendasi #6):
        # alert info = pengumuman sinyal/trade — begitu terkirim misinya selesai,
        # tidak boleh menumpuk sebagai "51 alert terbuka". Warning/kritis tetap
        # terbuka sampai owner meng-ack. Gagal kirim tetap terbuka untuk retry.
        if res.ok and a.severity == "info":
            a.ack_at = datetime.now(UTC)
            a.last_error = None
        hasil.append({"alert_id": a.id, "ok": res.ok, "detail": res.detail})
        dicoba += 1
    if dilewati:
        hasil.append(
            {
                "alert_id": None,
                "ok": False,
                "detail": (
                    f"{dilewati} alert dilewati: sudah {MAX_PERCOBAAN} percobaan "
                    "(tetap terbuka di DB; ack manual atau perbaiki transport)"
                ),
            }
        )
    s.flush()
    return hasil


def tandai_terkirim(s: SASession, alert_id: int, *, kapan: datetime | None = None) -> bool:
    """Tandai alert selesai (ack) — dipakai setelah transport mengembalikan sukses."""
    a = s.get(Alert, alert_id)
    if a is None:
        return False
    a.ack_at = kapan or datetime.now(UTC)
    return True