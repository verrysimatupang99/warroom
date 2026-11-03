from __future__ import annotations

from warroom_worker.jobs.formula import blokir_korelasi_rezim

"Pengawas aturan #9: cap korelasi searah + filter rezim BTC (15 Okt 2026)."


def test_cap_searah_memblokir_ketiga():
    arah = {"SHORT": 2}
    assert blokir_korelasi_rezim("SHORT", arah, "turun", 2, True) is not None
    # arah berlawanan TIDAK diblok korelasi (slot disisakan) — tapi tetap
    # diblok rezim: LONG di tren turun tetap ditahan oleh filter rezim.
    blocks = blokir_korelasi_rezim("LONG", arah, "turun", 2, True) or ""
    assert "korelasi" not in blocks
    assert blokir_korelasi_rezim("LONG", arah, None, 2, True) is None


def test_rezim_berlawanan_memblokir():
    assert "naik" in blokir_korelasi_rezim("SHORT", {}, "naik", 2, True)
    assert "turun" in blokir_korelasi_rezim("LONG", {}, "turun", 2, True)
    # searah rezim lolos
    assert blokir_korelasi_rezim("SHORT", {}, "turun", 2, True) is None
    assert blokir_korelasi_rezim("LONG", {}, "naik", 2, True) is None


def test_filter_nonaktif_atau_rezim_tak_terbaca_tidak_memblokir_rezim():
    assert blokir_korelasi_rezim("SHORT", {}, "naik", 2, False) is None
    assert blokir_korelasi_rezim("SHORT", {}, None, 2, True) is None


def test_cap_tetap_berlaku_tanpa_filter_rezim():
    arah = {"LONG": 2}
    assert blokir_korelasi_rezim("LONG", arah, None, 2, False) is not None
