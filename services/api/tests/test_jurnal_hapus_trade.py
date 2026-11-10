"""Tes hapus baris trade (owner-only) — bersihkan baris uji/keliru dari tabel `trades`."""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _bersihkan_trade(db: str) -> Iterator[None]:
    """Tabel `trades` tak dibersihkan conftest — kosongkan sendiri tiap tes."""
    from warroom_core.db import Trade, session_scope

    with session_scope() as s:
        s.query(Trade).delete()
    yield


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"wr_session={sid}"}


def _sisip_trade(venue: str = "forex", mode: str = "live", ext_id: str = "900001") -> int:
    from warroom_core.db import Trade, session_scope

    with session_scope() as s:
        t = Trade(
            venue=venue,
            mode=mode,
            ext_id=ext_id,
            side="BUY",
            evidence_json={"symbol": "XAUUSD", "account": "demo"},
        )
        s.add(t)
        s.flush()
        return t.id


def test_hapus_trade_owner(client, make_user) -> None:
    tid = _sisip_trade()
    _, sid = make_user("owner-hapus", role="owner")
    r = client.delete("/api/v1/journal/trades/900001?venue=forex&mode=live", headers=_cookie(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"
    assert body["ext_id"] == "900001"
    assert body["id"] == tid
    # baris benar-benar hilang → panggilan kedua 404
    r2 = client.delete("/api/v1/journal/trades/900001?venue=forex&mode=live", headers=_cookie(sid))
    assert r2.status_code == 404


def test_hapus_trade_tak_ada_404(client, make_user) -> None:
    _, sid = make_user("owner-hapus2", role="owner")
    r = client.delete("/api/v1/journal/trades/999999?venue=forex&mode=live", headers=_cookie(sid))
    assert r.status_code == 404


def test_hapus_trade_butuh_owner(client, make_user) -> None:
    _sisip_trade()
    _, sid = make_user("op-hapus", role="operator")
    r = client.delete("/api/v1/journal/trades/900001?venue=forex&mode=live", headers=_cookie(sid))
    assert r.status_code == 403
    # baris tetap ada
    _, sid_owner = make_user("owner-hapus3", role="owner")
    r2 = client.delete("/api/v1/journal/trades/900001?venue=forex&mode=live", headers=_cookie(sid_owner))
    assert r2.status_code == 200


def test_hapus_trade_tanpa_sesi_401(client) -> None:
    r = client.delete("/api/v1/journal/trades/900001?venue=forex&mode=live")
    assert r.status_code == 401
