"""Tes job-health: job gagal/stale memicu alert, pemulihan menutup alert."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, Strategy, session_scope
from warroom_worker.jobs.infra import handler_job_health


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        for model in (Alert, Event, Fact, Job, Strategy):
            s.execute(sa_delete(model))
    yield


def _job(nama: str, *, status: str, umur_s: int, enabled: bool = True) -> Job:
    return Job(
        name=nama,
        interval_s=300,
        enabled=enabled,
        payload_json={},
        note="uji",
        last_status=status,
        last_detail="boom" if status == "gagal" else "",
        last_run_at=datetime.now(UTC) - timedelta(seconds=umur_s),
    )


def _jalankan() -> str:
    with session_scope() as s:
        self_job = Job(name="job-health", interval_s=300, payload_json={}, note="uji")
        return handler_job_health(s, self_job)


def test_gagal_dan_stale_memicu_alert_job_mati_diabaikan(db) -> None:
    with session_scope() as s:
        s.add_all(
            [
                _job("gagal-uji", status="gagal", umur_s=60),
                _job("stale-uji", status="ok", umur_s=2000),
                _job("sehat-uji", status="ok", umur_s=60),
                _job("mati-uji", status="gagal", umur_s=5000, enabled=False),
            ]
        )
    detail = _jalankan()
    assert "alert=2" in detail
    with session_scope() as s:
        subjek = {a.subject for a in s.scalars(select(Alert)).all()}
        ev = s.scalar(select(Event).where(Event.type == "job.health"))
    assert subjek == {"job/gagal-uji", "job/stale-uji"}
    assert ev is not None and ev.payload_json["alert_baru"] == 2


def test_pemulihan_menutup_alert(db) -> None:
    with session_scope() as s:
        s.add(_job("gagal-uji", status="gagal", umur_s=60))
    _jalankan()
    assert "alert=0" in _jalankan(), "alert yang sama tidak boleh dibuat ulang"
    with session_scope() as s:
        j = s.scalar(select(Job).where(Job.name == "gagal-uji"))
        j.last_status = "ok"
        j.last_run_at = datetime.now(UTC)
    assert "pulih=1" in _jalankan()
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "job/gagal-uji"))
        assert a.ack_at is not None
        assert "PULIH otomatis" in a.message
