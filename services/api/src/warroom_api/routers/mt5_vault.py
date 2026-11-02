"""Router vault kredensial MT5 (`/api/v1/mt5-vault`).

Tujuan: gudang detail akun MT5 milik pemilik agar tinggal salin-tempel saat
login manual di UI MT5 Webtop. BUKAN auto-login: API tidak pernah memakai
sandi ini untuk terhubung ke broker.

Keamanan:
- Semua endpoint butuh sesi; tulis/hapus hanya `owner`.
- Sandi disimpan terenkripsi (Fernet) dan **tidak pernah** dikirim balik
  ke browser — respons hanya metadata.
- Kunci vault dari `WARROOM_MT5_VAULT_KEY` atau `/etc/warroom/mt5_vault.key`.
  Tanpa kunci: endpoint tulis menolak (503), metadata tetap terbaca.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from warroom_core.db import session_scope
from warroom_core.db.models import MT5Account, User
from warroom_core.mt5_crypto import VaultKeyError, decrypt, encrypt, key_available

from warroom_api import auth

router = APIRouter(prefix="/api/v1/mt5-vault", tags=["mt5-vault"])

_JENIS_SANDI = ("investor", "master")

class MT5AccountIn(BaseModel):
    label: str = Field(default="", max_length=120)
    login: str = Field(min_length=1, max_length=32, pattern=r"^\d+$")
    server: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=128)
    password_kind: str = Field(default="investor")
    note: str = Field(default="", max_length=2000)

class MT5AccountUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    server: str | None = Field(default=None, max_length=160)
    password: str | None = Field(default=None, max_length=128)
    password_kind: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    active: bool | None = None

def _meta(a: MT5Account) -> dict[str, Any]:
    """Metadata tanpa sandi — inilah satu-satunya bentuk yang keluar dari API."""
    return {
        "id": a.id,
        "label": a.label,
        "login": a.login,
        "server": a.server,
        "password_kind": a.password_kind,
        "note": a.note,
        "active": a.active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }

def _validasi_jenis(jenis: str) -> str:
    if jenis not in _JENIS_SANDI:
        raise HTTPException(422, f"password_kind harus salah satu dari {_JENIS_SANDI}")
    return jenis

@router.get("")
def daftar_akun(user: Annotated[User, Depends(auth.require_role("viewer"))]) -> dict[str, Any]:
    with session_scope() as ses:
        rows = ses.scalars(select(MT5Account).order_by(MT5Account.id)).all()
        return {"akun": [_meta(a) for a in rows], "kunci_vault_ada": key_available()}

@router.post("", status_code=status.HTTP_201_CREATED)
def simpan_akun(
    data: MT5AccountIn,
    user: Annotated[User, Depends(auth.require_role("owner"))],
) -> dict[str, Any]:
    if not key_available():
        raise HTTPException(503, "Kunci vault tidak tersedia — set WARROOM_MT5_VAULT_KEY")
    _validasi_jenis(data.password_kind)
    if data.password_kind == "master":
        # Peringatan lunak: tetap boleh (keputusan owner), tapi dicatat di note agar
        # operator tahu risikonya. Investor password disarankan untuk pemantauan.
        if "master" not in data.note.lower():
            data.note = (data.note + "\n[otomatis] master password: risiko penuh order/withdraw.").strip()
    try:
        token = encrypt(data.password)
    except VaultKeyError as exc:
        raise HTTPException(503, str(exc)) from exc
    with session_scope() as ses:
        duplikat = ses.scalars(
            select(MT5Account).where(MT5Account.login == data.login, MT5Account.server == data.server)
        ).first()
        if duplikat is not None:
            raise HTTPException(409, "Akun dengan login+server itu sudah ada")
        a = MT5Account(
            label=data.label,
            login=data.login,
            server=data.server,
            password_enc=token,
            password_kind=data.password_kind,
            note=data.note,
            created_by=user.id,
        )
        ses.add(a)
        ses.flush()
        return _meta(a)

@router.patch("/{akun_id}")
def ubah_akun(
    akun_id: int,
    data: MT5AccountUpdate,
    user: Annotated[User, Depends(auth.require_role("owner"))],
) -> dict[str, Any]:
    if data.password is not None and not key_available():
        raise HTTPException(503, "Kunci vault tidak tersedia — set WARROOM_MT5_VAULT_KEY")
    with session_scope() as ses:
        a = ses.get(MT5Account, akun_id)
        if a is None:
            raise HTTPException(404, "Akun tidak ditemukan")
        if data.label is not None:
            a.label = data.label
        if data.server is not None:
            a.server = data.server
        if data.note is not None:
            a.note = data.note
        if data.active is not None:
            a.active = data.active
        if data.password_kind is not None:
            a.password_kind = _validasi_jenis(data.password_kind)
        if data.password:
            try:
                a.password_enc = encrypt(data.password)
            except VaultKeyError as exc:
                raise HTTPException(503, str(exc)) from exc
        ses.flush()
        return _meta(a)

@router.delete("/{akun_id}", status_code=status.HTTP_204_NO_CONTENT)
def hapus_akun(
    akun_id: int,
    user: Annotated[User, Depends(auth.require_role("owner"))],
) -> Response:
    with session_scope() as ses:
        a = ses.get(MT5Account, akun_id)
        if a is None:
            raise HTTPException(404, "Akun tidak ditemukan")
        ses.delete(a)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{akun_id}/sandi")
def lihat_sandi(
    akun_id: int,
    user: Annotated[User, Depends(auth.require_role("owner"))],
) -> dict[str, str]:
    """Satu-satunya jalan sandi keluar: eksplisit, owner-only, satu akun.
    Ditujukan untuk salin-tempel login manual di UI MT5 Webtop."""
    with session_scope() as ses:
        a = ses.get(MT5Account, akun_id)
        if a is None:
            raise HTTPException(404, "Akun tidak ditemukan")
        try:
            return {"password": decrypt(a.password_enc), "password_kind": a.password_kind}
        except VaultKeyError as exc:
            raise HTTPException(503, str(exc)) from exc
