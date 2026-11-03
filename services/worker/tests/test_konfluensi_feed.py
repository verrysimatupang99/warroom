"""Konfluensi feed: kabari hanya bila sinyal sendiri sepakat; tanpa auto-trade."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, session_scope
from warroom_worker.jobs import register_handlers
from warroom_worker.jobs.formula import handler_konfluensi_feed
from warroom_worker.schedule import HANDLERS


def _job() -> Job:
    return Job(name="konfluensi-feed", interval_s=3600, enabled=True, payload_json={})


def _fakta(kind: str, key: str, source: str, nilai: dict) -> None:
    with session_scope() as s:
        s.add(Fact(kind=kind, key=key, value_json=nilai, source=source,
                   observed_at=datetime.now(UTC), ttl_s=21600, hash="uji"))


def test_terdaftar(db) -> None:
    register_handlers()
    assert HANDLERS.get("konfluensi-feed") is handler_konfluensi_feed


def test_cocok_mengabarkan_tanpa_eksekusi(db) -> None:
    with session_scope() as s:
        for model in (Alert, Event, Fact, Job):
            s.execute(sa_delete(model))
    _fakta("signal", "crypto/BTCUSDT", "telegram-feed:feed-telegram",
           {"pasar": "crypto", "simbol": "BTCUSDT", "arah": "LONG", "status": "kandidat"})
    _fakta("signal", "BTCUSDT", "lt:verdicts.jsonl#1",
           {"pair": "BTCUSDT", "arah": "LONG"})
    with session_scope() as s:
        hasil = handler_konfluensi_feed(s, _job())
    assert hasil == "kandidat=1 cocok=1 dikabarkan=1"
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "konfluensi/crypto/BTCUSDT"))
        assert a is not None and a.severity == "info"
        assert "BUKAN perintah eksekusi" in a.message


def test_tanpa_pasangan_diam(db) -> None:
    with session_scope() as s:
        for model in (Alert, Event, Fact, Job):
            s.execute(sa_delete(model))
    _fakta("signal", "forex/XAUUSD", "telegram-feed:feed-telegram",
           {"pasar": "forex", "simbol": "XAUUSD", "arah": "SHORT", "status": "kandidat"})
    _fakta("signal", "XAUUSD", "lt:verdicts.jsonl#2",
           {"pair": "XAUUSD", "arah": "LONG"})
    with session_scope() as s:
        hasil = handler_konfluensi_feed(s, _job())
    assert hasil == "kandidat=1 cocok=0 dikabarkan=0"
    with session_scope() as s:
        assert s.scalar(select(Alert.id).where(
            Alert.subject.like("konfluensi/%")).limit(1)) is None
