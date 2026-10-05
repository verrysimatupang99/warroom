"""Regresi: normalisasi kode emiten — sufiks ``.JK`` ganda (6 Okt 2026).

BUG YANG DIKUNCI DI SINI (nyata, produksi):

    symbol 'CAMP.JK'  ->  yfinance membentuk 'CAMP.JK.JK'  ->  404
                      ->  fallback ke Arjum  ->  kuota terpakai

Dampaknya terukur di Hermes Tencent: **1.447 dari 1.474 panggilan yang benar-benar
memakai kuota Arjum** (99%) berasal dari satu jalur ini. yfinance gagal karena sufiks
ganda, lalu fallback ke Arjum — dan fallback itu berbiaya.

Jadi yang diuji bukan "fungsi mengembalikan string", melainkan: **kode dengan sufiks
``.JK`` tidak boleh menghasilkan permintaan yang pasti gagal.**
"""

from __future__ import annotations

import pytest

from live_trading.collectors.idx import ArjumCollector, _kode_bersih


@pytest.mark.parametrize(
    "masuk,keluar",
    [
        ("BBRI", "BBRI"),
        ("BBRI.JK", "BBRI"),          # sufiks Yahoo — ini akar bug-nya
        ("bbri.jk", "BBRI"),          # huruf kecil + sufiks
        ("bbri", "BBRI"),
        ("  CAMP.JK  ", "CAMP"),      # spasi ikut dibersihkan
        ("ANTM.JK", "ANTM"),
        ("GOTO", "GOTO"),
    ],
)
def test_sufiks_jk_dibuang(masuk: str, keluar: str) -> None:
    assert _kode_bersih(masuk) == keluar


def test_idempoten() -> None:
    """Menormalkan dua kali tidak boleh berbeda dari sekali."""
    for kode in ["BBRI", "BBRI.JK", "bbri.jk"]:
        sekali = _kode_bersih(kode)
        assert _kode_bersih(sekali) == sekali


def test_tidak_membuang_titik_yang_bukan_sufiks() -> None:
    """Hanya ``.JK`` di AKHIR yang dibuang — bukan sembarang titik."""
    assert _kode_bersih("A.JK.B") == "A.JK.B"
    assert _kode_bersih("JKS") == "JKS"


def test_kosong_dan_none_aman() -> None:
    # None tidak boleh melempar: kode bisa datang dari payload yang kurang lengkap.
    assert _kode_bersih("") == ""
    assert _kode_bersih(None) == ""


def test_kolektor_memakai_kode_bersih_di_url(monkeypatch) -> None:
    """Penjaga utama: URL yang dibentuk TIDAK boleh memuat ``.JK``.

    Ini tes yang menangkap regresi sebenarnya — kalau seseorang mengembalikan
    ``code.upper()`` di dalam kolektor, URL akan memuat ``CAMP.JK`` dan tes ini gagal.
    """
    dari_url: list[str] = []

    class _Palsu:
        def get(self, path, params=None, **kw):  # noqa: ANN001, ANN003
            dari_url.append(path)
            return {"ok": True}

    k = ArjumCollector.__new__(ArjumCollector)  # tanpa __post_init__ (tak butuh HTTP)
    monkeypatch.setattr(k, "get", _Palsu().get, raising=False)

    k.broker_summary("CAMP.JK")
    k.history("camp.jk", "daily")
    k.analysis("CAMP.JK")

    assert dari_url, "kolektor harus memanggil get()"
    for url in dari_url:
        assert ".JK" not in url, f"sufiks .JK bocor ke URL: {url}"
        assert "CAMP" in url
    assert dari_url[0].endswith("/CAMP")
    assert dari_url[1].startswith("/api/history/CAMP")
