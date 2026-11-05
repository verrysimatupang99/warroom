"""Uji perilaku risk gate `tg-engine` — kode yang mengeksekusi order.

Sebelum 5 Nov 2026 unit ini tidak punya tes sama sekali: ia hanya diperiksa
lewat lint. Aturan gate adalah hal terakhir yang berdiri antara sinyal dan
order nyata, jadi kontraknya dikunci di sini.

Fokus tes: keputusan harus **fail-closed**. Bila bahan penilaian tidak lengkap,
hasilnya REJECTED — tidak pernah APPROVED karena data kosong.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

# Modul ini datar (bukan paket) — sisipkan direktorinya, bukan mengubah struktur app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import risk_gate  # noqa: E402


def _segar(**tambahan):
    """Sinyal BUY yang lolos semua aturan, umurnya baru."""
    dasar = {
        "action": "BUY",
        "symbol": "XAUUSD",
        "entry_low": 3980.0,
        "entry_high": 3982.0,
        "sl": 3970.0,
        "tp1": 4010.0,
        "timestamp": datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(minutes=5),
    }
    dasar.update(tambahan)
    return dasar


class TestComputeRr:
    def test_buy_memakai_entry_terjauh_dari_sl(self):
        # risk dari entry_high (3982-3970=12), reward 4010-3982=28 → 2.33
        # risk dari entry_low (3980-3970=10), reward 4010-3980=30 → 3.0
        # yang dipakai adalah RR TERKECIL (paling jujur)
        rr = risk_gate.compute_rr(_segar())
        assert rr == pytest.approx(28 / 12, rel=1e-6)

    def test_sell(self):
        # entry 4000 → risk 10, reward 30 → 3.0; entry 4002 → risk 8, reward 28 → 3.5
        # RR terkecil (paling jujur) = 3.0
        rr = risk_gate.compute_rr(
            {"action": "SELL", "entry_low": 4000.0, "entry_high": 4002.0, "sl": 4010.0, "tp1": 3970.0}
        )
        assert rr == pytest.approx(3.0, rel=1e-6)

    def test_bahan_kurang_menghasilkan_none_bukan_angka(self):
        assert risk_gate.compute_rr({"action": "BUY"}) is None
        assert risk_gate.compute_rr({"action": "BUY", "sl": 1.0}) is None

    def test_arah_salah_tidak_menghasilkan_rr_palsu(self):
        # BUY tapi SL di atas entry → tidak ada risiko yang bisa dihitung
        assert risk_gate.compute_rr(_segar(sl=3990.0, tp1=4010.0)) is None


class TestSizeLot:
    def test_dibatasi_lot_maksimum(self):
        # saldo besar + SL sangat dekat akan menghasilkan lot raksasa bila tak dibatasi
        assert risk_gate.size_lot(1_000_000.0, 0.01, "XAUUSD") == risk_gate.MAX_LOT

    def test_bahan_kurang_kembali_ke_lot_minimum(self):
        assert risk_gate.size_lot(0.0, 10.0, "XAUUSD") == risk_gate.MIN_LOT
        assert risk_gate.size_lot(500.0, None, "XAUUSD") == risk_gate.MIN_LOT
        assert risk_gate.size_lot(500.0, 0.0, "XAUUSD") == risk_gate.MIN_LOT

    def test_saldo_kecil_tidak_melebihi_minimum(self):
        assert risk_gate.size_lot(10.0, 50.0, "XAUUSD") == risk_gate.MIN_LOT


class TestEvaluate:
    def test_sinyal_sehat_disetujui(self):
        v = risk_gate.evaluate(_segar(), balance=1000.0)
        assert v["decision"] == "APPROVED"
        assert v["reasons"] == []
        assert v["rr"] is not None and v["rr"] >= risk_gate.MIN_RR

    def test_sinyal_basi_ditolak(self):
        tua = _segar(
            timestamp=datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
            - datetime.timedelta(hours=48)
        )
        v = risk_gate.evaluate(tua, balance=1000.0)
        assert v["decision"] == "REJECTED"
        assert any("basi" in r.lower() for r in v["reasons"])

    def test_rr_terlalu_kecil_ditolak(self):
        # TP hanya sedikit di atas entry → RR jauh di bawah 1.5
        v = risk_gate.evaluate(_segar(tp1=3983.0), balance=1000.0)
        assert v["decision"] == "REJECTED"
        assert any("RR" in r for r in v["reasons"])

    def test_data_kosong_ditolak_bukan_disetujui(self):
        v = risk_gate.evaluate({}, balance=1000.0)
        assert v["decision"] == "REJECTED"
        assert len(v["reasons"]) >= 3  # SL, TP1, entry, timestamp

    def test_sl_sama_dengan_entry_ditolak(self):
        v = risk_gate.evaluate(_segar(sl=3980.0), balance=1000.0)
        assert v["decision"] == "REJECTED"
        assert any("SL sama dengan entry" in r for r in v["reasons"])

    def test_arah_tidak_koheren_ditolak(self):
        # BUY tapi TP1 di bawah entry
        v = risk_gate.evaluate(_segar(tp1=3975.0), balance=1000.0)
        assert v["decision"] == "REJECTED"
        assert any("tidak koheren" in r for r in v["reasons"])

    def test_kebijakan_dilaporkan_dalam_hasil(self):
        v = risk_gate.evaluate(_segar(), balance=1000.0)
        assert v["policy"] == {
            "min_rr": risk_gate.MIN_RR,
            "max_age_hours": risk_gate.MAX_AGE_HOURS,
        }
