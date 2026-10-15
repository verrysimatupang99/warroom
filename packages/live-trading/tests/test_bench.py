"""Regresi: batas trade + fee harian per strategi dengan status 'benched'.

Yang dikunci:
1. Default (belum ada trade) → 'aktif', boleh entry.
2. Setelah `maks_trade` trade → 'benched', entry ditolak dengan alasan jelas.
3. Fee harian melebihi `maks_fee_usd` → 'benched' meski jumlah trade masih di bawah.
4. Reset harian WIB: ganti hari → status kembali 'aktif'.
5. State bertahan antar-instance (ditulis ke berkas) dan ringkas menampilkan status.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from live_trading.bench import BatasStrategi, BenchHarian


def _jam(hari: int, jam: int = 12) -> dt.datetime:
    """WIB palsu: 2026-10-<hari> <jam> WIB (offset +07:00)."""
    return dt.datetime(2026, 10, hari, jam, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=7)))


def _bench(tmp_path: Path, *, trade: int = 3, fee: float = 1.0, hari: int = 16) -> BenchHarian:
    return BenchHarian(
        tmp_path / "bench.json",
        batas=BatasStrategi(maks_trade=trade, maks_fee_usd=fee),
        now=lambda: _jam(hari),
    )


def test_default_aktif(tmp_path: Path) -> None:
    b = _bench(tmp_path)
    assert b.status("smc") == "aktif"
    assert b.boleh_entry("smc") == (True, "aktif")


def test_trade_melebihi_batas_jadi_benched(tmp_path: Path) -> None:
    b = _bench(tmp_path, trade=2)
    b.catat("smc")
    assert b.status("smc") == "aktif"
    b.catat("smc")  # mencapai batas 2
    assert b.status("smc") == "benched"
    ok, alasan = b.boleh_entry("smc")
    assert ok is False and "benched" in alasan and "2/2" in alasan


def test_fee_melebihi_batas_jadi_benched(tmp_path: Path) -> None:
    b = _bench(tmp_path, trade=10, fee=1.0)  # batas trade longgar, fee ketat
    b.catat("golden", fee_usd=0.6)
    assert b.status("golden") == "aktif"
    b.catat("golden", fee_usd=0.5)  # total 1.1 ≥ 1.0
    assert b.status("golden") == "benched"
    ok, alasan = b.boleh_entry("golden")
    assert ok is False and "fee" in alasan


def _bench_dengan_jam(tmp_path: Path, jam: dt.datetime, *, trade: int = 1) -> BenchHarian:
    return BenchHarian(
        tmp_path / "bench.json",
        batas=BatasStrategi(maks_trade=trade, maks_fee_usd=999.0),
        now=lambda: jam,
    )


def test_reset_harian_wib(tmp_path: Path) -> None:
    b16 = _bench_dengan_jam(tmp_path, _jam(16))
    b16.catat("smc")
    assert b16.status("smc") == "benched"  # batas 1 trade tercapai

    # hari berikutnya (WIB) → reset, boleh lagi
    b17 = _bench_dengan_jam(tmp_path, _jam(17))
    assert b17.status("smc") == "aktif"
    assert b17.boleh_entry("smc")[0] is True


def test_state_bertahan_antar_instance_dan_ringkas(tmp_path: Path) -> None:
    b = _bench(tmp_path, trade=2)
    b.catat("smc", fee_usd=0.1)
    b.catat("golden", fee_usd=0.2)

    # instance baru membaca berkas yang sama
    b2 = _bench(tmp_path, trade=2)
    r = b2.ringkas()
    assert r["smc"]["trade"] == 1 and r["smc"]["status"] == "aktif"
    assert r["golden"]["fee_usd"] == 0.2
    # strategi berbeda tidak saling mempengaruhi
    b2.catat("smc")
    assert b2.status("smc") == "benched"
    assert b2.status("golden") == "aktif"
