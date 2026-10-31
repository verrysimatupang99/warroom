"""Tes filter kalender makro (fungsi murni, tanpa jaringan)."""

from warroom_api.routers.kalender import _saring

DATA = [
    {"title": "CPI m/m", "country": "USD", "date": "2026-10-29T20:30:00-04:00",
     "impact": "High", "forecast": "0.3%", "previous": "0.2%"},
    {"title": "Retail Sales", "country": "EUR", "date": "2026-10-29T09:00:00-04:00",
     "impact": "Medium", "forecast": "", "previous": "1.1%"},
    {"title": "Bank Holiday", "country": "JPY", "date": "2026-10-29T00:00:00-04:00",
     "impact": "Holiday", "forecast": "", "previous": ""},
    {"title": "Trade Balance", "country": "NZD", "date": "2026-10-29T21:45:00-04:00",
     "impact": "Low", "forecast": "", "previous": ""},
    {"title": "GDP q/q", "country": "IDR", "date": "2026-10-29T04:00:00-04:00",
     "impact": "High", "forecast": "5.0%", "previous": "4.9%"},
]


def test_holiday_selalu_dibuang():
    hasil = _saring(DATA, "semua")
    assert all(a["dampak"].lower() != "holiday" for a in hasil)
    assert len(hasil) == 4


def test_dampak_tinggi_hanya_high():
    hasil = _saring(DATA, "tinggi")
    assert {a["judul"] for a in hasil} == {"CPI m/m", "GDP q/q"}


def test_utama_membuang_mata_uang_bukan_utama():
    hasil = _saring(DATA, "utama")
    judul = {a["judul"] for a in hasil}
    # IDR tidak termasuk mata uang utama, jadi GDP q/q keluar meski dampaknya High.
    assert judul == {"CPI m/m", "Retail Sales"}


def test_bentuk_keluaran_stabil():
    hasil = _saring(DATA, "semua")
    kunci = {"judul", "mata_uang", "waktu", "dampak", "perkiraan", "sebelumnya"}
    assert all(set(a) == kunci for a in hasil)


def test_forecast_kosong_jadi_none():
    hasil = _saring(DATA, "semua")
    retail = next(a for a in hasil if a["judul"] == "Retail Sales")
    assert retail["perkiraan"] is None
    cpi = next(a for a in hasil if a["judul"] == "CPI m/m")
    assert cpi["perkiraan"] == "0.3%"


def test_dampak_semua_tetap_menyertakan_low():
    hasil = _saring(DATA, "semua")
    assert any(a["dampak"].lower() == "low" for a in hasil)
