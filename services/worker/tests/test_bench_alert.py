"""Regresi: alert 'benched' hanya dibuat pada TRANSISI aktif→benched.

Kalau alert dibuat tiap siklus alih-alih tiap transisi, strategi yang duduk di
bangku sehari menghasilkan spam tiap 3 menit — kelas masalah yang sama dengan
temuan 197 alert untuk 12 sinyal unik di signal-sync.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from warroom_core.db import Alert, Event, Job, Strategy, session_scope
from warroom_worker.jobs import register_handlers
from warroom_worker.jobs.llm import alert_bench_jika_transisi


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        for model in (Alert, Event, Job, Strategy):
            s.execute(sa_delete(model))
    register_handlers()
    yield


def _bench(tmp_path: Path, *, trade: int = 1, fee: float = 999.0, now=None):
    from live_trading.bench import BatasStrategi, BenchHarian

    return BenchHarian(
        tmp_path / "bench.json",
        batas=BatasStrategi(maks_trade=trade, maks_fee_usd=fee),
        now=now,
    )


def test_transisi_trade_mengabarkan_sekali(db, tmp_path: Path) -> None:
    bench = _bench(tmp_path, trade=1)
    status_sebelum = bench.status("smc")
    assert status_sebelum == "aktif"
    entri = bench.catat("smc", fee_usd=0.05)

    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench, "smc", status_sebelum=status_sebelum, entri=entri
        ) is True

    # Siklus berikutnya strategi masih benched → tidak ada transisi baru, tidak ada alert baru.
    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench, "smc", status_sebelum="aktif", entri=entri
        ) is False

    with session_scope() as s:
        rows = s.scalars(select(Alert).where(Alert.subject == f"strategi/benched:smc:{bench.hari()}")).all()
        assert len(rows) == 1
        assert rows[0].severity == "warning"
        assert "batas 1 trade harian tercapai" in rows[0].message
        assert "1 trade" in rows[0].message


def test_belum_transisi_tidak_mengabarkan(db, tmp_path: Path) -> None:
    bench = _bench(tmp_path, trade=3)
    status_sebelum = bench.status("smc")
    entri = bench.catat("smc", fee_usd=0.05)

    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench, "smc", status_sebelum=status_sebelum, entri=entri
        ) is False
    with session_scope() as s:
        assert s.scalars(select(Alert)).all() == []


def test_transisi_fee_mengabarkan_dengan_alasan_fee(db, tmp_path: Path) -> None:
    bench = _bench(tmp_path, trade=99, fee=1.0)
    status_sebelum = bench.status("golden")
    entri = bench.catat("golden", fee_usd=1.5)

    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench, "golden", status_sebelum=status_sebelum, entri=entri
        ) is True

    with session_scope() as s:
        alert = s.scalars(select(Alert)).one()
        assert alert.subject == f"strategi/benched:golden:{bench.hari()}"
        assert "batas fee $1.00/hari tercapai" in alert.message


def test_benched_hari_berbeda_menghasilkan_alert_baru(db, tmp_path: Path) -> None:
    import datetime as dt

    waktu_hari1 = dt.datetime(2026, 10, 19, 10, 0, tzinfo=dt.UTC)
    waktu_hari2 = dt.datetime(2026, 10, 20, 10, 0, tzinfo=dt.UTC)

    # Hari 1: transisi ke benched
    bench1 = _bench(tmp_path, trade=1, now=lambda: waktu_hari1)
    status_sebelum = bench1.status("smc")
    entri1 = bench1.catat("smc", fee_usd=0.05)
    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench1, "smc", status_sebelum=status_sebelum, entri=entri1
        ) is True

    # Hari 2: status reset ke aktif, lalu trade baru memicu benched lagi
    bench2 = _bench(tmp_path, trade=1, now=lambda: waktu_hari2)
    status_sebelum_hari2 = bench2.status("smc")
    assert status_sebelum_hari2 == "aktif"
    entri2 = bench2.catat("smc", fee_usd=0.05)
    with session_scope() as s:
        assert alert_bench_jika_transisi(
            s, bench2, "smc", status_sebelum=status_sebelum_hari2, entri=entri2
        ) is True

    # Kedua alert harus ada di DB dengan subjek tanggal masing-masing
    with session_scope() as s:
        rows = s.scalars(select(Alert).order_by(Alert.id)).all()
        assert len(rows) == 2
        assert rows[0].subject == "strategi/benched:smc:2026-10-19"
        assert rows[1].subject == "strategi/benched:smc:2026-10-20"
