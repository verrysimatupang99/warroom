"""Router pengaturan — sakelar fitur yang boleh diubah owner dari UI.

Isi pertama: Laya AI. Laya NONAKTIF secara bawaan (timer systemd dimatikan);
menyalakannya dari menu Pengaturan menulis parameter `laya_enabled` SEKALIGUS
mencoba menyalakan/mematikan timer systemd, supaya satu sakelar = satu keadaan.
Hasil systemd dilaporkan apa adanya — kalau gagal, parameter tetap tersimpan dan
endpoint Laya menjawab 503 `laya_dinonaktifkan`/timer-mati dengan jujur.
"""

from __future__ import annotations

import subprocess
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from warroom_core.db import Event, Parameter, session_scope

from warroom_api import auth
from warroom_api.auth import User

router = APIRouter()

LAYA_PARAM = "laya_enabled"
LAYA_TIMER = "warroom-laya-verdict.timer"


def _baca_laya() -> bool:
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == LAYA_PARAM))
        return bool(p.value_json) if p is not None else False


def _systemd(aksi: str) -> tuple[bool, str]:
    """enable/disable timer lewat sudo. Kembalikan (ok, detail)."""
    try:
        r = subprocess.run(
            ["sudo", "-n", "systemctl", aksi, "--now", LAYA_TIMER],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if r.returncode != 0:
        return False, (r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}")[:200]
    return True, "ok"


def _timer_hidup() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "is-enabled", LAYA_TIMER],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "enabled"
    except (OSError, subprocess.SubprocessError):
        return False


@router.get("/api/v1/pengaturan/laya")
def laya_status(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    return {
        "aktif": _baca_laya(),
        "systemd_timer": _timer_hidup(),
        "catatan": (
            "Laya AI nonaktif secara bawaan. Menyalakannya mengaktifkan verdict "
            "Laya di forex + timer verdict tiap 60 detik."
        ),
    }


@router.post("/api/v1/pengaturan/laya")
def laya_setel(
    body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
) -> dict[str, Any]:
    aktif = bool(body.get("aktif"))
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == LAYA_PARAM))
        if p is None:
            p = Parameter(
                name=LAYA_PARAM, scope="global", value_json=aktif,
                locked=False, note="Sakelar Laya AI (menu Pengaturan).",
            )
            s.add(p)
        else:
            p.value_json = aktif
        s.add(
            Event(
                type="pengaturan.laya",
                actor=user.username,
                payload_json={"ke": aktif},
                fact_ids=[],
                severity="warning" if aktif else "info",
            )
        )
        s.flush()
    ok, detail = _systemd("enable" if aktif else "disable")
    return {
        "ok": True, "aktif": aktif, "oleh": user.username,
        "systemd_ok": ok, "systemd_detail": detail,
        "systemd_timer": _timer_hidup(),
    }


def laya_aktif_atau_503() -> None:
    """Dipakai endpoint Laya: 503 jujur bila sakelar mati."""
    if not _baca_laya():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "laya_dinonaktifkan",
                "message": (
                    "Laya AI sedang dinonaktifkan (menu Pengaturan → Laya). "
                    "Angka forex dihitung murni dari telemetri MT5 + rumus lokal."
                ),
            },
        )
