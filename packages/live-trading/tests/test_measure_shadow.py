"""Uji ringkas ukur: median + gerbang sampel (bukan cuma mean)."""

from live_trading.measure import _ringkas


def _baris(hasil, r):
    return {"hasil": hasil, "r": r}


def test_ringkas_median_dan_gerbang_sampel():
    rows = [_baris("tp1", 1.0)] * 3 + [_baris("sl", -1.0)] * 2 + [_baris("tp1", 50.0)]
    out = _ringkas(rows)
    assert out["n"] == 6
    assert out["median_r"] == 1.0
    assert out["sampel_cukup"] is False


def test_ringkas_sampel_cukup_50():
    rows = [_baris("tp1", 1.0)] * 30 + [_baris("sl", -1.0)] * 20
    out = _ringkas(rows)
    assert out["n"] == 50
    assert out["sampel_cukup"] is True
    assert out["median_r"] == 1.0
