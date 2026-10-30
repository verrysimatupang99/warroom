"""Tes watchdog forward test: telemetri mati saat sesi & deal tertutup tidak tercatat."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, Strategy, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers

# Rabu, 28 Okt 2026 — hari kerja, di dalam sesi Reaper 08–09.
SESI = datetime(2026, 10, 28, 8, 30, tzinfo=UTC)
LUAR_SESI = datetime(2026, 10, 28, 12, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        for model in (Fact, Event, Alert, Job, Strategy):
            s.execute(sa_delete(model))
    register_handlers()
    yield


def _fakta(jam_server: datetime, umur_s: int, total: int | None = 0, hash_: str = "h") -> Fact:
    server_time = int(jam_server.timestamp()) - umur_s
    nilai = {"server_time": server_time}
    if total is not None:
        nilai["total_trades_today"] = total
    return Fact(
        kind="mt5_snapshot",
        key="ringkas",
        value_json=nilai,
        source="uji",
        observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
        ttl_s=300,
        hash=hash_,
    )


def _jalan(tmp_path: Path, **payload):
    deals = tmp_path / "deals.csv"
    state = tmp_path / "watchdog.json"
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "forwardtest-watchdog"))
        job.payload_json = {
            "deals_path": str(deals),
            "state_path": str(state),
            **payload,
        }
        return schedule.run_one(s, job)


def _alert_subjek() -> list[str]:
    with session_scope() as s:
        return [a.subject for a in s.scalars(select(Alert)).all()]


def test_telemetri_mati_saat_sesi_memicu_alert(tmp_path) -> None:
    with session_scope() as s:
        s.add(_fakta(SESI, 300))
    status, detail = _jalan(tmp_path)
    assert status == "ok"
    assert "sesi=ya" in detail
    assert "alert=1" in detail
    assert _alert_subjek() == ["forwardtest/telemetri"]


def test_telemetri_mati_di_luar_sesi_tidak_memicu_alert(tmp_path) -> None:
    with session_scope() as s:
        s.add(_fakta(LUAR_SESI, 300))
    status, detail = _jalan(tmp_path)
    assert status == "ok"
    assert "sesi=tidak" in detail
    assert _alert_subjek() == []


def test_telemetri_segar_tidak_memicu_alert_dan_menutup_alert_lama(tmp_path) -> None:
    with session_scope() as s:
        s.add(_fakta(SESI, 300, hash_="basi"))
    _jalan(tmp_path)
    assert _alert_subjek() == ["forwardtest/telemetri"]

    with session_scope() as s:
        s.add(_fakta(SESI, 5, hash_="segar"))
    _, detail = _jalan(tmp_path)
    assert "alert=0" in detail
    assert "pulih=1" in detail
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "forwardtest/telemetri"))
        assert a.ack_at is not None
        assert "PULIH otomatis" in a.message


def test_deal_tertutup_hilang_alert_setelah_grace(tmp_path) -> None:
    state = tmp_path / "watchdog.json"
    state.write_text(
        json.dumps({"tanggal": "2026-10-28", "total": 4, "deal": 0, "selisih": 0}),
        encoding="utf-8",
    )
    with session_scope() as s:
        s.add(_fakta(SESI, 5, total=5))
    status, detail = _jalan(tmp_path)
    assert status == "ok"
    assert "selisih=1" in detail
    assert _alert_subjek() == [], "grace 5 menit belum lewat"

    # Perlambat waktu: sejak kapan selisih terlihat sudah > grace.
    data = json.loads(state.read_text(encoding="utf-8"))
    data["hilang_sejak"] = (datetime.now(UTC) - timedelta(seconds=400)).isoformat()
    state.write_text(json.dumps(data), encoding="utf-8")

    _, detail = _jalan(tmp_path)
    assert "alert=1" in detail
    assert _alert_subjek() == ["forwardtest/deal-hilang"]


def test_trade_pertama_hari_itu_terdeteksi(tmp_path) -> None:
    """Regresi: baseline `total=0` tidak boleh dibaca sebagai "belum ada data"."""
    state = tmp_path / "watchdog.json"
    state.write_text(
        json.dumps({"tanggal": "2026-10-28", "total": 0, "deal": 0, "selisih": 0}),
        encoding="utf-8",
    )
    with session_scope() as s:
        s.add(_fakta(SESI, 5, total=1))
    _, detail = _jalan(tmp_path)
    assert "selisih=1" in detail


def test_deal_yang_tercatat_menutup_selisih_dan_alert(tmp_path) -> None:
    deals = tmp_path / "deals.csv"
    state = tmp_path / "watchdog.json"
    state.write_text(
        json.dumps({"tanggal": "2026-10-28", "total": 4, "deal": 0, "selisih": 1,
                    "hilang_sejak": (datetime.now(UTC) - timedelta(seconds=400)).isoformat()}),
        encoding="utf-8",
    )
    with session_scope() as s:
        s.add(_fakta(SESI, 5, total=4))
        s.add(Alert(severity="kritis", subject="forwardtest/deal-hilang",
                    message="deal hilang", suggested_action="periksa"))
    deals.write_text(
        "ts,iso,ticket,position,close_time,net\n1793000000,2026-10-28 08:30:00,77,77,"
        "2026.10.28 08:30:00,8.5\n",
        encoding="utf-8",
    )
    _, detail = _jalan(tmp_path)
    assert "selisih=0" in detail
    assert "pulih=1" in detail
    with session_scope() as s:
        a = s.scalar(select(Alert).where(Alert.subject == "forwardtest/deal-hilang"))
        assert a.ack_at is not None


def test_tanpa_fakta_telemetri_watchdog_diam(tmp_path) -> None:
    status, detail = _jalan(tmp_path)
    assert status == "ok"
    assert "menunggu telemetri" in detail
    assert _alert_subjek() == []
