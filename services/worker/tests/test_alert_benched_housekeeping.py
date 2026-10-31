"""Tes housekeeping alert benched: hari berganti = alert kemarin tidak berlaku lagi."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, Strategy, session_scope
from warroom_worker.jobs.infra import _tutup_benched_lampau


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        for model in (Alert, Event, Fact, Job, Strategy):
            s.execute(sa_delete(model))
    yield


def _alert(subject: str, pesan: str) -> Alert:
    return Alert(severity="warning", subject=subject, message=pesan, suggested_action="uji")


def test_menutup_benched_hari_lalu_dan_format_lama(db) -> None:
    now = datetime.now(UTC)
    hari_ini = (now + timedelta(hours=7)).date().isoformat()
    kemarin = (now + timedelta(hours=7) - timedelta(days=1)).date().isoformat()
    with session_scope() as s:
        s.add_all(
            [
                _alert(f"strategi/benched:legacy-smc:{hari_ini}", "hari ini"),
                _alert(f"strategi/benched:legacy-smc:{kemarin}", "kemarin"),
                _alert("strategi/benched:legacy-smc", "format lama tanpa tanggal"),
                _alert("strategi/kill-switch:legacy-smc", "kill bukan benched"),
            ]
        )

    with session_scope() as s:
        assert _tutup_benched_lampau(s, now=now) == 2

    with session_scope() as s:
        buka = {a.subject for a in s.scalars(select(Alert).where(Alert.ack_at.is_(None)))}
        tutup = [a for a in s.scalars(select(Alert).where(Alert.ack_at.is_not(None)))]
    assert f"strategi/benched:legacy-smc:{hari_ini}" in buka
    assert "strategi/kill-switch:legacy-smc" in buka, "kill-switch tidak boleh ditutup otomatis"
    assert len(buka) == 2
    assert len(tutup) == 2
    assert all("PULIH otomatis: hari berganti" in (a.message or "") for a in tutup)


def test_idempoten(db) -> None:
    now = datetime.now(UTC)
    kemarin = (now + timedelta(hours=7) - timedelta(days=1)).date().isoformat()
    with session_scope() as s:
        s.add(_alert(f"strategi/benched:x:{kemarin}", "kemarin"))
    with session_scope() as s:
        assert _tutup_benched_lampau(s, now=now) == 1
    with session_scope() as s:
        assert _tutup_benched_lampau(s, now=now) == 0
