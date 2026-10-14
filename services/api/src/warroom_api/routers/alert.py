"""Router alert & status transport notifier (W5).

Diekstrak dari app.py (P1-2). Refactor murni.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from warroom_core.db import Alert, Event, User, session_scope

from warroom_api import auth

router = APIRouter()


@router.get("/api/v1/alerts")
def alerts_list(
    user: Annotated[User, Depends(auth.current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Alert + status transport. Transport kosong **tidak pernah** diklaim terkirim."""
    with session_scope() as s:
        rows = s.scalars(
            select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
        ).all()
        percobaan = s.scalar(
            select(Event.payload_json)
            .where(Event.type == "alert.sent")
            .order_by(Event.id.desc())
            .limit(1)
        )
        data = [
            {
                "id": a.id,
                "severity": a.severity,
                "subject": a.subject,
                "message": a.message,
                "suggested_action": a.suggested_action,
                "ack_at": a.ack_at.isoformat() if a.ack_at else None,
                "snooze_until": a.snooze_until.isoformat() if a.snooze_until else None,
                "created_at": a.created_at.isoformat(),
                "percobaan": a.attempts or 0,
                "kesalahan_terakhir": a.last_error,
                # None = belum pernah dicoba; True = percobaan terakhir sukses.
                "terakhir_ok": None if not (a.attempts or 0) else a.last_error is None,
            }
            for a in rows
        ]
    transport: dict[str, Any]
    try:
        from warroom_notifier.transport import transport_from_env

        tr = transport_from_env()
        transport = {"nama": tr.name, "terkonfigurasi": tr.name != "null"}
    except Exception as exc:  # noqa: BLE001 — jangan matikan halaman karena transport
        transport = {"nama": "error", "terkonfigurasi": False, "detail": type(exc).__name__}
    return {
        "transport": transport,
        "terbuka": sum(1 for d in data if d["ack_at"] is None),
        "alerts": data,
        "percobaan_terakhir": percobaan,
    }


@router.post("/api/v1/alerts/{aid}/ack")
def alerts_ack(
    aid: int,
    body: dict[str, Any],
    user: Annotated[User, Depends(auth.require_role("operator"))],
) -> dict[str, Any]:
    """Ack alert (atau snooze bila ``snooze_s`` > 0). Alert tidak pernah dihapus."""
    from datetime import timedelta

    snooze_s = max(0, int(body.get("snooze_s") or 0))
    now = datetime.now(UTC)
    with session_scope() as s:
        a = s.get(Alert, aid)
        if a is None:
            raise HTTPException(status_code=404, detail="alert tidak ditemukan")
        if snooze_s > 0:
            a.snooze_until = now + timedelta(seconds=snooze_s)
            a.ack_at = None
        else:
            a.ack_at = now
            a.snooze_until = None
        s.add(
            Event(
                type="alert.ack",
                actor=user.username,
                payload_json={"alert_id": aid, "snooze_s": snooze_s},
                fact_ids=[],
                severity="info",
            )
        )
    return {"ok": True, "id": aid, "snooze_s": snooze_s}
