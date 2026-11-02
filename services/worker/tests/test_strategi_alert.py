"""Regresi: alert kill-switch (HALTED) dari transisi fakta — sekali per transisi.

Yang dikunci:
1. Transisi belum-HALTED → HALTED dikabarkan sebagai alert critical sekali.
2. Fakta yang tidak berubah (HALTED tetap HALTED) tidak berkabar ulang.
3. Transisi yang sudah diproses tetap tidak berkabar ulang walau alertnya
   sudah di-ack owner — syarat supaya ini bukan pengingat tiap 5 menit.
4. Transisi yang terjadi saat watcher mati tetap tertangkap dari riwayat fakta.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, Strategy, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        for model in (Alert, Event, Fact, Job, Strategy):
            s.execute(sa_delete(model))
    register_handlers()
    yield


def _fakta(s, halted: bool, *, menit_lalu: int) -> Fact:
    f = Fact(
        kind="harian",
        key="status",
        value_json={
            "halted": halted,
            "alasan_halted": "drawdown 21.0% >= 20%" if halted else None,
        },
        source="ops/harian_cycle.py",
        observed_at=datetime.now(UTC) - timedelta(minutes=menit_lalu),
        ttl_s=86400,
        hash=f"h{menit_lalu}",
    )
    s.add(f)
    s.flush()
    return f


def _job_alert(*, last_run_menit_lalu: int | None) -> int:
    """Buat baris job `strategi-alert`; kembalikan id (bukan objek lintas sesi)."""
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "strategi-alert"))
        job.last_run_at = (
            datetime.now(UTC) - timedelta(minutes=last_run_menit_lalu)
            if last_run_menit_lalu is not None
            else None
        )
        if last_run_menit_lalu is not None:
            job.last_status = "ok"
        s.flush()
        return job.id


def test_transisi_halted_dikabarkan_sekali(db) -> None:
    with session_scope() as s:
        _fakta(s, False, menit_lalu=70)
        _fakta(s, True, menit_lalu=10)
    job_id = _job_alert(last_run_menit_lalu=60)

    with session_scope() as s:
        status, detail = schedule.run_one(s, s.get(Job, job_id))
    assert status == "ok" and "dikabarkan" in detail

    with session_scope() as s:
        rows = s.scalars(select(Alert)).all()
        assert len(rows) == 1
        assert rows[0].subject == "strategi/kill-switch:Strategi A"
        assert rows[0].severity == "critical"
        assert "drawdown 21.0%" in rows[0].message
        assert rows[0].fact_ids  # tertaut ke fakta pemicu, bukan alert tanpa jejak

    # Siklus berikutnya: fakta berhenti berubah → tidak ada alert kedua.
    with session_scope() as s:
        _, detail2 = schedule.run_one(s, s.get(Job, job_id))
    assert "tidak ada transisi" in detail2
    with session_scope() as s:
        assert len(s.scalars(select(Alert)).all()) == 1


def test_setelah_ack_tidak_berkabar_ulang(db) -> None:
    """Anti-spam inti: ack owner bukan pemicu alert berikutnya."""
    with session_scope() as s:
        _fakta(s, False, menit_lalu=70)
        _fakta(s, True, menit_lalu=10)
    job_id = _job_alert(last_run_menit_lalu=60)
    with session_scope() as s:
        schedule.run_one(s, s.get(Job, job_id))

    with session_scope() as s:
        s.scalars(select(Alert)).one().ack_at = datetime.now(UTC)

    with session_scope() as s:
        _, detail = schedule.run_one(s, s.get(Job, job_id))
    assert "tidak ada transisi" in detail
    with session_scope() as s:
        assert len(s.scalars(select(Alert)).all()) == 1


def test_halted_beruntun_tidak_mengabarkan(db) -> None:
    with session_scope() as s:
        _fakta(s, False, menit_lalu=4000)
        _fakta(s, True, menit_lalu=3000)
        _fakta(s, True, menit_lalu=100)
    job_id = _job_alert(last_run_menit_lalu=50)

    with session_scope() as s:
        _, detail = schedule.run_one(s, s.get(Job, job_id))
    assert "tidak ada transisi" in detail
    with session_scope() as s:
        assert s.scalars(select(Alert)).all() == []


def test_transisi_saat_watcher_mati_tertangkap_dari_riwayat(db) -> None:
    with session_scope() as s:
        _fakta(s, False, menit_lalu=4000)
        _fakta(s, True, menit_lalu=3000)
        _fakta(s, True, menit_lalu=100)
    # Siklus terakhir SEBELUM transisi (3000 mnt lalu) → watcher sempat mati.
    job_id = _job_alert(last_run_menit_lalu=3500)

    with session_scope() as s:
        _, detail = schedule.run_one(s, s.get(Job, job_id))
    assert "dikabarkan" in detail
    with session_scope() as s:
        assert len(s.scalars(select(Alert)).all()) == 1


def test_riwayat_kurang_dua_fakta_dilewati(db) -> None:
    with session_scope() as s:
        _fakta(s, True, menit_lalu=10)
    job_id = _job_alert(last_run_menit_lalu=None)

    with session_scope() as s:
        status, detail = schedule.run_one(s, s.get(Job, job_id))
    assert status == "ok" and "riwayat fakta < 2" in detail
    with session_scope() as s:
        assert s.scalars(select(Alert)).all() == []


def test_handler_gagal_siklus_berikutnya_tetap_mengabarkan(db) -> None:
    """Kegagalan handler pada satu siklus (last_run_at maju) tidak menelan transisi."""
    with session_scope() as s:
        _fakta(s, False, menit_lalu=70)
        _fakta(s, True, menit_lalu=10)
    job_id = _job_alert(last_run_menit_lalu=60)

    handler_asli = schedule.HANDLERS["strategi-alert"]
    try:
        def handler_error(_s_err, _j_err):
            raise RuntimeError("koneksi facts sesaat terputus")

        schedule.HANDLERS["strategi-alert"] = handler_error
        with session_scope() as s:
            status1, _ = schedule.run_one(s, s.get(Job, job_id))
        assert status1 == "gagal"
        with session_scope() as s:
            assert s.scalars(select(Alert)).all() == []
    finally:
        schedule.HANDLERS["strategi-alert"] = handler_asli

    with session_scope() as s:
        status2, detail2 = schedule.run_one(s, s.get(Job, job_id))
    assert status2 == "ok" and "dikabarkan" in detail2
    with session_scope() as s:
        assert len(s.scalars(select(Alert)).all()) == 1


def test_sumber_fakta_stale_menghasilkan_status_gagal(db) -> None:
    """Fakta status yang lebih tua dari 26 jam menandai job gagal agar operator tahu data macet."""
    with session_scope() as s:
        _fakta(s, False, menit_lalu=2000)
        _fakta(s, True, menit_lalu=1600)  # 1600 menit = 26.6 jam > 26 jam
    job_id = _job_alert(last_run_menit_lalu=None)

    with session_scope() as s:
        status, detail = schedule.run_one(s, s.get(Job, job_id))
    assert status == "gagal"
    assert "stale > 26 jam" in detail

    with session_scope() as s:
        assert s.scalars(select(Alert)).all() == []
        evt = s.scalars(select(Event).where(Event.type == "job.ran")).one()
        assert evt.severity == "warning"

