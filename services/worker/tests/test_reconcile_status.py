"""Regresi: kegagalan rekonsiliasi crypto harus menjadi `status: gagal`, bukan `ok`.

Temuan 31 Okt 2026: handler mengembalikan string berisi `gagal=2` setiap jam, tetapi
runner selalu mencatat `ok`, sehingga `job-health` tidak pernah melihat kegagalan.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import delete
from warroom_core.db import Job, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers


def _jalankan(monkeypatch, rep: dict) -> tuple[str, str]:
    import live_trading.config as cfg
    import live_trading.rekonsiliasi as rek

    monkeypatch.setattr(rek, "rekonsiliasi_watchlist", lambda _state_dir: rep)
    monkeypatch.setattr(cfg, "get_settings", lambda: SimpleNamespace(state_dir="/tmp"))
    register_handlers()
    with session_scope() as s:
        # Tes berbagi DB; buang sisa job dari tes sebelumnya agar nama unik tidak bentrok.
        s.execute(delete(Job).where(Job.name == "reconcile-crypto"))
        job = Job(name="reconcile-crypto", interval_s=3600, enabled=True, payload_json={}, note="")
        s.add(job)
        s.flush()
        return schedule.run_one(s, job)


def test_rekonsiliasi_gagal_menaikkan_status_job(db, monkeypatch) -> None:
    status, detail = _jalankan(
        monkeypatch,
        {
            "diperiksa": 2,
            "baru": [],
            "gagal": [{"signal_id": "XRPUSDT", "alasan": "TimeoutError: candle"}],
        },
    )
    assert status == "gagal"
    assert "gagal=1" in detail
    assert "XRPUSDT" in detail


def test_rekonsiliasi_bersih_tetap_ok(db, monkeypatch) -> None:
    status, detail = _jalankan(
        monkeypatch,
        {"diperiksa": 2, "baru": [], "gagal": []},
    )
    assert status == "ok"
    assert "gagal=0" in detail
