"""Tes klien OKX read-only: bentuk ringkasan dan kejujuran saat kunci tidak ada."""

from __future__ import annotations

import pytest

from live_trading import okx_account as ox


def test_ringkas_akun_membaca_total_eq_dan_jumlah_mata_uang(monkeypatch) -> None:
    monkeypatch.setattr(
        ox,
        "_get",
        lambda path: {
            "code": "0",
            "data": [
                {
                    "totalEq": "1234.56",
                    "details": [{"ccy": "USDT"}, {"ccy": "BTC"}],
                }
            ],
        },
    )
    d = ox.ringkas_akun()
    assert d["total_eq_usd"] == 1234.56
    assert d["mata_uang"] == 2
    assert d["diambil_at"]


def test_ringkas_posisi_menjumlah_upl_dan_menyaring_field(monkeypatch) -> None:
    monkeypatch.setattr(
        ox,
        "_get",
        lambda path: {
            "code": "0",
            "data": [
                {"instId": "BTC-USDT-SWAP", "posSide": "long", "pos": "1",
                 "avgPx": "60000", "upl": "12.5", "lever": "3", "mgnMode": "cross"},
                {"instId": "ETH-USDT-SWAP", "posSide": "short", "pos": "2",
                 "avgPx": "3000", "upl": "-2.5", "lever": "2", "mgnMode": "cross"},
            ],
        },
    )
    d = ox.ringkas_posisi()
    assert d["jumlah"] == 2
    assert d["upl_total_usd"] == 10.0
    assert d["posisi"][0]["instId"] == "BTC-USDT-SWAP"
    assert "OKX" in d["sumber"]


def test_kunci_hilang_menolak_dengan_pesan_jelas(monkeypatch) -> None:
    for nama in ("OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE"):
        monkeypatch.delenv(nama, raising=False)
    with pytest.raises(ox.OkxError, match="kunci OKX tidak ada"):
        ox._get("/api/v5/account/balance")
