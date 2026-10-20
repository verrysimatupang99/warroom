"""Kontrak executor paper — R harus benar, ledger harus konsisten."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from live_trading.config import get_settings
from live_trading.execution.paper import PaperBroker, compute_be_stop, compute_r


def _broker(tmp_path: Path) -> PaperBroker:
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    return PaperBroker(s)


def test_r_long_dan_short(tmp_path: Path) -> None:
    assert compute_r("LONG", 100.0, 95.0, 110.0) == pytest.approx(2.0)  # risiko 5, untung 10
    assert compute_r("SHORT", 100.0, 105.0, 90.0) == pytest.approx(2.0)
    assert compute_r("LONG", 100.0, 95.0, 95.0) == pytest.approx(-1.0)


def test_stop_di_sisi_salah_ditolak() -> None:
    """LONG dengan stop di atas entry = risiko tak terdefinisi. Harus gagal keras."""
    with pytest.raises(ValueError):
        compute_r("LONG", 100.0, 105.0, 110.0)


def test_buka_dan_tutup_menulis_ledger(tmp_path: Path) -> None:
    b = _broker(tmp_path)
    pos = b.open_position(
        pair="BTCUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=200.0
    )

    rec = b.close_position(pos.signal_id, 110.0, "closed_TP2")

    assert rec["r"] == pytest.approx(2.0)
    assert b.positions() == [], "posisi harus hilang setelah ditutup"
    lines = (b.s.ledger_path.read_text(encoding="utf-8")).strip().splitlines()
    assert json.loads(lines[0])["pair"] == "BTCUSDT"


def test_tutup_posisi_tidak_ada_gagal_jelas(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        _broker(tmp_path).close_position("#SIGTIDAKADA", 100.0, "closed_manual")


def test_sl_dihormati_saat_evaluasi(tmp_path: Path) -> None:
    b = _broker(tmp_path)
    b.open_position(
        pair="ETHUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=100.0
    )

    closed = b.evaluate({"ETHUSDT": 94.0})

    assert len(closed) == 1
    assert closed[0]["status"] == "closed_SL"
    assert closed[0]["r"] == pytest.approx(-1.0)
    assert b.positions() == []


def test_tp1_digeser_ke_break_even_bukan_ditutup(tmp_path: Path) -> None:
    """TP1 kena -> posisi tetap jalan, tapi stop ke entry. Ini yang bikin R tak jadi negatif."""
    b = _broker(tmp_path)
    b.open_position(
        pair="SOLUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=100.0
    )

    closed = b.evaluate({"SOLUSDT": 106.0})

    assert closed == []
    pos = b.positions()[0]
    assert pos.status == "tp1_hit_runner"
    assert pos.stop == 100.0


def test_compute_be_stop_long_dan_short() -> None:
    # default fee_buffer_pct = 0.001 (0.10% round-trip)
    assert compute_be_stop("LONG", 100.0) == 100.1
    assert compute_be_stop("SHORT", 100.0) == 99.9
    # custom fee buffer
    assert compute_be_stop("LONG", 1000.0, fee_buffer_pct=0.002) == 1002.0
    assert compute_be_stop("SHORT", 1000.0, fee_buffer_pct=0.002) == 998.0


def test_tp1_digeser_ke_net_break_even_okx(tmp_path: Path) -> None:
    """Saat net_be=True, TP1 kena -> stop digeser ke entry * (1 + fee_buffer) bukan entry murni."""
    b = _broker(tmp_path)
    b.open_position(
        pair="SOLUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=100.0
    )
    b.open_position(
        pair="AVAXUSDT", direction="SHORT", entry=100.0, stop=105.0, tp1=95.0, tp2=90.0, size_usd=100.0
    )

    closed = b.evaluate({"SOLUSDT": 106.0, "AVAXUSDT": 94.0}, net_be=True)
    assert closed == []

    positions = {p.pair: p for p in b.positions()}
    assert positions["SOLUSDT"].status == "tp1_hit_runner"
    assert positions["SOLUSDT"].stop == pytest.approx(100.1)  # 100 * 1.001

    assert positions["AVAXUSDT"].status == "tp1_hit_runner"
    assert positions["AVAXUSDT"].stop == pytest.approx(99.9)  # 100 * 0.999


def test_harga_tidak_diketahui_tidak_menutup_posisi(tmp_path: Path) -> None:
    """Pair tanpa harga (mis. API gagal) harus dilewati, bukan ditutup paksa."""
    b = _broker(tmp_path)
    b.open_position(
        pair="LINKUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=50.0
    )

    assert b.evaluate({}) == []
    assert len(b.positions()) == 1


def test_short_tp2_ditutup_di_harga_tp(tmp_path: Path) -> None:
    b = _broker(tmp_path)
    b.open_position(
        pair="BTCUSDT", direction="SHORT", entry=100.0, stop=105.0, tp1=95.0, tp2=90.0, size_usd=100.0
    )

    closed = b.evaluate({"BTCUSDT": 89.0})

    assert closed[0]["status"] == "closed_TP2"
    assert closed[0]["r"] == pytest.approx(2.0)


def test_closed_at_wib_berlabel_jujur(tmp_path: Path) -> None:
    """Temuan QA 15 Okt 2026: `closed_at` dulu jam WIB berlabel +00:00.

    Akibatnya satu trade tampil beda 7 jam antar panel (feed pakai created_at
    DB yang benar; /riset percaya label dan menambah 7 jam lagi). Sekarang
    offset harus +07:00 dan jamnya cocok dengan waktu WIB nyata.
    """
    import datetime as dt

    b = _broker(tmp_path)
    pos = b.open_position(
        pair="BTCUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0, size_usd=100.0
    )
    rec = b.close_position(pos.signal_id, 110.0, "closed_TP2")

    parsed = dt.datetime.fromisoformat(rec["closed_at"])
    assert parsed.utcoffset() == dt.timedelta(hours=7), "closed_at harus ber-offset +07:00 (WIB)"
    wib_now = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
    assert abs((parsed - wib_now).total_seconds()) < 60, "jam harus waktu WIB saat ini"

    # posisi terbuka juga jujur
    pos2 = b.open_position(
        pair="ETHUSDT", direction="SHORT", entry=100.0, stop=105.0, tp1=95.0, tp2=90.0, size_usd=50.0
    )
    opened = dt.datetime.fromisoformat(pos2.opened_at)
    assert opened.utcoffset() == dt.timedelta(hours=7)


def test_strategi_tersimpan_di_posisi_dan_ledger(tmp_path: Path) -> None:
    """Field strategi diteruskan dari open_position ke PaperPosition dan record ledger."""
    b = _broker(tmp_path)
    pos = b.open_position(
        pair="SOLUSDT",
        direction="LONG",
        entry=150.0,
        stop=145.0,
        tp1=155.0,
        tp2=160.0,
        size_usd=75.0,
        strategi="legacy-smc",
    )
    assert pos.strategi == "legacy-smc"
    # Memastikan tersimpan di berkas positions
    posisi_ulang = b.positions()
    assert len(posisi_ulang) == 1
    assert posisi_ulang[0].strategi == "legacy-smc"

    rec = b.close_position(pos.signal_id, 155.0, "closed_TP1")
    assert rec["strategi"] == "legacy-smc"
    # Memastikan tertulis di ledger
    lines = (b.s.ledger_path.read_text(encoding="utf-8")).strip().splitlines()
    assert json.loads(lines[-1])["strategi"] == "legacy-smc"
