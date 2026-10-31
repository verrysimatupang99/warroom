"""Tes modul SNR: deteksi swing, pengelompokan zona, dan validasi posisi SL."""

from __future__ import annotations

from warroom_core.forex.snr import (
    Zona,
    bangun_zona,
    deteksi_swing,
    peta_snr,
    sl_terlindungi,
    zona_mengandung,
)


def _candles(highs: list[float], lows: list[float]) -> list[dict]:
    pasangan = zip(highs, lows, strict=True)
    return [{"h": float(h), "l": float(lo), "o": float(lo), "c": float(lo), "v": 1.0} for h, lo in pasangan]


def test_deteksi_swing_menemukan_puncak_dan_dasar():
    highs = [1, 2, 3, 9, 3, 2, 1, 2, 3, 2, 1]
    lows = [9, 8, 7, 2, 7, 8, 9, 8, 7, 8, 9]
    sh, sl = deteksi_swing(_candles(highs, lows), kiri=2, kanan=2)
    assert 9 in sh
    assert 2 in sl


def test_deteksi_swing_data_kurang_mengembalikan_kosong():
    sh, sl = deteksi_swing(_candles([1, 2], [1, 2]), kiri=3, kanan=3)
    assert sh == [] and sl == []


def test_bangun_zona_mengelompokkan_level_berdekatan():
    zona = bangun_zona([100.0, 100.4, 100.8, 120.0], toleransi=1.0, jenis="support")
    assert len(zona) == 2
    assert zona[0].sentuhan == 3
    assert zona[0].bawah == 100.0 and zona[0].atas == 100.8
    assert zona[1].sentuhan == 1


def test_bangun_zona_kosong():
    assert bangun_zona([], 1.0, "support") == []


def test_peta_snr_tanpa_atr_mengembalikan_kosong():
    c = _candles([1, 2, 3, 2, 1], [1, 2, 3, 2, 1])
    assert peta_snr(c, atr=0.0) == []


def test_zona_mengandung_dengan_buffer():
    z = Zona(bawah=100.0, atas=101.0, sentuhan=2, jenis="support")
    assert zona_mengandung(z, 100.5)
    assert not zona_mengandung(z, 99.0)
    assert zona_mengandung(z, 99.5, buffer=0.6)


def test_sl_long_di_bawah_support_terlindungi():
    zona = [Zona(bawah=100.0, atas=101.0, sentuhan=3, jenis="support")]
    aman, alasan = sl_terlindungi(entry=105.0, sl=99.0, zonas=zona, buffer=0.0)
    assert aman, alasan


def test_sl_long_di_dalam_support_rentan():
    zona = [Zona(bawah=100.0, atas=101.0, sentuhan=3, jenis="support")]
    aman, alasan = sl_terlindungi(entry=105.0, sl=100.5, zonas=zona, buffer=0.0)
    assert not aman
    assert "di dalam zona support" in alasan


def test_sl_short_di_atas_resistance_terlindungi():
    zona = [Zona(bawah=109.0, atas=110.0, sentuhan=2, jenis="resistance")]
    aman, _ = sl_terlindungi(entry=105.0, sl=111.0, zonas=zona, buffer=0.0)
    assert aman


def test_sl_short_di_dalam_resistance_rentan():
    zona = [Zona(bawah=109.0, atas=110.0, sentuhan=2, jenis="resistance")]
    aman, alasan = sl_terlindungi(entry=105.0, sl=109.5, zonas=zona, buffer=0.0)
    assert not aman
    assert "resistance" in alasan


def test_tanpa_zona_relevan_dianggap_aman():
    aman, alasan = sl_terlindungi(entry=105.0, sl=99.0, zonas=[], buffer=0.0)
    assert aman
    assert "tidak ada zona" in alasan
