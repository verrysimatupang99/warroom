"""Router governance — parameter, usulan (proposal), kill switch AI, kejadian (events).

Diekstrak dari app.py (P1-2, langkah 6). Refactor murni: path, status kode, dan
auth dependency (termasuk `require_role("owner")`) tidak berubah.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from warroom_core import autonomy
from warroom_core.db import User, session_scope

from warroom_api import auth
from warroom_api.providers import provider_ringkas

router = APIRouter()


# --- P5: parameter, usulan, kill switch AI -------------------------------------------


@router.get("/api/v1/params")
def params(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    from warroom_core.db import Parameter

    with session_scope() as s:
        rows = s.scalars(select(Parameter).order_by(Parameter.name)).all()
        data = [
            {
                "nama": p.name,
                "nilai": p.value_json,
                "batas": p.bounds_json,
                "terkunci": p.locked,
                "scope": p.scope,
                "catatan": p.note,
                "diperbarui": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in rows
        ]
    return {"params": data, "count": len(data)}


@router.get("/api/v1/proposals")
def proposals(
    user: Annotated[User, Depends(auth.current_user)],
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    from warroom_core.db import Proposal

    with session_scope() as s:
        rows = s.scalars(
            select(Proposal).order_by(Proposal.created_at.desc()).limit(limit)
        ).all()
        data = [
            {
                "id": pr.id,
                "parameter": pr.parameter_name,
                "dari": pr.from_json,
                "ke": pr.to_json,
                "alasan": pr.reason,
                "bukti": pr.evidence_json,
                "gate": pr.gate_verdict,
                "status": pr.status,
                "ditolak_karena": pr.rejected_reason,
                "diputuskan_oleh": pr.decided_by,
                "diterapkan_pada": pr.applied_at.isoformat() if pr.applied_at else None,
                "config_hash": pr.config_hash,
                "dibuat": pr.created_at.isoformat() if pr.created_at else None,
            }
            for pr in rows
        ]
    return {"proposals": data, "count": len(data)}


@router.post("/api/v1/proposals/{pid}/apply")
def proposal_apply(
    pid: int, user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    with session_scope() as s:
        ok = autonomy.terapkan(s, pid, actor=user.username)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="usulan tidak bisa diterapkan (sudah diterapkan atau parameter terkunci)",
        )
    return {"ok": True, "oleh": user.username}


@router.post("/api/v1/proposals/{pid}/rollback")
def proposal_rollback(
    pid: int, user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    with session_scope() as s:
        ok = autonomy.rollback(s, pid, actor=user.username)
    if not ok:
        raise HTTPException(status_code=409, detail="usulan belum pernah diterapkan")
    return {"ok": True, "oleh": user.username}


@router.get("/api/v1/ai/status")
def ai_status(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    from warroom_core.db import LLMCall, Proposal

    with session_scope() as s:
        return {
            "kill_switch": autonomy.kill_switch_aktif(s),
            "usulan_menunggu": s.scalar(
                select(func.count()).select_from(Proposal).where(Proposal.status == "butuh_manusia")
            )
            or 0,
            "panggilan_llm": s.scalar(select(func.count()).select_from(LLMCall)) or 0,
            # Kesehatan provider (W6): mana yang gagal dan dengan kode apa.
            "provider": provider_ringkas(s),
        }


@router.post("/api/v1/ai/kill-switch")
def ai_kill_switch(
    body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    aktif = bool(body.get("aktif"))
    with session_scope() as s:
        ok = autonomy.set_kill_switch(s, aktif, actor=user.username)
    if not ok:
        raise HTTPException(status_code=409, detail="parameter kill switch belum terdaftar")
    return {"ok": True, "kill_switch": aktif, "oleh": user.username}


@router.get("/api/v1/events")
def events_list(
    user: Annotated[User, Depends(auth.current_user)],
    limit: int = Query(120, ge=1, le=500),
    tipe: str | None = Query(
        None,
        description=(
            "prefix tipe, boleh daftar dipisah koma (mis. 'trade.,signal.,verdict.'). "
            "Dipakai panel Kejadian Area: tanpa filter, 120 baris terakhir hampir pasti "
            "didominasi job.ran sehingga kejadian area tak pernah terlihat."
        ),
    ),
) -> dict[str, Any]:
    """Kejadian terakhir dari tabel `events` (append-only).

    Dipakai panel "Kejadian Area": SSE hanya mengirim kejadian BARU (tanpa
    Last-Event-ID ia mulai dari sekarang — perilaku yang benar untuk CPU/DB),
    sehingga panel selalu kosong sampai ada kejadian baru. Backfill lewat
    endpoint ini; angka & tipe apa adanya dari DB.
    """
    from warroom_core.db import Event

    with session_scope() as s:
        q = select(Event)
        if tipe:
            from sqlalchemy import or_

            prefiks = [t.strip() for t in tipe.split(",") if t.strip()]
            q = q.where(or_(*[Event.type.like(f"{p}%") for p in prefiks]))
        rows = s.scalars(q.order_by(Event.id.desc()).limit(limit)).all()
        return {
            "events": [
                {
                    "id": e.id,
                    "type": e.type,
                    "actor": e.actor,
                    "severity": e.severity,
                    "payload": e.payload_json,
                    "fact_ids": e.fact_ids,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in rows
            ],
            "count": len(rows),
        }
