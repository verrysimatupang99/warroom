"""Tes pengiriman alert (P1-T8) — termasuk POST sungguhan ke server HTTP lokal."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from sqlalchemy import select
from warroom_core.db import Alert, Event, session_scope
from warroom_notifier.dispatch import MAX_PERCOBAAN, kirim_tertunda, tandai_terkirim
from warroom_notifier.transport import (
    HttpTransport,
    NullTransport,
    TelegramTransport,
    transport_from_env,
)


class _Penerima(BaseHTTPRequestHandler):
    """Server uji: mencatat body yang diterima; bisa dipaksa menjawab 500."""

    bodies: list[dict] = []
    seen_headers: list[dict] = []
    status = 200

    def do_POST(self) -> None:  # noqa: N802 — nama wajib dari BaseHTTPRequestHandler
        panjang = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(panjang).decode("utf-8")
        type(self).bodies.append(json.loads(body))
        type(self).seen_headers.append(dict(self.headers))
        self.send_response(type(self).status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: object) -> None:  # senyapkan log server uji
        return


@pytest.fixture
def server_uji():
    srv = HTTPServer(("127.0.0.1", 0), _Penerima)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Penerima.bodies, _Penerima.seen_headers, _Penerima.status = [], [], 200
    yield f"http://127.0.0.1:{srv.server_port}/hook"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        s.query(Alert).delete()
        s.query(Event).filter(Event.type.in_(["alert.sent"])).delete()
    yield


def _alert(subject: str = "snapshot/mode") -> Alert:
    return Alert(
        severity="warning",
        subject=subject,
        message="data basi",
        suggested_action="periksa sumber",
        fact_ids=[7],
    )


# --- transport -------------------------------------------------------------------------


def test_tanpa_konfigurasi_transport_null_dan_tidak_mengklaim_terkirim(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("WARROOM_ALERT_WEBHOOK", raising=False)
    monkeypatch.setenv("WARROOM_NOTIFIER_ENV_FILE", str(tmp_path / "tidak-ada.env"))
    assert isinstance(transport_from_env(), NullTransport)
    res = NullTransport().send("s", "m", "warning", {})
    assert res.ok is False
    assert "tidak ada transport" in res.detail


def test_transport_dibaca_dari_berkas_env(monkeypatch, tmp_path) -> None:
    """Kredensial webhook dibaca dari berkas (pola /etc/warroom/notifier.env), bukan repo."""
    berkas = tmp_path / "notifier.env"
    berkas.write_text(
        "WARROOM_ALERT_WEBHOOK=http://127.0.0.1:9/hook\nWARROOM_ALERT_TOKEN=tok\n", encoding="utf-8"
    )
    monkeypatch.delenv("WARROOM_ALERT_WEBHOOK", raising=False)
    monkeypatch.setenv("WARROOM_NOTIFIER_ENV_FILE", str(berkas))
    tr = transport_from_env()
    assert isinstance(tr, HttpTransport)
    assert tr.url.endswith("/hook") and tr.token == "tok"


def test_http_transport_benar_benar_mengirim(server_uji: str) -> None:
    tr = HttpTransport(server_uji, token="rahasia-jangan-ditulis-dalam-payload")
    res = tr.send("snapshot/mode", "data basi", "warning", {"suggested_action": "cek"})
    assert res.ok is True
    assert res.detail == "http 200"
    assert len(_Penerima.bodies) == 1
    body = _Penerima.bodies[0]
    assert body["subject"] == "snapshot/mode" and body["severity"] == "warning"
    assert body["detail"]["suggested_action"] == "cek"
    # token hanya di header, TIDAK di body
    assert "rahasia" not in json.dumps(body)
    assert "Bearer rahasia" in _Penerima.seen_headers[0].get("Authorization", "")


def test_http_transport_menandai_kegagalan_500(server_uji: str) -> None:
    _Penerima.status = 500
    res = HttpTransport(server_uji).send("s", "m", "warning", {})
    assert res.ok is False and "500" in res.detail


def test_http_transport_menandai_serangan_jaringan() -> None:
    res = HttpTransport("http://127.0.0.1:1/hook", timeout_s=1.0).send("s", "m", "warning", {})
    assert res.ok is False and "URLError" in res.detail or "Connection" in res.detail


# --- dispatch --------------------------------------------------------------------------


def test_kirim_tertunda_mencatat_event_dan_tidak_mengubah_status_tanpa_sukses(db, server_uji: str) -> None:
    with session_scope() as s:
        s.add(_alert())
    with session_scope() as s:
        hasil = kirim_tertunda(s, HttpTransport(server_uji))
    assert hasil[0]["ok"] is True

    with session_scope() as s:
        ev = s.scalar(select(Event).where(Event.type == "alert.sent"))
        assert ev is not None
        assert ev.payload_json["ok"] is True
        assert ev.payload_json["transport"] == "http"
        # belum di-ack: hanya sukses transport yang tercatat, ack tetap keputusan terpisah
        assert s.query(Alert).one().ack_at is None


def test_gagal_kirim_dicatat_sebagai_gagal(db) -> None:
    with session_scope() as s:
        s.add(_alert())
    with session_scope() as s:
        hasil = kirim_tertunda(s, NullTransport())
    assert hasil[0]["ok"] is False
    with session_scope() as s:
        ev = s.scalar(select(Event).where(Event.type == "alert.sent"))
    assert ev.payload_json["ok"] is False


def test_batas_percobaan_mencegah_pengulangan_tak_terbatas(db) -> None:
    with session_scope() as s:
        s.add(_alert())
    for _ in range(MAX_PERCOBAAN + 2):
        with session_scope() as s:
            kirim_tertunda(s, NullTransport())
    with session_scope() as s:
        jumlah = len(s.scalars(select(Event).where(Event.type == "alert.sent")).all())
    assert jumlah == MAX_PERCOBAAN


def test_tandai_terkirim_mengisi_ack(db) -> None:
    with session_scope() as s:
        a = _alert()
        s.add(a)
        s.flush()
        aid = a.id
    with session_scope() as s:
        assert tandai_terkirim(s, aid) is True
    with session_scope() as s:
        assert s.get(Alert, aid).ack_at is not None
    with session_scope() as s:
        assert tandai_terkirim(s, 999_999) is False


def test_alert_terkirim_tidak_diulang_tiap_siklus(db, server_uji: str) -> None:
    with session_scope() as s:
        a = _alert()
        s.add(a)
        s.flush()
        aid = a.id
    with session_scope() as s:
        kirim_tertunda(s, HttpTransport(server_uji))
        tandai_terkirim(s, aid)
    with session_scope() as s:
        hasil = kirim_tertunda(s, HttpTransport(server_uji))
    assert hasil == [], "alert yang sudah di-ack tidak boleh dikirim lagi"


def test_telegram_transport_mengirim_ke_bot_api(server_uji: str, monkeypatch) -> None:
    """Transport Telegram: badan pesan benar, token hanya di URL (bukan di badan)."""
    monkeypatch.setenv("WARROOM_TELEGRAM_API_BASE", server_uji.rsplit("/hook", 1)[0])
    tr = TelegramTransport("123:RAHASIA", "-1001234567890", thread_id="12")
    res = tr.send("snapshot/mode", "data basi 30 mnt", "warning", {"suggested_action": "periksa sumber"})
    assert res.ok is True
    assert len(_Penerima.bodies) == 1
    body = _Penerima.bodies[0]
    assert body["chat_id"] == "-1001234567890"
    assert body["message_thread_id"] == "12"
    assert "data basi 30 mnt" in body["text"]
    assert "periksa sumber" in body["text"]
    assert "RAHASIA" not in json.dumps(body), "token tidak boleh ada di badan pesan"


def test_transport_memilih_telegram_bila_dikonfigurasi(monkeypatch, tmp_path) -> None:
    berkas = tmp_path / "notifier.env"
    berkas.write_text(
        "WARROOM_TELEGRAM_BOT_TOKEN=tok123\nWARROOM_TELEGRAM_CHAT_ID=-100999\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("WARROOM_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("WARROOM_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("WARROOM_NOTIFIER_ENV_FILE", str(berkas))
    tr = transport_from_env()
    assert tr.name == "telegram"
    assert isinstance(tr, TelegramTransport)


def test_dispatch_lewat_telegram_tercatat_di_event(db, server_uji: str, monkeypatch) -> None:
    monkeypatch.setenv("WARROOM_TELEGRAM_API_BASE", server_uji.rsplit("/hook", 1)[0])
    with session_scope() as s:
        s.add(_alert("snapshot/gmgn"))
    with session_scope() as s:
        hasil = kirim_tertunda(s, TelegramTransport("1:x", "-1001"))
    assert hasil[0]["ok"] is True
    with session_scope() as s:
        ev = s.scalar(select(Event).where(Event.type == "alert.sent"))
    assert ev.payload_json["transport"] == "telegram"
    assert ev.payload_json["ok"] is True


def test_timestamp_ack_dipakai_untuk_dedupe(db) -> None:
    with session_scope() as s:
        a = _alert()
        s.add(a)
        s.flush()
        tandai_terkirim(s, a.id, kapan=datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    with session_scope() as s:
        assert s.query(Alert).one().ack_at == datetime(2026, 10, 2, 12, 0, tzinfo=UTC)