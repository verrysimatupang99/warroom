"""Denyut Telegram: 1 siklus = 1 alert info dengan angka jujur dari DB."""

from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Job, session_scope
from warroom_worker.jobs import register_handlers
from warroom_worker.jobs.infra import handler_denyut
from warroom_worker.schedule import HANDLERS


def _job() -> Job:
    return Job(name="denyut", interval_s=21600, enabled=True, payload_json={})


def test_denyut_terdaftar(db) -> None:
    register_handlers()
    assert HANDLERS.get("denyut") is handler_denyut


def test_denyut_menulis_alert_info_jujur(db) -> None:
    with session_scope() as s:
        for model in (Alert, Event, Job):
            s.execute(sa_delete(model))
        s.add(Job(name="rusak", interval_s=60, enabled=True,
                  payload_json={}, last_status="gagal"))
    with session_scope() as s:
        hasil = handler_denyut(s, _job())
    assert "fakta_baru=" in hasil and "job_gagal=rusak" in hasil
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "denyut/war-room"))
        assert a is not None and a.severity == "info"


def test_denyut_tidak_duplikat_selama_terbuka(db) -> None:
    with session_scope() as s:
        for model in (Alert, Event, Job):
            s.execute(sa_delete(model))
    with session_scope() as s:
        assert handler_denyut(s, _job()).endswith("alert_baru=1")
    with session_scope() as s:
        assert handler_denyut(s, _job()).endswith("alert_baru=0")
    with session_scope() as s:
        n = len(s.scalars(select(Alert).where(Alert.subject == "denyut/war-room")).all())
        assert n == 1
