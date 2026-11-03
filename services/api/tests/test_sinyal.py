"""Ingest sinyal Telegram: auth, validasi, fakta jujur."""

from __future__ import annotations

from sqlalchemy import select
from warroom_api import auth
from warroom_core.db import Fact, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def test_sinyal_tanpa_sesi_401(client) -> None:
    r = client.post("/api/v1/sinyal/telegram",
                    json={"pasar": "crypto", "simbol": "BTCUSDT", "arah": "LONG"})
    assert r.status_code == 401


def test_sinyal_viewer_ditolak(client, make_user) -> None:
    _, sid = make_user("sin-view", role="viewer")
    r = client.post("/api/v1/sinyal/telegram",
                    json={"pasar": "crypto", "simbol": "BTCUSDT", "arah": "LONG"},
                    headers=_cookie(sid))
    assert r.status_code == 403


def test_sinyal_arah_salah_422(client, make_user) -> None:
    _, sid = make_user("sin-op", role="operator")
    r = client.post("/api/v1/sinyal/telegram",
                    json={"pasar": "crypto", "simbol": "BTCUSDT", "arah": "NAIK"},
                    headers=_cookie(sid))
    assert r.status_code == 422


def test_sinyal_ok_menulis_fakta(client, make_user) -> None:
    _, sid = make_user("sin-ok", role="operator")
    r = client.post("/api/v1/sinyal/telegram",
                    json={"pasar": "crypto", "simbol": "BTCUSDT", "arah": "short",
                          "entry": 97000.5, "catatan": "dari feed uji"},
                    headers=_cookie(sid))
    assert r.status_code == 200
    assert r.json()["key"] == "crypto/BTCUSDT"
    with session_scope() as s:
        f = s.scalar(select(Fact).where(Fact.kind == "signal",
                                        Fact.key == "crypto/BTCUSDT"))
        assert f is not None
        assert f.value_json["arah"] == "SHORT"
        assert f.value_json["status"] == "kandidat"
        assert "gate" in f.value_json["kejujuran"].lower() or "belum lolos" in f.value_json["kejujuran"]
        assert f.source == "telegram-feed:sin-ok"
