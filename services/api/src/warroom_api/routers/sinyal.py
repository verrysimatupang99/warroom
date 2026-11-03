"""Ingest sinyal eksternal — mis. live feed dari akun Telegram di instabox testing.

Kontrak untuk sisi pengirim (contoh curl ada di docstring bawah):
  POST /api/v1/sinyal/telegram  {pasar, simbol, arah, entry?, sl?, tp1?, catatan?}

Yang ditulis: fakta kind `signal`, key `{pasar}/{simbol}`, source
`telegram-feed:{akun}` (akun = username pembuat sesi, jujur asalnya).
Ditolak bila field wajib hilang atau arah bukan LONG/SHORT — tidak ada tebakan.

Auth: operator ke atas (feed memakai sesi/token layanan, bukan anonim).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from warroom_core.db import User, session_scope
from warroom_core.db.models import Fact

from warroom_api import auth

router = APIRouter()

ARAH_SAH = {"LONG", "SHORT"}


class SinyalTelegram(BaseModel):
    pasar: str = Field(min_length=2, max_length=24)
    simbol: str = Field(min_length=2, max_length=32)
    arah: str = Field(min_length=4, max_length=5)
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    catatan: str = Field(default="", max_length=500)


@router.post("/api/v1/sinyal/telegram")
def terima_sinyal_telegram(
    body: SinyalTelegram, user: Annotated[User, Depends(auth.current_user)]
) -> dict[str, Any]:
    if user.role not in ("owner", "operator"):
        raise HTTPException(status_code=403, detail="feed sinyal butuh peran operator")
    arah = body.arah.upper().strip()
    if arah not in ARAH_SAH:
        raise HTTPException(
            status_code=422,
            detail={"code": "arah_tidak_sah", "message": "arah harus LONG atau SHORT"},
        )
    pasar = body.pasar.lower().strip()
    simbol = body.simbol.upper().strip()
    nilai = {
        "pasar": pasar,
        "simbol": simbol,
        "arah": arah,
        "entry": body.entry,
        "sl": body.sl,
        "tp1": body.tp1,
        "catatan": body.catatan,
        "status": "kandidat",
        "kejujuran": "sinyal feed eksternal — belum lolos gate statistik War Room",
    }
    isi = json.dumps(nilai, sort_keys=True, default=str)
    with session_scope() as s:
        s.add(
            Fact(
                kind="signal",
                key=f"{pasar}/{simbol}",
                value_json=nilai,
                source=f"telegram-feed:{user.username}",
                observed_at=datetime.now(UTC),
                ttl_s=21_600,
                hash=hashlib.sha256(isi.encode()).hexdigest(),
            )
        )
        s.flush()
    return {"ok": True, "kind": "signal", "key": f"{pasar}/{simbol}"}
