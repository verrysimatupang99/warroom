"""Tes endpoint alert (W5): daftar + ack/snooze; transport kosong dilaporkan apa adanya.

Aturan yang diuji: alert tidak pernah dihapus, hanya di-ack/ditunda; viewer tidak boleh
mengubah; dan status transport **tidak** diklaim terkonfigurasi bila memang kosong.
"""

from __future__ import annotations

from warroom_api import auth
from warroom_core.db import Alert, Event, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}

def _bersihkan() -> None:
    with session_scope() as s:
        s.query(Alert).delete()
        s.query(Event).delete()

def test_daftar_dan_ack_alert(client, make_user, monkeypatch) -> None:
    """Viewer hanya membaca; operator meng-ack; alert tetap ada setelah di-ack."""
    import warroom_notifier.transport as tr

    monkeypatch.setattr(tr, "_from_file", lambda key: None)
    for var in ("WARROOM_TELEGRAM_BOT_TOKEN", "WARROOM_TELEGRAM_CHAT_ID", "WARROOM_ALERT_WEBHOOK"):
        monkeypatch.delenv(var, raising=False)
    _bersihkan()

    _, sid_view = make_user("al-view", role="viewer")
    _, sid_op = make_user("al-op", role="operator")
    with session_scope() as s:
        s.add(
            Alert(
                severity="warning",
                subject="uji/alert",
                message="sesuatu terjadi",
                suggested_action="periksa",
            )
        )

    lst = client.get("/api/v1/alerts", headers=_cookie(sid_view)).json()
    assert lst["terbuka"] == 1
    assert lst["transport"]["terkonfigurasi"] is False
    assert lst["transport"]["nama"] == "null"
    aid = lst["alerts"][0]["id"]

    r = client.post(f"/api/v1/alerts/{aid}/ack", json={}, headers=_cookie(sid_view))
    assert r.status_code == 403, "viewer tidak boleh meng-ack"

    r = client.post(f"/api/v1/alerts/{aid}/ack", json={}, headers=_cookie(sid_op))
    assert r.status_code == 200
    lst2 = client.get("/api/v1/alerts", headers=_cookie(sid_view)).json()
    assert lst2["terbuka"] == 0
    assert lst2["alerts"][0]["ack_at"] is not None, "alert di-ack, bukan dihapus"

def test_snooze_alert_menunda_tanpa_menghapus(client, make_user, monkeypatch) -> None:
    import warroom_notifier.transport as tr

    monkeypatch.setattr(tr, "_from_file", lambda key: None)
    _bersihkan()
    _, sid_op = make_user("al-op2", role="operator")
    with session_scope() as s:
        a = Alert(severity="info", subject="uji/snooze", message="m", suggested_action="a")
        s.add(a)
        s.flush()
        aid = a.id

    r = client.post(f"/api/v1/alerts/{aid}/ack", json={"snooze_s": 3600}, headers=_cookie(sid_op))
    assert r.status_code == 200 and r.json()["snooze_s"] == 3600
    lst = client.get("/api/v1/alerts", headers=_cookie(sid_op)).json()
    a = next(x for x in lst["alerts"] if x["id"] == aid)
    assert a["snooze_until"] is not None and a["ack_at"] is None
    assert lst["terbuka"] == 1, "snooze bukan ack: tetap terhitung terbuka"
