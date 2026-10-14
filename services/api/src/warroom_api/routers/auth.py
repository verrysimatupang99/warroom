"""Router auth — login / logout / me (dipisah dari app.py, P1-2).

Diekstrak murni: perilaku, path, status kode, dan cookie TIDAK berubah.
Pembatas laju login (`LOGIN_LIMITER`) dipakai bersama dari modul ini.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from warroom_core.db import User, session_scope

from warroom_api import auth, limits

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str
    totp: str | None = None


@router.post("/api/v1/auth/login")
def login(body: LoginBody, response: Response, request: Request) -> dict[str, Any]:
    # Batas laju per IP klien (asli, dari XFF yang ditambahkan nginx) — temuan audit 5 Okt.
    if not limits.LOGIN_LIMITER.izinkan(limits.kunci_klien(request)):
        raise HTTPException(
            status_code=429,
            detail="terlalu banyak percobaan login; coba lagi nanti",
        )
    sid = auth.login(body.username, body.password, body.totp)
    if sid is None:
        raise HTTPException(status_code=401, detail="kredensial tidak sah")
    response.set_cookie(
        auth.COOKIE_NAME,
        sid,
        httponly=True,
        samesite="lax",
        secure=auth.cookie_secure(),
        max_age=int(auth.SESSION_TTL.total_seconds()),
        path="/",
    )
    return {"ok": True}


@router.post("/api/v1/auth/logout")
def logout(
    user: Annotated[User, Depends(auth.current_user)],
    wr_session: Annotated[str | None, Cookie(alias=auth.COOKIE_NAME)] = None,
) -> dict[str, Any]:
    with session_scope() as s:
        if wr_session:
            auth.revoke_session(s, wr_session)
    return {"ok": True}


@router.get("/api/v1/auth/me")
def me(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    return {"username": user.username, "role": user.role}
