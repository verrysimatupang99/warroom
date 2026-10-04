"""Tes pencatat posisi LP — inti: IL vs hold harus bisa dijawab, dan yang tidak diketahui
harus ditulis "belum diketahui" bukan ditebak.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from live_trading import lp_positions as L


def _masuk(d: Path, **kw) -> dict:
    arg = {
        "rantai": "sol",
        "alamat_pool": "PoolABC",
        "pasangan": "TOKEN/SOL",
        "jumlah_base": 1000.0,
        "jumlah_quote": 1.0,
    }
    arg.update(kw)
    return L.catat_masuk(d, **arg)


def test_catat_masuk_lalu_keluar(tmp_path: Path) -> None:
    _masuk(tmp_path)
    p = L.catat_keluar(
        tmp_path, rantai="sol", alamat_pool="PoolABC", jumlah_base=1010.0, jumlah_quote=1.01
    )
    assert p["keluar_base"] == 1010.0
    lap = L.laporan(tmp_path)
    assert lap["jumlah"] == 1 and lap["terbuka"] == 0 and lap["tertutup"] == 1


def test_tolak_posisi_setengah_hati(tmp_path: Path) -> None:
    """LP tanpa kedua kaki tidak bisa dihitung — lebih baik ditolak daripada bikin angka palsu."""
    with pytest.raises(ValueError):
        _masuk(tmp_path, jumlah_quote=0)
    with pytest.raises(ValueError):
        _masuk(tmp_path, jumlah_base=-5)


def test_tolak_keluar_tanpa_posisi_terbuka(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        L.catat_keluar(
            tmp_path, rantai="sol", alamat_pool="TidakAda", jumlah_base=1, jumlah_quote=1
        )


def test_kedua_kaki_naik_proporsi_sama_berarti_il_nol(tmp_path: Path) -> None:
    """IL == hold tepat ketika kenaikan proporsi kedua kaki sama."""
    _masuk(tmp_path, jumlah_base=1000.0, jumlah_quote=1.0)
    L.catat_keluar(tmp_path, rantai="sol", alamat_pool="PoolABC", jumlah_base=1100.0, jumlah_quote=1.1)
    h = L.laporan(tmp_path)["riwayat"][-1]["hitung"]
    assert h["kenaikan_base_pct"] == 10.0
    assert h["kenaikan_quote_pct"] == 10.0
    assert h["il_vs_hold_pct"] == 0.0
    assert h["menang"] == "seri"


def test_klaim_bagspay_menghasilkan_hold_menang(tmp_path: Path) -> None:
    """Angka PERSIS dari klaim poster: 5,71K + 0,035 SOL -> 6,23K + 0,077 SOL.

    Menambah kuantitas di kedua kaki (tanda fee masuk) TIDAK cukup: karena modal awal
    98,8% ada di kaki SOL, dan kaki SOL naik +120% sementara BAGSPAY cuma +9,1%,
    memegang (hold) justru jauh lebih untung. Inilah yang tidak pernah disebut klaim itu.
    """
    _masuk(tmp_path, jumlah_base=5710.0, jumlah_quote=0.035)
    L.catat_keluar(tmp_path, rantai="sol", alamat_pool="PoolABC", jumlah_base=6230.0, jumlah_quote=0.077)
    h = L.laporan(tmp_path)["riwayat"][-1]["hitung"]
    assert h["jumlah_kedua_kaki_naik"] is True  # fee memang masuk
    assert h["kenaikan_quote_pct"] == 120.0
    assert h["kenaikan_base_pct"] == pytest.approx(9.107, abs=0.01)
    assert h["menang"] == "hold"
    assert h["il_vs_hold_pct"] < 0  # LP kalah jauh dari sekadar memegang
    assert h["imbalance"] > 2.0  # komposisi makin tak seimbang


def test_dengan_harga_lengkap_bisa_hitung_usd(tmp_path: Path) -> None:
    _masuk(
        tmp_path,
        jumlah_base=1000.0,
        jumlah_quote=1.0,
        harga_usd_base=2.0,
        harga_usd_quote=100.0,
    )
    L.catat_keluar(
        tmp_path,
        rantai="sol",
        alamat_pool="PoolABC",
        jumlah_base=1000.0,
        jumlah_quote=1.0,
        harga_usd_base=3.0,
        harga_usd_quote=90.0,
    )
    h = L.laporan(tmp_path)["riwayat"][-1]["hitung"]
    assert h["unit"] == "USD"
    assert h["nilai_masuk_usd"] == pytest.approx(2100.0)  # 1000*2 + 1*100
    assert h["nilai_keluar_usd"] == pytest.approx(3090.0)  # 1000*3 + 1*90
    # hold: 1000 token @3 + 1 SOL @90 = 3090 -> sama, jadi seri
    assert h["menang"] == "seri"


def test_harga_tidak_lengkap_tidak_menebak_usd(tmp_path: Path) -> None:
    _masuk(tmp_path, harga_usd_base=2.0)  # hanya satu kaki ada harganya
    L.catat_keluar(tmp_path, rantai="sol", alamat_pool="PoolABC", jumlah_base=1, jumlah_quote=1)
    h = L.laporan(tmp_path)["riwayat"][-1]["hitung"]
    assert "nilai_masuk_usd" not in h
    assert h["unit"] == "rasio (tanpa harga)"


def test_posisi_terbuka_punya_umur(tmp_path: Path) -> None:
    _masuk(tmp_path)
    lap = L.laporan(tmp_path)
    assert lap["posisi_terbuka"][0]["umur_jam"] == pytest.approx(0.0, abs=0.1)
    assert lap["tertutup"] == 0


def test_berkas_rusak_dianggap_kosong(tmp_path: Path) -> None:
    (tmp_path / L.NAMA_BERKAS).write_text("{ bukan json", encoding="utf-8")
    assert L.laporan(tmp_path)["jumlah"] == 0


def test_tersimpan_di_berkas_json(tmp_path: Path) -> None:
    _masuk(tmp_path)
    isi = json.loads((tmp_path / L.NAMA_BERKAS).read_text(encoding="utf-8"))
    assert isinstance(isi, list) and isi[0]["pool"] == "sol:poolabc"


def test_dari_lp_cari_membuat_rujukan(tmp_path: Path) -> None:
    """Hasil `dexscreen.lp_cari` bisa langsung jadi rujukan catat_masuk."""
    ref = L.dari_lp_cari(
        {
            "rantai": "solana",
            "alamat": "PoolXYZ",
            "pair": "BAGSPAY/SOL",
            "dex": "meteora",
            "label_pool": "DYN2",
        }
    )
    assert ref["rantai"] == "solana" and ref["label_pool"] == "DYN2"
    p = L.catat_masuk(
        tmp_path, jumlah_base=100, jumlah_quote=0.1, pasangan=ref["pasangan"],
        alamat_pool=ref["alamat_pool"], rantai=ref["rantai"],
    )
    assert p["pasangan"] == "BAGSPAY/SOL"
