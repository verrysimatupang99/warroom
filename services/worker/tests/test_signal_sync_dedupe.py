"""Tes dedupe `handler_signal_sync` — ledger yang sama tidak ditulis/kabarkan ulang.

Latar produksi: 197 alert untuk 12 sinyal unik dalam ~2 hari, karena setiap siklus
(15 mnt) menulis ulang fakta + alert untuk sinyal yang sama, dan `observed_at=now`
membuat kandidat tua terlihat segar.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers
from warroom_worker.jobs.domain import handler_signal_sync


@pytest.fixture(autouse=True)
def _bersihkan(db):
    from warroom_core.db import Strategy

    with session_scope() as s:
        for model in (Fact, Event, Alert, Job, Strategy):
            s.execute(sa_delete(model))
    register_handlers()
    yield


def _ledger(tmp_path: Path, menit_lalu: int = 20) -> Path:
    d = tmp_path / "state"
    d.mkdir(parents=True, exist_ok=True)
    baris = {
        "ts": (datetime.now(UTC) - timedelta(minutes=menit_lalu)).isoformat(timespec="seconds"),
        "pair": "BTCUSDT",
        "direction": "SHORT",
        "allowed": True,
        "tier": "PREMIUM",
        "entry": 100.0,
        "sl": 101.5,
        "tp1": 98.5,
        "risk_pct": 1.5,
        "rules": [],
    }
    (d / "verdicts.jsonl").write_text(json.dumps(baris) + "\n", encoding="utf-8")
    return d


def _job_signal(tmp_path: Path, monkeypatch) -> Job:
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(tmp_path))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "signal-sync"))
        job.payload_json = {**job.payload_json, "kabari": True}
        s.flush()
        return job


def test_sinyal_sama_hanya_ditulis_satu_kali(db, tmp_path, monkeypatch) -> None:
    _ledger(tmp_path)
    job = _job_signal(tmp_path, monkeypatch)
    with session_scope() as s:
        j = s.get(Job, job.id)
        status1, detail1 = schedule.run_one(s, j)
    assert status1 == "ok" and "baru=1" in detail1 and "sudah_ada=0" in detail1

    # siklus berikutnya: ledger identik → tidak ada fakta baru, tidak ada alert baru
    with session_scope() as s:
        j = s.get(Job, job.id)
        status2, detail2 = schedule.run_one(s, j)
    assert status2 == "ok" and "baru=0" in detail2 and "sudah_ada=1" in detail2

    with session_scope() as s:
        assert len(s.scalars(select(Fact).where(Fact.kind == "signal")).all()) == 1
        assert len(s.scalars(select(Alert)).all()) == 1, "alert tidak boleh berulang"


def test_sinyal_baru_tetap_mengabarkan(db, tmp_path, monkeypatch) -> None:
    """Dedupe tidak boleh menelan sinyal BARU: ts berbeda = entri berbeda."""
    d = _ledger(tmp_path)
    job = _job_signal(tmp_path, monkeypatch)
    with session_scope() as s:
        schedule.run_one(s, s.get(Job, job.id))

    isi = json.loads((d / "verdicts.jsonl").read_text(encoding="utf-8"))
    isi["ts"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat(timespec="seconds")
    (d / "verdicts.jsonl").write_text(json.dumps(isi) + "\n", encoding="utf-8")

    with session_scope() as s:
        j = s.get(Job, job.id)
        _, detail = schedule.run_one(s, j)
    assert "baru=1" in detail
    with session_scope() as s:
        assert len(s.scalars(select(Fact).where(Fact.kind == "signal")).all()) == 2


def test_handler_bisa_dipanggil_langsung(db, tmp_path, monkeypatch) -> None:
    """Panggilan langsung (tanpa run_one) memakai payload job apa adanya."""
    _ledger(tmp_path)
    job = _job_signal(tmp_path, monkeypatch)
    with session_scope() as s:
        j = s.get(Job, job.id)
        keluar = handler_signal_sync(s, j)
    assert "sinyal=1" in keluar and "baru=1" in keluar
