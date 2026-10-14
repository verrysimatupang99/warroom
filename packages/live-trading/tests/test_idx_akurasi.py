"""Uji akurasi IDX — angka harus SAMA dengan drift mesin Tencent (bukti 6 Okt).

Ledger contoh memakai baris nyata yang sudah diverifikasi: BSJP gabungan n=45
meanR 0,6079; angka berbeda = bug, bukan sudut pandang.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from live_trading import idx_akurasi as A

SKEMA = """
CREATE TABLE signals (
  event_id TEXT PRIMARY KEY, job_id TEXT, created_at TEXT, ticker TEXT, setup TEXT,
  source TEXT, direction TEXT, entry_low REAL, entry_high REAL, sl REAL, tp1 REAL,
  tp2 REAL, status TEXT, filled_at TEXT, closed_at TEXT, result TEXT, net_r REAL,
  costs_r REAL, data_source TEXT, freshness_s REAL, duplicate_of TEXT, note TEXT,
  producer TEXT, source_timestamp TEXT, graded_at TEXT, grader_version TEXT
)
"""


def _buat(db: Path, baris: list[tuple]) -> None:
    con = sqlite3.connect(db)
    con.execute(SKEMA)
    con.executemany(
        "INSERT INTO signals (event_id, ticker, setup, status, closed_at, result, net_r,"
        " costs_r, grader_version) VALUES (?,?,?,?,?,?,?,?,?)",
        baris,
    )
    con.commit()
    con.close()


def test_ledger_tidak_ada_bukan_error(tmp_path: Path):
    assert A.read_ledger(tmp_path / "hilang.db") == []
    r = A.summarize_accuracy(tmp_path / "hilang.db")
    assert r["tersedia"] is False and "tidak terbaca" in r["alasan"]


def test_metrik_hanya_dari_tuntas(tmp_path: Path):
    db = tmp_path / "l.db"
    _buat(db, [
        # BSJP_STRONG: 3 tuntas menang, 2 kalah
        ("e1", "AAAA", "BSJP_STRONG", "CLOSED", "2026-09-18T09:00+07:00", "TP1", 1.0, 0.0, "v2"),
        ("e2", "AAAB", "BSJP_STRONG", "CLOSED", "2026-09-18T09:00+07:00", "TP1", 1.0, 0.0, "v2"),
        ("e3", "AAAC", "BSJP_STRONG", "CLOSED", "2026-09-19T09:00+07:00", "TP1", 1.0, 0.0, "v2"),
        ("e4", "AAAD", "BSJP_STRONG", "CLOSED", "2026-09-20T09:00+07:00", "SL", -1.0, 0.0, "v2"),
        ("e5", "AAAE", "BSJP_STRONG", "CLOSED", "2026-09-21T09:00+07:00", "SL", -1.0, 0.0, "v2"),
        # belum tuntas → TIDAK boleh masuk metrik
        ("e6", "AAAF", "BSJP_STRONG", "CREATED", None, None, None, None, "v2"),
        ("e7", "AAAG", "BSJP_STRONG", "CREATED", None, None, None, None, "v2"),
        # ambigu → terhitung terpisah, tidak masuk win/loss
        ("e8", "AAAH", "BSJP_STRONG", "CLOSED", "2026-09-22T09:00+07:00", "AMBIGUOUS", 0.0, 0.0, "v2"),
    ])
    h = A.compute_accuracy(A.read_ledger(db), setup_min=1)
    assert h["tuntas"] == 5 and h["belum_tuntas"] == 2 and h["ambigu"] == 1
    s = h["per_setup"]["BSJP_STRONG"]
    assert s["n"] == 5, "ambigu & belum tuntas tidak boleh ikut"
    assert s["n_hari"] == 4
    assert s["winrate_pct"] == 60.0
    assert s["total_r"] == 1.0
    assert s["belum_tuntas"] == 2


def test_pakem_pakai_hari_independen(tmp_path: Path):
    """20 baris tuntas tapi hanya 4 hari → tetap INSUFFICIENT (bukan 'terbukti')."""
    db = tmp_path / "l.db"
    baris = []
    for i in range(20):
        hari = ["2026-09-18", "2026-09-19", "2026-09-22", "2026-09-23"][i % 4]
        baris.append((f"e{i}", "AAAA", "BSJP_STRONG", "CLOSED", f"{hari}T09:00+07:00", "TP1", 1.0, 0.0, "v2"))
    _buat(db, baris)
    h = A.compute_accuracy(A.read_ledger(db), setup_min=1)
    s = h["per_setup"]["BSJP_STRONG"]
    assert s["n"] == 20 and s["n_hari"] == 4
    assert s["pakem"] == "INSUFFICIENT"
    assert any("sampel kurang" in a for a in s["alasan"])


def test_setup_kecil_tidak_ditampilkan_sebagai_akurasi(tmp_path: Path):
    db = tmp_path / "l.db"
    _buat(db, [("e1", "AAAA", "BSJP_ARA", "CLOSED", "2026-09-18T09:00+07:00", "TP1", 1.0, 0.0, "v2")])
    h = A.compute_accuracy(A.read_ledger(db))
    s = h["per_setup"]["BSJP_ARA"]
    assert s["pakem"] == "INSUFFICIENT"
    assert s["winrate_pct"] is None, "n kecil jangan tampil seperti akurasi"
    assert any("belum ditampilkan" in a for a in s["alasan"])


def test_bsjp_gabungan_dihitung(tmp_path: Path):
    db = tmp_path / "l.db"
    b = []
    for i in range(3):
        b.append((f"a{i}", "X", "BSJP_ARA", "CLOSED", f"2026-09-2{i}T09:00+07:00", "TP1", 0.5, 0.0, "v2"))
    for i in range(3):
        b.append((f"b{i}", "Y", "BSJP_STRONG", "CLOSED", f"2026-09-2{i}T09:00+07:00", "SL", -1.0, 0.0, "v2"))
    _buat(db, b)
    h = A.compute_accuracy(A.read_ledger(db), setup_min=1)
    g = h["bsjp_gabungan"]
    assert g["n"] == 6 and g["total_r"] == 3 * 0.5 + 3 * -1.0


def test_angka_cocok_dengan_drift_tencent(tmp_path: Path):
    """Bila nanti diberi ledger asli: BSJP n=45 meanR≈0,6079; ARA n=198 meanR≈−0,7024."""
    ledger = Path("/home/admin/live-trading/state/idx_ledger.db")
    if not ledger.is_file():
        import pytest

        pytest.skip("ledger produksi belum diimpor")
    h = A.summarize_accuracy(ledger)
    if not h.get("tersedia"):
        import pytest

        pytest.skip("ledger tidak terbaca")
    bsjp = h["bsjp_gabungan"]
    assert bsjp is not None
    assert bsjp["n"] == 45
    assert abs(bsjp["mean_r"] - 0.6079) < 0.002
    ara = h["per_setup"]["ARA_HUNTER"]
    assert ara["n"] == 198
    assert abs(ara["mean_r"] - (-0.7024)) < 0.002
    assert ara["pakem"] == "INSUFFICIENT", "5 hari bursa → belum bisa diklaim"


def test_timeout_masuk_tuntas(tmp_path: Path):
    """TIMEOUT = posisi ditutup di pasar dengan net_r nyata → masuk metrik.

    Kalau dikeluarkan, kerugian nyata terbuang dan angka terlihat lebih baik
    (kasus nyata INTRADAY: +0,107 vs −0,011).
    """
    db = tmp_path / "l.db"
    _buat(db, [
        ("e1", "A", "INTRADAY", "CLOSED", "2026-09-21T10:00+07:00", "TP1", 2.0, 0.0, "v3"),
        ("e2", "B", "INTRADAY", "CLOSED", "2026-09-21T11:00+07:00", "TIMEOUT", -0.6, 0.0, "v3"),
        ("e3", "C", "INTRADAY", "CLOSED", "2026-09-22T10:00+07:00", "SL", -1.0, 0.0, "v3"),
    ])
    h = A.compute_accuracy(A.read_ledger(db), setup_min=1)
    s = h["per_setup"]["INTRADAY"]
    assert s["n"] == 3
    assert abs(s["mean_r"] - (2.0 - 0.6 - 1.0) / 3) < 1e-3  # dibulatkan 4 desimal
    assert h["tuntas"] == 3


def test_angka_intraday_cocok_dengan_drift(tmp_path: Path):
    """Dengan ledger produksi: INTRADAY n=35 meanR≈−0,0108 (termasuk 7 timeout)."""
    ledger = Path("/home/admin/live-trading/state/idx_ledger.db")
    if not ledger.is_file():
        import pytest

        pytest.skip("ledger produksi belum diimpor")
    h = A.summarize_accuracy(ledger)
    if not h.get("tersedia"):
        import pytest

        pytest.skip("ledger tidak terbaca")
    intra = h["per_setup"]["INTRADAY"]
    assert intra["n"] == 35, "7 timeout harus ikut terhitung"
    assert abs(intra["mean_r"] - (-0.0108)) < 0.002
    assert h["tuntas"] == 278
