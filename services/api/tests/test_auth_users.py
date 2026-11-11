"""Tes buat akun login (owner-only) via POST /api/v1/auth/users."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Pembatas laju login singleton modul — reset antar tes supaya tak 429."""
    from warroom_api import app as app_mod

    for lim in (app_mod.LOGIN_LIMITER, app_mod.VERIFIER_LIMITER, app_mod.NARRATE_LIMITER):
        lim.reset()
    yield
    for lim in (app_mod.LOGIN_LIMITER, app_mod.VERIFIER_LIMITER, app_mod.NARRATE_LIMITER):
        lim.reset()


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"wr_session={sid}"}


def test_buat_user_owner(client, make_user) -> None:
    _, sid = make_user("owner-u1", role="owner")
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "demo", "password": "kiroween2026", "role": "viewer"},
        headers=_cookie(sid),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "created"
    assert r.json()["username"] == "demo"
    assert r.json()["role"] == "viewer"


def test_buat_user_duplikat_409(client, make_user) -> None:
    _, sid = make_user("owner-u2", role="owner")
    body = {"username": "demo2", "password": "kiroween2026", "role": "viewer"}
    assert client.post("/api/v1/auth/users", json=body, headers=_cookie(sid)).status_code == 201
    r = client.post("/api/v1/auth/users", json=body, headers=_cookie(sid))
    assert r.status_code == 409


def test_buat_user_role_invalid_400(client, make_user) -> None:
    _, sid = make_user("owner-u3", role="owner")
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "x", "password": "kiroween2026", "role": "superadmin"},
        headers=_cookie(sid),
    )
    assert r.status_code == 400


def test_buat_user_password_pendek_400(client, make_user) -> None:
    _, sid = make_user("owner-u4", role="owner")
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "y", "password": "abc", "role": "viewer"},
        headers=_cookie(sid),
    )
    assert r.status_code == 400


def test_buat_user_butuh_owner(client, make_user) -> None:
    _, sid = make_user("op-u5", role="operator")
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "z", "password": "kiroween2026", "role": "viewer"},
        headers=_cookie(sid),
    )
    assert r.status_code == 403


def test_buat_user_tanpa_sesi_401(client) -> None:
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "w", "password": "kiroween2026", "role": "viewer"},
    )
    assert r.status_code == 401


def test_user_baru_bisa_login(client, make_user) -> None:
    _, sid = make_user("owner-u6", role="owner")
    client.post(
        "/api/v1/auth/users",
        json={"username": "demologin", "password": "kiroween2026", "role": "viewer"},
        headers=_cookie(sid),
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "demologin", "password": "kiroween2026"},
    )
    assert r.status_code == 200
