"""Tes job okx-sync: fakta akun/posisi ditulis, bukan diklaim tanpa data."""

from __future__ import annotations

from sqlalchemy import delete, select
from warroom_core.db import Fact, Job, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers


def _bersihkan() -> None:
    with session_scope() as s:
        s.execute(delete(Fact).where(Fact.kind.in_(("okx.account", "okx.positions"))))


def test_okx_sync_menulis_fakta_akun_dan_posisi(db, monkeypatch) -> None:
    import live_trading.okx_account as ox

    monkeypatch.setattr(
        ox,
        "ringkas_akun",
        lambda: {"total_eq_usd": 100.0, "mata_uang": 2, "diambil_at": "2026-11-01T00:00:00+00:00",
                 "sumber": "OKX /account/balance (read-only)"},
    )
    monkeypatch.setattr(
        ox,
        "ringkas_posisi",
        lambda: {"jumlah": 1, "upl_total_usd": 2.5, "posisi": [], "diambil_at": "x",
                 "sumber": "OKX /account/positions (read-only)"},
    )
    register_handlers()
    _bersihkan()
    try:
        with session_scope() as s:
            job = Job(name="okx-sync", interval_s=300, enabled=True, payload_json={"ttl_s": 900}, note="")
            s.add(job)
            s.flush()
            status, detail = schedule.run_one(s, job)
            assert status == "ok"
            assert "equity_usd=100.0" in detail and "posisi=1" in detail
            kinds = set(s.scalars(select(Fact.kind)).all())
            assert {"okx.account", "okx.positions"} <= kinds
    finally:
        _bersihkan()
