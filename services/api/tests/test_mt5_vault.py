"""Tes vault kredensial MT5 — enkripsi-at-rest & kontrol akses."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def bersihkan_vault() -> Iterator[None]:
    """Tabel vault bukan tabel platform — conftest tidak membersihkannya,
    jadi kosongkan sendiri sebelum tiap tes (unik login+server jangan bocor)."""
    from warroom_core.db import MT5Account, session_scope

    with session_scope() as ses:
        ses.query(MT5Account).delete()
    yield


@pytest.fixture
def kunci_vault(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("WARROOM_MT5_VAULT_KEY", key)
    return key


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"wr_session={sid}"}


BODY = {
    "label": "Exness cent",
    "login": "36525553",
    "server": "Exness-MT5Trial8",
    "password": "sandi-rahasia",
    "password_kind": "investor",
}


def test_tulis_butuh_owner(client, make_user, kunci_vault) -> None:
    _, sid_viewer = make_user("viewer-vault", role="viewer")
    r = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid_viewer))
    assert r.status_code == 403


def test_simpan_dan_daftar_tanpa_sandi(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-vault", role="owner")
    r = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid))
    assert r.status_code == 201, r.text
    meta = r.json()
    assert meta["login"] == "36525553"
    # Sandi TIDAK boleh ada di metadata
    assert "password" not in meta and "password_enc" not in meta

    r2 = client.get("/api/v1/mt5-vault", headers=_cookie(sid))
    assert r2.status_code == 200
    assert r2.json()["kunci_vault_ada"] is True
    assert all("password" not in a for a in r2.json()["akun"])


def test_duplikat_login_server_ditolak(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-vault2", role="owner")
    assert client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid)).status_code == 201
    r = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid))
    assert r.status_code == 409


def test_lihat_sandi_owner_only_dan_isi_benar(client, make_user, kunci_vault) -> None:
    _, sid_owner = make_user("owner-vault3", role="owner")
    _, sid_viewer = make_user("viewer-vault3", role="viewer")
    buat = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid_owner))
    assert buat.status_code == 201, buat.text
    akun_id = buat.json()["id"]

    assert client.get(f"/api/v1/mt5-vault/{akun_id}/sandi", headers=_cookie(sid_viewer)).status_code == 403
    r = client.get(f"/api/v1/mt5-vault/{akun_id}/sandi", headers=_cookie(sid_owner))
    assert r.status_code == 200
    assert r.json()["password"] == "sandi-rahasia"


def test_tanpa_kunci_vault_tulis_503(client, make_user, monkeypatch) -> None:
    monkeypatch.delenv("WARROOM_MT5_VAULT_KEY", raising=False)
    _, sid = make_user("owner-vault4", role="owner")
    r = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid))
    assert r.status_code == 503


def test_hapus_akun(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-vault5", role="owner")
    buat = client.post("/api/v1/mt5-vault", json=BODY, headers=_cookie(sid))
    assert buat.status_code == 201, buat.text
    akun_id = buat.json()["id"]
    assert client.delete(f"/api/v1/mt5-vault/{akun_id}", headers=_cookie(sid)).status_code == 204
    assert client.get("/api/v1/mt5-vault", headers=_cookie(sid)).json()["akun"] == []
