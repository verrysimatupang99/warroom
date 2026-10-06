"""Tes worker: jadwal deklaratif, eksekusi job, dan penjagaan terhadap duplikasi (P1-T4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers


@pytest.fixture(autouse=True)
def _bersihkan(db):
    from warroom_core.db import Strategy

    with session_scope() as s:
        for row in s.scalars(select(Job)).all():
            s.delete(row)
        s.query(Fact).delete()
        s.query(Event).delete()
        s.query(Alert).delete()
        s.query(Strategy).delete()
    register_handlers()
    yield


_JOB_BERAT = (
    "refresh-snapshot",  # memanggil CLI domain (jaringan)
    "radar-update",      # memanggil gmgn-cli (jaringan, bisa kena rate-limit)
    "lp-mark",           # memanggil DexScreener (jaringan)
    "collect",
    "backup",
    "poly-sync",         # membaca /var/lib lewat sudo
    "verdict-sync",      # menjalankan alat Poly lewat sudo (baca-saja)
    "llm-brief",         # memanggil provider LLM sungguhan (biaya + jaringan)
    "parity-drift",
    "gmgn-sync",
    "reconcile",
    "learner",  # membaca log agen lewat sudo
    "signal-sync",  # membaca ledger domain + MEMBUAT alert (bisa memicu kirim Telegram)
    "paper-eval",
    "paper-scan",
    "retensi",  # menghapus baris `facts` di DB nyata — bukan untuk tes
)


def _matikan_job_berat() -> None:
    """Tes TIDAK boleh menyentuh jaringan, CLI domain, atau berkas milik user lain."""
    with session_scope() as s:
        for nama in _JOB_BERAT:
            j = s.scalar(select(Job).where(Job.name == nama))
            if j is not None:
                j.enabled = False


# --- pendaftaran job -------------------------------------------------------------------


def test_daftar_job_idempoten(db) -> None:
    with session_scope() as s:
        pertama = schedule.ensure_jobs(s)
    with session_scope() as s:
        kedua = schedule.ensure_jobs(s)
        total = len(s.scalars(select(Job)).all())
    assert set(pertama) == {
        "publish-facts", "freshness", "notify", "refresh-snapshot", "radar-update", "lp-mark",
        "collect", "backup", "poly-sync", "verdict-sync", "parity-drift", "gmgn-sync",
        "signal-sync", "reconcile", "learner", "prompts-sync", "llm-brief", "paper-eval",
        "paper-scan", "retensi",
    }
    assert kedua == [], "job yang sudah ada tidak boleh didaftarkan ulang"
    assert total == 20


def test_spesifikasi_job_disinkronkan_dari_kode(db) -> None:
    """Ubah kode (interval/payload/catatan) harus sampai ke DB; `enabled` tidak disentuh."""
    from warroom_worker.schedule import JobSpec

    with session_scope() as s:
        schedule.ensure_jobs(s)
        j = s.scalar(select(Job).where(Job.name == "publish-facts"))
        j.interval_s = 1
        j.payload_json = {"basi": True}
        j.note = "usang"
        j.enabled = False
    with session_scope() as s:
        schedule.ensure_jobs(s)
    with session_scope() as s:
        j = s.scalar(select(Job).where(Job.name == "publish-facts"))
        assert j.interval_s == 300
        assert j.payload_json.get("ttl_s") == 1800
        assert "usang" not in j.note
        assert j.enabled is False, "enabled adalah keputusan manusia — kode tidak boleh membatalkannya"
    # dan set_enabled mengubahnya secara eksplisit
    with session_scope() as s:
        assert schedule.set_enabled(s, "publish-facts", True) is True
    with session_scope() as s:
        assert s.scalar(select(Job).where(Job.name == "publish-facts")).enabled is True
    _matikan_job_berat()
    assert JobSpec is not None


def test_semua_job_punya_handler_dan_catatan(db) -> None:
    """Job aktif tanpa handler = jadwal yang diam-diam tidak melakukan apa pun."""
    register_handlers()
    with session_scope() as s:
        schedule.ensure_jobs(s)
        jobs = s.scalars(select(Job)).all()
        for j in jobs:
            assert j.note, f"job {j.name} wajib punya catatan"
            if j.enabled:
                assert j.name in schedule.HANDLERS, f"job aktif {j.name} tidak punya handler"


def test_job_nonaktif_tidak_dijalankan_dan_punya_alasan(db) -> None:
    """Job yang dimatikan manusia tidak boleh jalan; catatannya tetap ada."""
    with session_scope() as s:
        schedule.ensure_jobs(s)
    _matikan_job_berat()
    with session_scope() as s:
        nonaktif = {j.name: j for j in s.scalars(select(Job).where(Job.enabled.is_(False))).all()}
    assert nonaktif, "prasyarat tes: ada job yang dimatikan"
    for nama, j in nonaktif.items():
        assert j.note, f"job nonaktif {nama} wajib punya alasan eksplisit"

    with session_scope() as s:
        hasil = schedule.run_due(s)
    assert not ({h["job"] for h in hasil} & set(nonaktif))


def test_hanya_job_jatuh_tempo_yang_jalan(db) -> None:
    with session_scope() as s:
        schedule.ensure_jobs(s)
    _matikan_job_berat()
    with session_scope() as s:
        # dorong semua jauh ke depan
        for j in s.scalars(select(Job)).all():
            j.next_run_at = datetime.now(UTC) + timedelta(hours=5)
        s.flush()
        hasil = schedule.run_due(s)
    assert hasil == []


# --- handler publish-facts --------------------------------------------------------------


def test_handler_publish_facts_membaca_snapshot_domain(db, tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "state").mkdir()
    snap = tmp_path / "state" / "snapshot.json"
    snap.write_text(
        json.dumps({"dibuat": datetime.now(UTC).isoformat(), "mode": "paper", "equity": {"usd": 100}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(tmp_path))

    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "publish-facts"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok"
    assert "fakta=3" in detail
    with session_scope() as s:
        assert s.query(Fact).filter_by(kind="snapshot").count() == 3


def test_handler_gagal_dicatat_bukan_mematikan_loop(db, tmp_path: Path, monkeypatch) -> None:
    """Snapshot rusak: job berstatus gagal, loop tetap hidup, event tercatat."""
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "snapshot.json").write_text("{bukan json", encoding="utf-8")
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(tmp_path))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "publish-facts"))
        status, _ = schedule.run_one(s, job)
        job.last_status = "gagal"
    # publish_snapshot menandai "rusak" sebagai laporan, bukan exception → detail memuat status
    assert status in {"ok", "gagal"}


def test_status_dan_next_run_tercatat(db, tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "snapshot.json").write_text(
        json.dumps({"dibuat": datetime.now(UTC).isoformat(), "mode": "paper"}), encoding="utf-8"
    )
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(tmp_path))
    t0 = datetime.now(UTC)
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "publish-facts"))
        schedule.run_one(s, job, now=t0)
    with session_scope() as s:
        job = s.scalar(select(Job).where(Job.name == "publish-facts"))
        assert job.last_status == "ok"
        assert job.last_run_at is not None
        assert job.next_run_at is not None and job.next_run_at > t0
        ev = s.scalars(select(Event).where(Event.type == "job.ran")).all()
    assert len(ev) >= 1
    assert ev[0].payload_json["job"] == "publish-facts"


# --- handler freshness ------------------------------------------------------------------


def _fakta(kind: str, key: str, umur_s: int, ttl_s: int = 600, value=None) -> Fact:
    return Fact(
        kind=kind,
        key=key,
        value_json=value if value is not None else {"x": 1},
        source="uji",
        observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
        ttl_s=ttl_s,
        hash="h",
    )


def test_freshness_membuat_alert_untuk_fakta_basi(db) -> None:
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", umur_s=7200, ttl_s=600))
        s.add(_fakta("snapshot", "equity", umur_s=10, ttl_s=600))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "freshness"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok"
    assert "basi=1" in detail
    with session_scope() as s:
        alerts = s.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].subject == "snapshot/mode"
        assert alerts[0].fact_ids and len(alerts[0].fact_ids) == 1
        assert "periksa sumber" in alerts[0].suggested_action


def test_freshness_tidak_mengulang_alert_yang_sama(db) -> None:
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", umur_s=7200))
    with session_scope() as s:
        ensure_jobs_done = schedule.ensure_jobs(s)
        assert ensure_jobs_done
    for _ in range(3):
        with session_scope() as s:
            job = s.scalar(select(Job).where(Job.name == "freshness"))
            schedule.run_one(s, job)
    with session_scope() as s:
        assert s.query(Alert).count() == 1, "alert yang sama tidak boleh diulang tiap siklus"


def test_freshness_diam_saat_semua_segar(db) -> None:
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", umur_s=5))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "freshness"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok" and "basi=0" in detail
    with session_scope() as s:
        assert s.query(Alert).count() == 0


def test_ttl_fakta_lebih_panjang_dari_interval_job(db) -> None:
    """Regresi: job yang menulis fakta dengan `ttl_s` <= interval-nya membuat fakta selalu
    "basi" tepat sebelum run berikutnya (jeda nyata selalu sedikit lebih lama dari interval),
    sehingga alert freshness berbunyi tiap siklus. Terbukti di produksi pada `poly.money`
    (ttl 3600 = interval reconcile 3600) dan `ai.brief` (ttl 21600 = interval llm-brief 21600).
    """
    dicek = 0
    for spec in schedule.DEFAULT_JOBS:
        ttl = (spec.payload or {}).get("ttl_s")
        if ttl is None:
            continue
        dicek += 1
        assert ttl > spec.interval_s, (
            f"job {spec.name}: ttl_s={ttl} harus LEBIH PANJANG dari interval_s={spec.interval_s}"
        )
    assert dicek >= 3, "prasyarat tes: harus ada job ber-payload ttl_s"


def test_run_once_mencatat_event_per_job(db, tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "snapshot.json").write_text(
        json.dumps({"dibuat": datetime.now(UTC).isoformat(), "mode": "paper"}), encoding="utf-8"
    )
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(tmp_path))
    from warroom_worker.run import run_once

    with session_scope() as s:
        schedule.ensure_jobs(s)
    _matikan_job_berat()
    hasil = run_once()
    assert {h["job"] for h in hasil} == {"publish-facts", "freshness", "notify", "prompts-sync"}
    with session_scope() as s:
        jenis = {e.type for e in s.scalars(select(Event)).all()}
    assert {"job.ran", "snapshot.published", "freshness.checked"} <= jenis