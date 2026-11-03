"""Pengaturan Laya: baca butuh sesi, tulis khusus owner, default mati."""

from __future__ import annotations

from warroom_api import auth


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def test_laya_tanpa_sesi_401(client) -> None:
    r = client.get("/api/v1/pengaturan/laya")
    assert r.status_code == 401


def test_laya_default_nonaktif(client, make_user) -> None:
    _, sid = make_user("atur-baca", role="viewer")
    body = client.get("/api/v1/pengaturan/laya", headers=_cookie(sid)).json()
    assert body["aktif"] is False
    assert isinstance(body["systemd_timer"], bool)


def test_laya_tulis_hanya_owner(client, make_user) -> None:
    _, sid_op = make_user("atur-op", role="operator")
    r = client.post("/api/v1/pengaturan/laya", json={"aktif": True}, headers=_cookie(sid_op))
    assert r.status_code == 403

    _, sid_own = make_user("atur-own", role="owner")
    r = client.post("/api/v1/pengaturan/laya", json={"aktif": False}, headers=_cookie(sid_own))
    assert r.status_code == 200
    assert r.json()["aktif"] is False

    body = client.get("/api/v1/pengaturan/laya", headers=_cookie(sid_own)).json()
    assert body["aktif"] is False
