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

# --- US3.2 scanlog forex vs crypto -------------------------------------------------------

def _snapshot_row(ts: str, eval_at: int, alasan: str, sesi: bool = True) -> dict:
    return {
        "observed_at": ts,
        "value_json": {
            "eval_at": eval_at,
            "eval_alasan": alasan,
            "eval_sesi": sesi,
            "eval_atr": 3.8,
            "eval_spread": 0.24,
            "eval_rsi": 55.2,
            "eval_ema_fast": 4001.0,
            "eval_ema_slow": 3995.0,
            "eval_tren": "BULL",
        },
    }


def test_scanlog_forex_memakai_evaluasi_ea_dan_dedup(monkeypatch):
    rows = [
        _snapshot_row("2026-10-30T08:05:00+00:00", 100, "menunggu breakout"),
        _snapshot_row("2026-10-30T08:04:00+00:00", 100, "menunggu breakout"),
        _snapshot_row("2026-10-30T08:03:00+00:00", 99, "spread tipis", sesi=False),
    ]

    async def fake_db(kueri: str, param: dict | None = None) -> list[dict]:
        return rows

    monkeypatch.setattr(lokal, "_db", fake_db)
    hasil = asyncio.run(lokal.journal_scanlog("forex"))
    assert hasil["market"] == "forex"
    assert hasil["sumber"] == "lokal:mt5_snapshot"
    assert hasil["n"] == 2, "evaluasi identik tidak boleh tampil dua kali"
    assert [r["alasan"] for r in hasil["terakhir"]] == ["menunggu breakout", "spread tipis"]
    assert hasil["terakhir"][0]["sesi"] is True
    assert hasil["terakhir"][1]["sesi"] is False
    assert hasil["terakhir"][0]["atr"] == 3.8


def test_scanlog_forex_kosong_503(monkeypatch):
    async def fake_db(kueri: str, param: dict | None = None) -> list[dict]:
        return []

    monkeypatch.setattr(lokal, "_db", fake_db)
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_scanlog("forex"))
    assert "telemetri MT5" in str(exc.value)


def test_scanlog_crypto_membaca_verdicts(monkeypatch, tmp_path):
    berkas = tmp_path / "verdicts.jsonl"
    berkas.write_text(
        '{"ts":"2026-10-30T10:00:00+00:00","pair":"OPUSDT","allowed":false}\n'
        'bukan json\n'
        '{"ts":"2026-10-30T11:00:00+00:00","pair":"AVAXUSDT","allowed":true}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(lokal, "VERDICTS", berkas)
    hasil = asyncio.run(lokal.journal_scanlog("crypto"))
    assert hasil["market"] == "crypto"
    assert hasil["n"] == 3
    assert [r["pair"] for r in hasil["terakhir"]] == ["AVAXUSDT", "OPUSDT"]


def test_scanlog_crypto_tanpa_berkas_503(monkeypatch, tmp_path):
    monkeypatch.setattr(lokal, "VERDICTS", tmp_path / "tidak-ada.jsonl")
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_scanlog("crypto"))
    assert "verdicts" in str(exc.value)


def test_scanlog_all_memuat_dua_market_terpisah(monkeypatch, tmp_path):
    async def fake_db(kueri: str, param: dict | None = None) -> list[dict]:
        return [_snapshot_row("2026-10-30T08:05:00+00:00", 100, "sesi aktif")]

    berkas = tmp_path / "verdicts.jsonl"
    berkas.write_text('{"ts":"2026-10-30T10:00:00+00:00","pair":"OPUSDT"}\n', encoding="utf-8")
    monkeypatch.setattr(lokal, "_db", fake_db)
    monkeypatch.setattr(lokal, "VERDICTS", berkas)

    hasil = asyncio.run(lokal.journal_scanlog("all"))
    assert hasil["market"] == "all"
    assert hasil["forex"]["market"] == "forex"
    assert hasil["crypto"]["market"] == "crypto"
    assert hasil["forex"]["terakhir"][0]["pair"] == "XAUUSD"
    assert hasil["crypto"]["terakhir"][0]["pair"] == "OPUSDT"

# --- US2.4 marker trade + drawdown di kurva ekuitas ---------------------------------------

def test_drawdown_maks_dari_puncak_berjalan():
    deret = [
        {"equity": 1000},
        {"equity": 1100},
        {"equity": 1050},
        {"equity": 990},
        {"equity": 1200},
    ]
    # Puncak 1100 → terendah 990 = 10%; bukan dihitung dari titik awal.
    assert lokal._drawdown_maks(deret) == 10.0
    assert lokal._drawdown_maks([{"equity": 1000}, {"equity": 1000}]) == 0.0
    assert lokal._drawdown_maks([{"equity": None}]) == 0.0


def test_performance_memuat_marker_deal(monkeypatch):
    async def fake_deret(batas: int = 2000) -> list[dict]:
        return [
            {"t": "2026-10-30T08:00:00+00:00", "equity": 1000.0, "balance": 1000.0},
            {"t": "2026-10-30T08:10:00+00:00", "equity": 1010.0, "balance": 1000.0},
        ]

    monkeypatch.setattr(lokal, "_deret_ekuitas", fake_deret)
    monkeypatch.setattr(
        lokal,
        "_trade_forex",
        lambda: [
            {"iso": "2026-10-30 08:05:00", "ticket": "9001", "symbol": "XAUUSDm",
             "side": "SELL", "pnl_usd": "8.50"},
            {"iso": "2026-10-30 08:07:00", "ticket": "9002", "symbol": "XAUUSDm",
             "side": "BUY", "pnl_usd": ""},
        ],
    )
    hasil = asyncio.run(lokal.journal_performance("forex"))
    assert hasil["n_titik"] == 2
    assert hasil["drawdown_max_pct"] == 0.0
    assert [m["ticket"] for m in hasil["markers"]] == ["9001", "9002"]
    assert hasil["markers"][0]["net_usd"] == 8.5
    assert hasil["markers"][1]["net_usd"] is None, "net kosong jangan dibaca 0"


def test_performance_crypto_tetap_menolak():
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_performance("crypto"))
    assert "belum direkam" in str(exc.value)

# --- jurnal sinyal terkirim ---------------------------------------------------------------

def test_journal_signals_membaca_berkas(monkeypatch, tmp_path):
    import json

    p = tmp_path / "jurnal_sinyal.json"
    p.write_text(json.dumps({"ringkas": {"n_terkirim": 2, "winrate": 50.0}}), encoding="utf-8")
    monkeypatch.setattr(lokal, "JURNAL_SINYAL", p)
    hasil = asyncio.run(lokal.journal_signals())
    assert hasil["ringkas"]["n_terkirim"] == 2


def test_journal_signals_belum_ada_503(monkeypatch, tmp_path):
    monkeypatch.setattr(lokal, "JURNAL_SINYAL", tmp_path / "tidak-ada.json")
    with pytest.raises(lokal.SumberKosong) as exc:
        asyncio.run(lokal.journal_signals())
    assert "belum dihitung" in str(exc.value)
