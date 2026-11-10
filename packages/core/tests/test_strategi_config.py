"""Test layer konfigurasi strategy (formula aman, indikator, config, backtest)."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from warroom_core.strategi_config import (
    ConfigError,
    evaluasi,
    muat_config,
    baca_candles,
    jalankan_backtest,
)
from warroom_core.strategi_config.formula import FormulaError
from warroom_core.strategi_config.variabel import ema, rsi, atr, highest, lowest


# ---------- formula aman ----------

def test_formula_aritmetika_dan_perbandingan():
    assert evaluasi("2 + 3 * 4", {}) == 14
    assert evaluasi("10 > 5", {}) is True
    assert evaluasi("1 < 2 and 3 > 2", {}) is True


def test_formula_resolusi_variabel():
    assert evaluasi("rsi < 35", {"rsi": 30}) is True
    assert evaluasi("rsi < 35", {"rsi": 40}) is False


def test_formula_tolak_injeksi_atribut():
    # akses atribut / dunder harus ditolak (bukan dieksekusi)
    with pytest.raises(FormulaError):
        evaluasi("__import__('os').system('id')", {})
    with pytest.raises(FormulaError):
        evaluasi("a.b", {"a": object()})


def test_formula_tolak_variabel_tak_kenal():
    with pytest.raises(FormulaError):
        evaluasi("xyz + 1", {})


def test_formula_tolak_literal_string():
    with pytest.raises(FormulaError):
        evaluasi("'abc' == 'abc'", {})


def test_formula_indikator_butuh_candles():
    # pemanggilan indikator tanpa __candles__ -> error jelas
    with pytest.raises(FormulaError):
        evaluasi("EMA(20)", {})


# ---------- indikator ----------

def _candles_naik(n=50):
    return [{"open": i, "high": i + 1, "low": i - 1, "close": i + 0.5, "volume": 1.0}
            for i in range(n)]


def test_ema_panjang_dan_nilai():
    candles = _candles_naik(50)
    out = ema(candles, 20)
    assert len(out) == 50
    assert out[18] is None          # belum cukup periode
    assert out[19] is not None      # seed di indeks period-1
    assert out[-1] > out[20]        # tren naik -> EMA naik


def test_highest_mengecualikan_bar_sekarang():
    candles = [{"open": 1, "high": float(i), "low": 0, "close": 1, "volume": 1}
               for i in range(1, 11)]  # high naik 1..10
    out = highest(candles, 3)
    # di indeks 5, highest dari 3 bar SEBELUM (indeks 2,3,4) = high 3,4,5 -> 5
    assert out[5] == 5.0
    assert out[9] == 9.0            # bar sebelum indeks 9 = 7,8,9 -> 9
    assert out[1] is None           # belum cukup period


def test_lowest_mengecualikan_bar_sekarang():
    candles = [{"open": 1, "high": 10, "low": float(i), "close": 1, "volume": 1}
               for i in range(10, 0, -1)]  # low turun 10..1
    out = lowest(candles, 3)
    assert out[5] == min(8.0, 7.0, 6.0)


def test_rsi_batas():
    naik = [{"open": i, "high": i + 1, "low": i, "close": i + 1, "volume": 1}
            for i in range(30)]
    out = rsi(naik, 14)
    assert out[-1] == 100.0         # semua naik -> RSI 100


def test_atr_positif():
    candles = _candles_naik(30)
    out = atr(candles, 14)
    assert out[-1] is not None
    assert out[-1] >= 0


# ---------- config loader ----------

def _tulis_config(tmp_path, isi: str) -> Path:
    p = tmp_path / "s.yaml"
    p.write_text(isi, encoding="utf-8")
    return p


CONFIG_VALID = """
id: t1
nama: Test
market: crypto
waktu: 1h
simbol: [BTCUSDT]
variabel:
  rsi: RSI(14)
  atr: ATR(14)
filter:
  - "atr > 0"
entry_long:
  - "rsi < 30"
exit:
  sl_atr: 1.5
  tp_rrr: 2.0
"""


def test_config_valid(tmp_path):
    cfg = muat_config(_tulis_config(tmp_path, CONFIG_VALID))
    assert cfg.id == "t1"
    assert cfg.simbol == ["BTCUSDT"]
    assert cfg.sl_atr == 1.5


def test_config_kunci_wajib_hilang(tmp_path):
    with pytest.raises(ConfigError):
        muat_config(_tulis_config(tmp_path, "id: x\nnama: y\n"))


def test_config_formula_tak_kenal_ditolak(tmp_path):
    buruk = CONFIG_VALID.replace("rsi < 30", "variabel_hantu < 30")
    with pytest.raises(ConfigError):
        muat_config(_tulis_config(tmp_path, buruk))


def test_config_tanpa_entry_ditolak(tmp_path):
    buruk = CONFIG_VALID.replace('entry_long:\n  - "rsi < 30"\n', "")
    with pytest.raises(ConfigError):
        muat_config(_tulis_config(tmp_path, buruk))


# ---------- backtest ----------

def _candle(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c, "volume": 1.0}


def test_baca_candles_kosong_jika_file_tak_ada(tmp_path):
    assert baca_candles(tmp_path / "tak_ada.csv") == []


def test_backtest_long_tp(monkeypatch, tmp_path):
    """Long: naik ke TP -> +tp_rrr R."""
    cfg = muat_config(_tulis_config(tmp_path, CONFIG_VALID))
    # bar0: rsi rendah (entry long), lalu naik ke TP
    candles = [_candle(100, 100, 100, 100)]  # placeholder, akan dioverride variabel
    # Kita stub evaluasi via variabel: pakai config yang entry selalu long.
    cfg.entry_long = ["atr > 0"]
    cfg.filter = ["atr > 0"]
    candles = [
        _candle(100, 101, 99, 100),    # entry long @100
        _candle(100, 130, 100, 120),   # naik -> TP
    ]
    # injeksi variabel atr & rsi tetap agar kondisi terpenuhi
    import warroom_core.strategi_config.backtest as bt
    monkeypatch.setattr(bt, "_precompute_variabel",
                        lambda cfg, c: {"atr": [1.0, 1.0], "rsi": [10, 10]})
    r = jalankan_backtest(cfg, "X", candles)
    assert r.total_trade == 1
    assert r.trades[0].arah == "long"
    assert r.trades[0].hasil_r == pytest.approx(2.0)  # tp_rrr=2.0


def test_backtest_short_tp_regresi(monkeypatch, tmp_path):
    """Regresi bug TP short: short yang benar harus profit saat harga turun ke TP."""
    cfg = muat_config(_tulis_config(tmp_path, CONFIG_VALID))
    cfg.entry_short = ["atr > 0"]
    cfg.entry_long = []
    cfg.filter = ["atr > 0"]
    candles = [
        _candle(100, 101, 99, 100),   # entry short @100
        _candle(100, 100, 70, 75),    # turun -> TP short (di bawah entry)
    ]
    import warroom_core.strategi_config.backtest as bt
    monkeypatch.setattr(bt, "_precompute_variabel",
                        lambda cfg, c: {"atr": [1.0, 1.0], "rsi": [90, 90]})
    r = jalankan_backtest(cfg, "X", candles)
    assert r.total_trade == 1
    t = r.trades[0]
    assert t.arah == "short"
    assert t.hasil_r == pytest.approx(2.0)  # TP di bawah entry -> PROFIT, bukan rugi
    assert t.tp < t.entry                    # TP short harus di bawah entry


def test_backtest_sl_pesimis(monkeypatch, tmp_path):
    """Jika SL & TP tersentuh di bar sama -> diasumsikan SL (pesimis)."""
    cfg = muat_config(_tulis_config(tmp_path, CONFIG_VALID))
    cfg.entry_long = ["atr > 0"]
    cfg.filter = ["atr > 0"]
    candles = [
        _candle(100, 101, 99, 100),
        _candle(100, 200, 50, 150),   # sentuh SL & TP di bar sama
    ]
    import warroom_core.strategi_config.backtest as bt
    monkeypatch.setattr(bt, "_precompute_variabel",
                        lambda cfg, c: {"atr": [1.0, 1.0], "rsi": [10, 10]})
    r = jalankan_backtest(cfg, "X", candles)
    assert r.trades[0].alasan_exit == "sl"
    assert r.trades[0].hasil_r == pytest.approx(-1.0)
