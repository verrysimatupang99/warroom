"""Tes R5: konteks akun yang dikirim ke Laya.

Sebelum ini Laya hanya menerima `symbol, side, session, price, atr, setup` —
tidak ada balance, equity, floating PnL, atau jumlah posisi. Artinya model menilai
"apakah pasar aman", bukan "apakah trade ini pantas untuk ukuran akun".

Modul job berada di `ops/` (bukan paket), jadi diimpor lewat path berkas.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

JOB = Path(__file__).resolve().parents[3] / "ops" / "laya_verdict_job.py"


def _muat_modul() -> Any:
    spec = importlib.util.spec_from_file_location("laya_verdict_job", JOB)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def job() -> Any:
    return _muat_modul()


def test_akun_lengkap_diringkas(job: Any) -> None:
    telemetri = {
        "connected": True,
        "balance": 456.98,
        "equity": 450.00,
        "floating_pnl": -6.98,
        "free_margin": 380.12,
        "positions": [{"ticket": 1}, {"ticket": 2}],
        "win_rate_pct": 66.7,
        "net_pnl_usd": -43.02,
    }
    k = job.susun_konteks_akun(telemetri)

    assert k["akun_tersedia"] is True
    assert k["balance_usd"] == pytest.approx(456.98)
    assert k["equity_usd"] == pytest.approx(450.00)
    assert k["floating_pnl_usd"] == pytest.approx(-6.98)
    assert k["posisi_terbuka"] == 2
    assert k["free_margin_usd"] == pytest.approx(380.12)
    # -6.98 / 456.98 * 100 = -1.53%
    assert k["floating_pct_balance"] == pytest.approx(-1.53, abs=0.01)


def test_tanpa_telemetri_semua_none(job: Any) -> None:
    k = job.susun_konteks_akun({})

    assert k["akun_tersedia"] is False
    assert k["balance_usd"] is None
    assert k["equity_usd"] is None
    assert k["floating_pct_balance"] is None
    assert k["posisi_terbuka"] is None


def test_ea_terputus_ditandai_tidak_tersedia(job: Any) -> None:
    k = job.susun_konteks_akun({"connected": False, "balance": 456.98})
    assert k["akun_tersedia"] is False
    # Angka yang ada tetap diteruskan apa adanya, tidak dipaksa None
    assert k["balance_usd"] == pytest.approx(456.98)


def test_balance_nol_tidak_membagi_nol(job: Any) -> None:
    k = job.susun_konteks_akun({"connected": True, "balance": 0.0, "floating_pnl": -5.0})
    assert k["floating_pct_balance"] is None


def test_posisi_bukan_list_tidak_pecah(job: Any) -> None:
    k = job.susun_konteks_akun({"connected": True, "positions": "kosong"})
    assert k["posisi_terbuka"] is None


def test_riwayat_verdict_ditulis_sekali_header(job: Any, tmp_path: Path) -> None:
    """CSV dipakai untuk memilih ambang Laya, jadi harus rapi & append-only."""
    log = tmp_path / "riwayat.csv"
    verdicts = {
        "LONG": {"choice": "SKIP", "confidence": 0.1493},
        "SHORT": {"choice": "EXECUTE", "confidence": 0.612},
    }

    job.catat_riwayat("NEW_YORK", 3996.057, 2.452, verdicts, jalur_log=str(log))
    job.catat_riwayat("LONDON", 4000.0, 2.5, verdicts, jalur_log=str(log))

    baris = log.read_text(encoding="utf-8").splitlines()
    assert baris[0] == "ts,session,price,atr,side,choice,confidence"
    assert len(baris) == 5, baris  # header + 2 siklus x 2 arah
    assert baris[1].count(",") == 6
    # header tidak boleh muncul lagi
    assert sum(1 for b in baris if b.startswith("ts,")) == 1


def test_riwayat_gagal_tulis_tidak_melempar(job: Any, tmp_path: Path) -> None:
    """Job tidak boleh mati hanya karena log tidak bisa ditulis."""
    sasaran = tmp_path / "tidak-ada" / "x.csv"
    sasaran.parent.mkdir()
    sasaran.parent.chmod(0o500)
    try:
        job.catat_riwayat("ASIA", 4000.0, 2.0, {"LONG": {"choice": "SKIP", "confidence": 0.1}},
                          jalur_log=str(sasaran))
    finally:
        sasaran.parent.chmod(0o700)
