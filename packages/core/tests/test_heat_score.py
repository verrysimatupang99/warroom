"""Kontrak skor heat: terukur, jujur soal komponen yang tidak terbaca.

Yang dikunci:
1. Tanpa komponen terukur → skor None (bukan 0) — 0 adalah angka, "tidak ada" bukan.
2. Komponen bernilai 0 TETAP dihitung (0 nyata ≠ tidak terbaca).
3. Nilai di atas referensi di-clamp ke 100; nilai negatif di-clamp ke 0.
4. Cakupan melaporkan bagian bobot yang benar-benar terukur.
"""

from __future__ import annotations

import pytest
from warroom_core.heat_score import HeatComponent, hitung_heat


def test_tanpa_komponen_ditolak() -> None:
    with pytest.raises(ValueError):
        hitung_heat([])


def test_semua_tidak_terbaca_skor_none_bukan_nol() -> None:
    h = hitung_heat([
        HeatComponent(nama="funding", nilai=None, referensi=0.05),
        HeatComponent(nama="oi", nilai=None, referensi=10.0),
    ])
    assert h.skor is None
    assert h.cakupan == 0.0
    assert "n/a" in h.catatan
    assert h.komponen[0].skor is None


def test_satu_komponen_terukur() -> None:
    h = hitung_heat([HeatComponent(nama="volume", nilai=50.0, referensi=100.0)])
    assert h.skor == 50
    assert h.cakupan == 1.0


def test_rata_berbobot_dan_cakupan_mengikuti_komponen_terukur() -> None:
    h = hitung_heat([
        HeatComponent(nama="a", nilai=50.0, referensi=100.0, bobot=1.0),
        HeatComponent(nama="b", nilai=10.0, referensi=100.0, bobot=1.0),
        HeatComponent(nama="c", nilai=None, referensi=100.0, bobot=2.0),
    ])
    assert h.skor == 30, "rata-rata berbobot dari komponen terukur saja"
    assert h.cakupan == 0.5, "2 dari 4 bobot terukur"
    assert "c" in h.catatan


def test_nol_adalah_nilai_nyata_bukan_tidak_terbaca() -> None:
    h = hitung_heat([HeatComponent(nama="chg", nilai=0.0, referensi=10.0)])
    assert h.skor == 0
    assert h.cakupan == 1.0


def test_clamp_atas_dan_bawah() -> None:
    penuh = hitung_heat([HeatComponent(nama="vol", nilai=250.0, referensi=100.0)])
    assert penuh.skor == 100
    dasar = hitung_heat([HeatComponent(nama="funding", nilai=-3.0, referensi=1.0)])
    assert dasar.skor == 0


def test_bobot_nol_or_negatif_ditolak() -> None:
    with pytest.raises(ValueError):
        HeatComponent(nama="x", nilai=1.0, referensi=1.0, bobot=0.0)
    with pytest.raises(ValueError):
        HeatComponent(nama="x", nilai=1.0, referensi=0.0)


def test_to_dict_lengkap() -> None:
    h = hitung_heat([HeatComponent(nama="vol", nilai=10.0, referensi=100.0, catatan="hipotesis")])
    d = h.to_dict()
    assert d["skor"] == 10
    assert d["komponen"][0]["nama"] == "vol"
    assert d["komponen"][0]["catatan"] == "hipotesis"
