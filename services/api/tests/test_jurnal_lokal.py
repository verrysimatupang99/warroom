"""Tes filter market pada lapisan data lokal (jurnal)."""

import asyncio

import pytest
from warroom_api import lokal


def test_cek_market_menerima_nilai_sah():
    assert lokal._cek_market("all") == "all"
    assert lokal._cek_market("forex") == "forex"
    assert lokal._cek_market("crypto") == "crypto"


def test_cek_market_menolak_nilai_aneh():
    assert lokal._cek_market("") == "all"
    assert lokal._cek_market(None) == "all"
    assert lokal._cek_market("saham") == "all"
    assert lokal._cek_market("CRYPTO") == "crypto"


def test_trade_crypto_dibentuk_seperti_fill(monkeypatch):
    monkeypatch.setattr(
        lokal,
        "_baca_csv",
        lambda p: [
            {"waktu": "2026-10-28T14:57:18+00:00", "koin": "EVAAUSDT", "aksi": "BELI",
             "harga": "1.3962", "qty": "23.65", "pnl_pct": "", "alasan": "breakout_55"},
            {"waktu": "2026-10-28T15:10:00+00:00", "koin": "BLESSUSDT", "aksi": "JUAL",
             "harga": "0.0112", "qty": "2971", "pnl_pct": "+4.28", "alasan": "trailing_stop"},
        ],
    )
    hasil = lokal._trade_crypto()
    assert len(hasil) == 2
    assert hasil[0]["market"] == "crypto"
    assert hasil[0]["side"] == "BUY"
    assert hasil[1]["side"] == "SELL"
    assert hasil[1]["iso"] == "2026-10-28 15:10:00"


def test_ringkas_momentum_menghitung_ekuitas(monkeypatch):
    monkeypatch.setattr(
        lokal,
        "_baca_momentum",
        lambda: {
            "AAAUSDT": {"kas": 100.0, "qty": 10.0, "entry": 5.0, "harga": 6.0},
            "BBBUSDT": {"kas": 500.0, "qty": 0.0, "entry": 0.0, "harga": 0.0},
        },
    )
    r = lokal._ringkas_momentum()
    assert r["aktif"] is True
    assert r["koin"] == 2
    assert r["modal"] == 1000.0
    # 100 + 10*6 + 500 = 660
    assert r["ekuitas"] == 660.0
    assert r["posisi"] == 1


def test_ringkas_momentum_kosong(monkeypatch):
    monkeypatch.setattr(lokal, "_baca_momentum", lambda: None)
    r = lokal._ringkas_momentum()
    assert r == {"aktif": False}


def test_trade_forex_dibentuk_dari_deals(monkeypatch):
    """Trade tertutup = deals.csv; bukan lagi baris fills (entry)."""
    monkeypatch.setattr(
        lokal,
        "_baca_deals",
        lambda: [
            {"iso": "2026-10-30 09:00:00", "symbol": "XAUUSDm", "side": "BUY",
             "volume": "0.02", "open_price": "3900.000", "close_price": "3910.000",
             "net": "20.00", "ticket": "9001"},
        ],
    )
    hasil = lokal._trade_forex()
    assert len(hasil) == 1
    assert hasil[0]["market"] == "forex"
    assert hasil[0]["pnl_usd"] == "20.00"
    assert hasil[0]["price_filled"] == "3910.000"
    assert hasil[0]["open_price"] == "3900.000"

# --- US2.2 edge eksekusi dari fills ------------------------------------------------------

def test_edge_fills_mengelompokkan_per_jam_dan_simbol(monkeypatch):
    monkeypatch.setattr(
        lokal,
        "_baca_fills",
        lambda: [
            {"iso": "2026-10-30 08:05:00", "symbol": "XAUUSDm",
             "slippage_pts": "1.5", "latency_ms": "120"},
            {"iso": "2026-10-30 08:45:00", "symbol": "XAUUSDm",
             "slippage_pts": "-0.5", "latency_ms": "180"},
            {"iso": "2026-10-30 09:10:00", "symbol": "EURUSDm",
             "slippage_pts": "2.0", "latency_ms": ""},
        ],
    )
    hasil = asyncio.run(lokal.journal_edge("forex"))
    assert hasil["n"] == 3
    assert hasil["per_jam"]["08"]["n"] == 2
    assert hasil["per_jam"]["08"]["slip_rata_pts"] == 0.5
    assert hasil["per_jam"]["08"]["slip_terburuk_pts"] == -0.5
    assert hasil["per_jam"]["09"]["n"] == 1
    assert hasil["per_simbol"]["XAUUSDm"]["n"] == 2
    assert hasil["per_simbol"]["EURUSDm"]["slip_rata_pts"] == 2.0
    assert hasil["latensi_rata_ms"] == 150.0


def test_edge_fills_kosong_hanya_503(monkeypatch):
    monkeypatch.setattr(lokal, "_baca_fills", lambda: [])
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_edge("forex"))
    assert "Belum ada fill forex" in str(exc.value)


def test_edge_fills_crypto_ditolak_dengan_alasan(monkeypatch):
    monkeypatch.setattr(lokal, "_baca_fills", lambda: [{"iso": "2026-10-30 08:00:00"}])
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_edge("crypto"))
    assert "slippage nyata" in str(exc.value)
