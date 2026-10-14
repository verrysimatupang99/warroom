"""Router live (P6) — kesiapan arming, grant, aksi gate, uji kering (dry-run).

Diekstrak dari app.py (P1-2). Refactor murni: path, status kode, dan auth
dependency (owner/operator) tidak berubah. Endpoint di sini **tidak pernah**
mengeksekusi order; hanya memeriksa grant.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from warroom_core.db import Grant, User, session_scope

from warroom_api import auth, live

router = APIRouter()


@router.get("/api/v1/live/arming")
def live_arming(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    return live.arming_status().to_dict()


@router.get("/api/v1/live/grants")
def live_grants(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    with session_scope() as s:
        rows = s.scalars(select(Grant).order_by(Grant.granted_at.desc()).limit(100)).all()
        data = [
            {
                "id": g.id,
                "scope": g.scope,
                "oleh": g.granted_by,
                "message_id": g.message_id,
                "alasan": g.reason,
                "diberikan": g.granted_at.isoformat() if g.granted_at else None,
                "kedaluwarsa": g.expires_at.isoformat() if g.expires_at else None,
                "dicabut": g.revoked_at.isoformat() if g.revoked_at else None,
            }
            for g in rows
        ]
    return {"grants": data, "count": len(data), "scope_dikenal": list(live.SCOPE_DIKENAL)}


@router.post("/api/v1/live/grant")
def live_grant(
    body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    try:
        with session_scope() as s:
            hasil = live.grant_baru(
                s,
                scope=str(body.get("scope", "")),
                granted_by=user.username,
                message_id=str(body.get("message_id", "")),
                reason=str(body.get("reason", "")),
                ttl_s=body.get("ttl_s", 3600),
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, **hasil}


@router.post("/api/v1/live/action")
def live_action(
    body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    """Tidak pernah mengeksekusi apa pun. Hanya memeriksa grant → 409 bila kurang."""
    scope = str(body.get("scope", ""))
    with session_scope() as s:
        kurang = live.scope_kurang(s, scope)
    if kurang:
        raise HTTPException(
            status_code=409,
            detail={
                "aksi": scope,
                "kurang": kurang,
                "catatan": "eksekusi nyata tetap milik owner di luar repo ini",
            },
        )
    return {
        "ok": True,
        "scope": scope,
        "catatan": "grant lengkap; tidak ada aksi yang dijalankan oleh API ini",
    }


@router.post("/api/v1/live/dry-run")
def live_dry_run(
    body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("operator"))]
) -> dict[str, Any]:
    """Uji kering read-only: ukur kedalaman buku (tanpa order) — P6-T3.

    Hanya subperintah yang di-allowlist yang diterima. Subperintah lain → **422**,
    bukan 200-dengan-pesan-gagal: permintaannya memang tidak sah, dan pemanggil
    tidak boleh menganggapnya berhasil. (Temuan audit 5 Okt 2026.)
    """
    sub = str(body.get("subperintah", "depth"))
    if sub not in live.SUBPERINTAH_DRY_RUN_DIIZINKAN:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "subperintah_ditolak",
                "message": (
                    f"subperintah '{sub}' tidak diizinkan untuk uji kering; "
                    f"pilihan: {', '.join(sorted(live.SUBPERINTAH_DRY_RUN_DIIZINKAN))}"
                ),
            },
        )
    return live.run_dry_depth(sub)
