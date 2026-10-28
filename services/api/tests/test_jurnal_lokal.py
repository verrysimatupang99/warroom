"""Tes filter market pada lapisan data lokal (jurnal)."""

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
