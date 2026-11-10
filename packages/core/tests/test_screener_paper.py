"""Test screener, provider, dan paper bot (Fase 2-4)."""
from __future__ import annotations

import json

import pytest
from warroom_core.strategi_config.config import muat_config
from warroom_core.strategi_config.paper_bot import Posisi, _cek_tutup, jalankan_paper_bot
from warroom_core.strategi_config.provider import BinanceProvider, provider_untuk
from warroom_core.strategi_config.screener import scan_satu

CONFIG = """
id: t
nama: T
market: crypto
waktu: 1h
simbol: [X]
variabel:
  atr: ATR(14)
  ema: EMA(20)
filter:
  - "atr > 0"
entry_long:
  - "close > ema"
entry_short: []
exit:
  sl_atr: 1.0
  tp_rrr: 2.0
"""


def _tulis(tmp_path, isi=CONFIG):
    p = tmp_path / "s.yaml"
    p.write_text(isi, encoding="utf-8")
    return muat_config(p)


class _ProviderPalsu:
    """Provider stub — mengembalikan candle yang sudah ditentukan."""

    def __init__(self, candles):
        self._c = candles

    def candles(self, simbol, timeframe, limit=300):
        return self._c


def _c(o, h, lo, cl, v=1.0):
    return {"open": o, "high": h, "low": lo, "close": cl, "volume": v}


# ---------- provider ----------

def test_provider_untuk_crypto_dan_memecoin():
    assert isinstance(provider_untuk("crypto"), BinanceProvider)
    assert isinstance(provider_untuk("memecoin"), BinanceProvider)


def test_provider_market_tak_kenal_gagal():
    with pytest.raises(ValueError):
        provider_untuk("polymarket")   # belum ada provider -> fail-closed


# ---------- screener ----------

def test_screener_deteksi_long(tmp_path):
    cfg = _tulis(tmp_path)
    # harga naik terus -> close > EMA20 -> setup long
    candles = [_c(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(60)]
    prov = _ProviderPalsu(candles)
    setup = scan_satu(cfg, "X", prov)
    assert setup is not None
    assert setup.arah == "long"


def test_screener_tidak_match(tmp_path):
    cfg = _tulis(tmp_path)
    # harga turun -> close < EMA -> bukan long
    candles = [_c(200 - i, 201 - i, 199 - i, 199.5 - i) for i in range(60)]
    prov = _ProviderPalsu(candles)
    setup = scan_satu(cfg, "X", prov)
    assert setup is not None
    assert setup.arah == "-"   # entry_long gagal (close < ema)


# ---------- paper bot ----------

def test_paper_bot_buka_dan_tutup_tp(tmp_path):
    cfg = _tulis(tmp_path)
    state = tmp_path / "state"
    # siklus 1: harga naik -> buka long
    candles_naik = [_c(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(60)]
    r1 = jalankan_paper_bot(cfg, _ProviderPalsu(candles_naik), state, modal_per_trade_usd=100)
    assert len(r1["dibuka"]) == 1
    pos_file = state / "posisi_t.json"
    assert pos_file.exists()
    posisi = json.loads(pos_file.read_text())["posisi"]
    assert len(posisi) == 1
    assert posisi[0]["arah"] == "long"

    # siklus 2: harga melonjak -> TP tersentuh -> tutup profit
    entry = posisi[0]["entry"]
    tp = posisi[0]["tp"]
    candle_tp = [_c(tp, tp + 5, entry, tp)]   # high >= tp
    r2 = jalankan_paper_bot(cfg, _ProviderPalsu(candle_tp), state, modal_per_trade_usd=100)
    assert len(r2["ditutup"]) == 1
    assert r2["ditutup"][0]["alasan_exit"] == "tp"
    assert r2["ditutup"][0]["hasil_r"] == pytest.approx(2.0)
    # ledger tertulis
    ledger = state / "trades_t.jsonl"
    assert ledger.exists()
    baris = [json.loads(x) for x in ledger.read_text().strip().splitlines()]
    assert baris[-1]["alasan_exit"] == "tp"


def test_paper_bot_tutup_sl(tmp_path):
    cfg = _tulis(tmp_path)
    state = tmp_path / "state"
    candles_naik = [_c(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(60)]
    jalankan_paper_bot(cfg, _ProviderPalsu(candles_naik), state, modal_per_trade_usd=100)
    posisi = json.loads((state / "posisi_t.json").read_text())["posisi"]
    sl = posisi[0]["sl"]
    entry = posisi[0]["entry"]
    candle_sl = [_c(sl, entry, sl - 5, sl)]   # low <= sl
    r = jalankan_paper_bot(cfg, _ProviderPalsu(candle_sl), state, modal_per_trade_usd=100)
    assert len(r["ditutup"]) == 1
    assert r["ditutup"][0]["alasan_exit"] == "sl"
    assert r["ditutup"][0]["hasil_r"] == pytest.approx(-1.0)


def test_ceks_tutup_short_tp_di_bawah():
    """Regresi: TP short di bawah entry -> profit, bukan rugi."""
    p = Posisi("X", "short", entry=100, sl=102, tp=97, size_usd=100, waktu_entry="t")
    # candle turun menyentuh TP 97
    hasil = _cek_tutup(p, _c(99, 99, 96, 97))
    assert hasil is not None
    assert hasil["alasan_exit"] == "tp"
    assert hasil["hasil_r"] > 0    # profit, bukan rugi
