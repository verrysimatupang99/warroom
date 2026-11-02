"""Tes gudang kredensial generik (/api/v1/vault)."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet

BODY = {
    "platform": "binance",
    "label": "utama",
    "endpoint": "https://api.binance.com",
    "api_key": "KUNCI123",
    "api_secret": "RAHASIA456",
}


@pytest.fixture(autouse=True)
def bersihkan_vault() -> Iterator[None]:
    from warroom_core.db import session_scope
    from warroom_core.db.models import VaultCredential

    with session_scope() as db:
        for row in db.query(VaultCredential).all():
            db.delete(row)
    yield
    with session_scope() as db:
        for row in db.query(VaultCredential).all():
            db.delete(row)


@pytest.fixture
def kunci_vault(monkeypatch: pytest.MonkeyPatch) -> str:
    kunci = Fernet.generate_key().decode()
    monkeypatch.setenv("WARROOM_MT5_VAULT_KEY", kunci)
    return kunci


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"wr_session={sid}"}


def test_platform_preset_tanpa_polymarket(client, make_user) -> None:
    _, sid = make_user("viewer-preset", role="viewer")
    r = client.get("/api/v1/vault/platform", headers=_cookie(sid))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["platform"]}
    assert "binance" in ids and "bybit" in ids and "okx" in ids
    assert "polymarket" not in ids
    assert "polymarket" in r.json()["diblokir"]


def test_tulis_butuh_owner(client, make_user, kunci_vault) -> None:
    _, sid_viewer = make_user("viewer-vaultg", role="viewer")
    _, sid_owner = make_user("owner-vaultg", role="owner")
    assert client.post("/api/v1/vault", json=BODY, headers=_cookie(sid_viewer)).status_code == 403
    assert client.post("/api/v1/vault", json=BODY, headers=_cookie(sid_owner)).status_code == 201


def test_polymarket_diblokir(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-pm", role="owner")
    r = client.post(
        "/api/v1/vault",
        json={"platform": "polymarket", "label": "pm", "api_key": "x"},
        headers=_cookie(sid),
    )
    assert r.status_code == 403


def test_preset_butuh_endpoint(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-ep", role="owner")
    r = client.post(
        "/api/v1/vault", json={"platform": "binance", "label": "x", "api_key": "k"}, headers=_cookie(sid)
    )
    assert r.status_code == 422


def test_metadata_tidak_bocor_rahasia(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-bocor", role="owner")
    buat = client.post("/api/v1/vault", json=BODY, headers=_cookie(sid))
    assert buat.status_code == 201, buat.text
    meta = buat.json()
    assert "KUNCI123" not in str(meta) and "RAHASIA456" not in str(meta)
    assert meta["punya_key"] and meta["punya_secret"]
    daftar = client.get("/api/v1/vault", headers=_cookie(sid)).json()
    assert "KUNCI123" not in str(daftar)


def test_lihat_rahasia_owner_only(client, make_user, kunci_vault) -> None:
    _, sid_owner = make_user("owner-rahasia", role="owner")
    _, sid_viewer = make_user("viewer-rahasia", role="viewer")
    kid = client.post("/api/v1/vault", json=BODY, headers=_cookie(sid_owner)).json()["id"]
    assert client.get(f"/api/v1/vault/{kid}/rahasia", headers=_cookie(sid_viewer)).status_code == 403
    r = client.get(f"/api/v1/vault/{kid}/rahasia", headers=_cookie(sid_owner))
    assert r.status_code == 200
    isi = r.json()
    assert isi["api_key"] == "KUNCI123" and isi["api_secret"] == "RAHASIA456"
    assert isi["endpoint"] == "https://api.binance.com"


def test_extra_terenkripsi(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-extra", role="owner")
    body = dict(BODY, platform="okx", extra={"passphrase": "PHEENIX"})
    kid = client.post("/api/v1/vault", json=body, headers=_cookie(sid)).json()["id"]
    r = client.get(f"/api/v1/vault/{kid}/rahasia", headers=_cookie(sid))
    assert r.json()["extra"] == {"passphrase": "PHEENIX"}
    meta = client.get("/api/v1/vault", headers=_cookie(sid)).json()
    assert "PHEENIX" not in str(meta)


def test_update_dan_hapus(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-edit", role="owner")
    kid = client.post("/api/v1/vault", json=BODY, headers=_cookie(sid)).json()["id"]
    r = client.patch(
        f"/api/v1/vault/{kid}", json={"aktif": False, "api_key": "KUNCI-BARU"}, headers=_cookie(sid)
    )
    assert r.status_code == 200 and r.json()["aktif"] is False
    rahasia = client.get(f"/api/v1/vault/{kid}/rahasia", headers=_cookie(sid)).json()
    assert rahasia["api_key"] == "KUNCI-BARU"
    assert client.delete(f"/api/v1/vault/{kid}", headers=_cookie(sid)).status_code == 204
    assert client.get("/api/v1/vault", headers=_cookie(sid)).json()["items"] == []


def test_duplikat_platform_label_ditolak(client, make_user, kunci_vault) -> None:
    _, sid = make_user("owner-dup", role="owner")
    assert client.post("/api/v1/vault", json=BODY, headers=_cookie(sid)).status_code == 201
    assert client.post("/api/v1/vault", json=BODY, headers=_cookie(sid)).status_code == 409


def test_tanpa_kunci_vault_tulis_503(client, make_user, monkeypatch) -> None:
    monkeypatch.delenv("WARROOM_MT5_VAULT_KEY", raising=False)
    monkeypatch.setattr("warroom_core.mt5_crypto._KEY_PATHS", ("/nonexistent/kunci",))
    _, sid = make_user("owner-nokey", role="owner")
    r = client.post("/api/v1/vault", json=BODY, headers=_cookie(sid))
    assert r.status_code == 503
