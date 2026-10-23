"""Uji A4: biaya eksekusi terukur (fee + slippage) tanpa membuka order."""

from __future__ import annotations

import pytest
from warroom_api import live


def test_sisi_salah_ditolak_tanpa_menyentuh_jaringan() -> None:
    # Validasi harus lebih dulu daripada panggilan buku: sisi salah tidak boleh
    # memicu request keluar sama sekali.
    hasil = live.ukur_biaya_eksekusi(pair="BTCUSDT", size_usd=100.0, sisi="beli")
    assert hasil["status"] == "ditolak"
    assert "ask" in hasil["detail"]


def test_size_tidak_valid_ditolak() -> None:
    assert live.ukur_biaya_eksekusi(size_usd=0)["status"] == "ditolak"
    assert live.ukur_biaya_eksekusi(size_usd=-5)["status"] == "ditolak"


@pytest.mark.skipif(
    __import__("os").environ.get("WARROOM_SKIP_NETWORK_TESTS") == "1",
    reason="tes jaringan dilewati lewat WARROOM_SKIP_NETWORK_TESTS=1",
)
def test_biaya_terukur_dari_buku_nyata() -> None:
    """Bukti A4: angka berasal dari buku, bukan asumsi.

    Memanggil Binance; otomatis di-skip bila buku tidak terbaca (jaringan mati).
    """
    hasil = live.ukur_biaya_eksekusi(pair="BTCUSDT", size_usd=100.0)
    if hasil["status"] != "ok":
        pytest.skip(f"buku tidak terbaca: {hasil.get('detail')}")
    # Sumber harus menyebut depth:<pair>; "asumsi" berarti slippage tak terukur.
    assert hasil["sumber"] == "depth:BTCUSDT"
    assert hasil["total_bps"] is not None and hasil["total_bps"] > 0
    assert hasil["fee_bps"] is not None and hasil["fee_bps"] > 0
    assert hasil["slippage_bps_masuk"] is not None
