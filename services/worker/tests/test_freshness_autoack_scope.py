"""Batas auto-ack alert freshness: hanya pesan 'data basi:' yang boleh ditutup.

Regresi: filter lama hanya cek subjek memuat '/', sehingga alert domain lain
yang kebetulan bersubjek sama (mis. 'strategi/benched…') ikut ter-ack otomatis
lima menit setelah dibuat — alert keselamatan uang hilang tanpa keputusan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from warroom_core.db import Alert, Fact, Job, session_scope
from warroom_worker import schedule


def _fakta(kind: str, key: str, umur_s: int) -> Fact:
    return Fact(
        kind=kind,
        key=key,
        value_json={"x": 1},
        source="uji",
        observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
        ttl_s=600,
        hash="h",
    )


@pytest.fixture(autouse=True)
def _bersihkan(db):
    from sqlalchemy import delete as sa_delete
    from warroom_core.db import Event, Strategy

    with session_scope() as s:
        for model in (Fact, Event, Alert, Job, Strategy):
            s.execute(sa_delete(model))
    yield


def _jalankan_freshness() -> None:
    from warroom_worker.jobs import register_handlers

    register_handlers()
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "freshness"))
        schedule.run_one(s, job)


def test_alert_bukan_data_basi_tidak_terack_otomatis(db) -> None:
    with session_scope() as s:
        # fakta segar (umur 30 s vs ttl 600) → alert 'data basi' lamanya boleh pulih
        s.add(_fakta("snapshot", "mode", umur_s=30))
        s.add(
            Alert(
                severity="warning",
                subject="snapshot/mode",
                message="data basi: snapshot/mode umur 120 mnt",
                created_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        # alert domain lain: subjek mengandung '/' tapi BUKAN berpola 'data basi:'
        s.add(
            Alert(
                severity="warning",
                subject="strategi/benched:smc-tf15",
                message="strategi/benched:smc-tf15 benched: lewat batas harian",
                created_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
    _jalankan_freshness()
    with session_scope() as s:
        pulih = s.scalar(select(Alert).where(Alert.subject == "snapshot/mode"))
        strategi = s.scalar(
            select(Alert).where(Alert.subject == "strategi/benched:smc-tf15")
        )
    assert pulih.ack_at is not None  # data basi → auto-pulih tetap bekerja
    assert strategi.ack_at is None  # bukan 'data basi:' → tidak boleh disentuh
    assert "PULIH otomatis" not in (strategi.message or "")


def test_alert_data_basi_yang_masih_basi_tetap_terbuka(db) -> None:
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", umur_s=2 * 3600))
        s.add(
            Alert(
                severity="warning",
                subject="snapshot/mode",
                message="data basi: snapshot/mode umur 100 mnt",
                created_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
    _jalankan_freshness()
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "snapshot/mode"))
    # masih basi → tidak dipulihkan (fakta baru saja membuat alert duplikat dedup
    # tertahan oleh _alert; yang penting alert lama TIDAK ikut ter-ack)
    assert a.ack_at is None
