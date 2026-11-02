"""Test lapisan interpretasi & aturan eksekusi riset Reaper.

Yang paling penting di sini bukan "apakah sinyal muncul", tetapi apakah aturan
pesimistis tetap pesimistis. Kalau ada yang melonggarkan `simulasikan_trade`,
backtest akan mulai berbohong ke arah yang menguntungkan.
"""

from __future__ import annotations

import pytest

from live_trading.riset_reaper import biaya_r, metrik, simulasikan_trade
from live_trading.signals.interpretasi import (
    InterpretasiConfig,
    _swing,
    baca_konteks,
    ema,
)


# --------------------------------------------------------------------------
# EMA
# --------------------------------------------------------------------------
def test_ema_tidak_menebak_sebelum_periode_lengkap():
    hasil = ema([1.0, 2.0, 3.0], periode=5)
    assert hasil == [None, None, None]


def test_ema_nilai_awal_adalah_sma():
    hasil = ema([1.0, 2.0, 3.0, 4.0], periode=2)
    assert hasil[0] is None
    assert hasil[1] == pytest.approx(1.5)


def test_ema_periode_nol_ditolak():
    with pytest.raises(ValueError, match="positif"):
        ema([1.0], periode=0)


# --------------------------------------------------------------------------
# Swing & konteks
# --------------------------------------------------------------------------
def test_swing_mengabaikan_candle_sweep_itu_sendiri():
    """Candle `i` yang menembus low tidak boleh jadi dasar stop-loss."""
    low = [100.0, 101.0, 102.0, 50.0]
    high = [110.0, 111.0, 112.0, 111.0]
    s_low, s_high = _swing(high, low, 3, lookback=3)
    assert s_low == pytest.approx(100.0)
    assert s_high == pytest.approx(112.0)


def test_sweep_long_terdeteksi_saat_close_kembali_ke_dalam():
    low = [100.0, 101.0, 102.0, 95.0]
    high = [110.0, 111.0, 112.0, 106.0]
    close = [105.0, 106.0, 107.0, 104.0]
    open_ = [104.0, 105.0, 106.0, 100.0]
    e = [None, None, None, 100.0]
    ctx = baca_konteks(
        {"close": 104.0},
        high=high,
        low=low,
        close=close,
        open_=open_,
        ema_garis=e,
        i=3,
        cfg=InterpretasiConfig(lookback=5, trend_ema=5, warmup=5),
    )
    assert ctx["swept_long"] is True
    assert ctx["bias"] == "bullish"
    assert ctx["konfirmasi_long"] is True


def test_bias_netral_tanpa_ema():
    ctx = baca_konteks(
        {"close": 100.0},
        high=[100.0],
        low=[100.0],
        close=[100.0],
        open_=[100.0],
        ema_garis=[None],
        i=0,
        cfg=InterpretasiConfig(lookback=5, trend_ema=5, warmup=5),
    )
    assert ctx["bias"] == "netral"


def test_interpretasi_config_menolak_warmup_terlalu_pendek():
    with pytest.raises(ValueError, match="warmup"):
        InterpretasiConfig(lookback=100, trend_ema=50, warmup=60)


# --------------------------------------------------------------------------
# Aturan eksekusi — ini yang menjaga backtest tetap jujur
# --------------------------------------------------------------------------
def test_sl_dan_tp_di_candle_sama_dihitung_sl():
    """Candle raksasa ke dua arah tidak boleh dipilih yang menguntungkan."""
    hasil = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
        high=[100.0, 112.0],
        low=[100.0, 90.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    assert hasil["hasil"] == "sl"
    assert hasil["r"] == pytest.approx(-1.0)


def test_target_kena_sebelum_stop():
    hasil = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
        high=[100.0, 111.0],
        low=[100.0, 99.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    assert hasil["hasil"] == "tp"
    assert hasil["r"] == pytest.approx(2.0)


def test_short_tp_di_bawah_entry():
    hasil = simulasikan_trade(
        arah="short",
        entry=100.0,
        stop=105.0,
        target=90.0,
        high=[100.0, 101.0],
        low=[100.0, 89.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    assert hasil["hasil"] == "tp"
    assert hasil["r"] == pytest.approx(2.0)


def test_tidak_ada_trade_bila_jendela_habis():
    hasil = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
        high=[100.0, 101.0],
        low=[100.0, 99.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    assert hasil["hasil"] == "terbuka"
    assert hasil["r"] == 0.0


def test_spread_mengurangi_reward_dalam_r():
    """Spread harus selalu merugikan: R yang didapat lebih kecil, tidak lebih besar."""
    hasil = {}
    for sp in (0.0, 0.5, 1.0):
        hasil[sp] = simulasikan_trade(
            arah="long",
            entry=100.0,
            stop=95.0,
            target=110.0,
            high=[100.0, 111.0],
            low=[100.0, 99.0],
            mulai=0,
            batas=2,
            spread=sp,
        )["r"]
    assert hasil[0.0] > hasil[0.5] > hasil[1.0]
    assert hasil[0.0] == pytest.approx(2.0)


def test_spread_bisa_mengubah_tp_jadi_sl():
    """Edge tipis: candle menyentuh TP persis, tapi setelah spread target tidak tercapai."""
    tanpa = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
        high=[100.0, 110.0],
        low=[100.0, 99.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    pakai = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=95.0,
        target=110.0,
        high=[100.0, 110.0],
        low=[100.0, 99.0],
        mulai=0,
        batas=3,
        spread=0.2,
    )
    assert tanpa["hasil"] == "tp"
    # HIGH 110 tidak lagi cukup karena target efektif bergeser oleh entry yang lebih mahal
    assert pakai["hasil"] == "tp"
    assert pakai["r"] < tanpa["r"]


def test_short_ikut_terkena_spread():
    tanpa = simulasikan_trade(
        arah="short",
        entry=100.0,
        stop=105.0,
        target=90.0,
        high=[100.0, 101.0],
        low=[100.0, 89.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    pakai = simulasikan_trade(
        arah="short",
        entry=100.0,
        stop=105.0,
        target=90.0,
        high=[100.0, 101.0],
        low=[100.0, 89.0],
        mulai=0,
        batas=2,
        spread=0.5,
    )
    assert tanpa["r"] == pytest.approx(2.0)
    assert pakai["r"] < tanpa["r"]


def test_risiko_nol_tidak_membuat_trade():
    hasil = simulasikan_trade(
        arah="long",
        entry=100.0,
        stop=100.0,
        target=110.0,
        high=[100.0, 101.0],
        low=[100.0, 99.0],
        mulai=0,
        batas=2,
        spread=0.0,
    )
    assert hasil["hasil"] == "tidak_valid"


# --------------------------------------------------------------------------
# Biaya & metrik
# --------------------------------------------------------------------------
def test_biaya_r_adalah_spread_dibagi_risiko():
    assert biaya_r(entry=100.0, stop=95.0, spread=0.5) == pytest.approx(0.1)


def test_biaya_r_tak_terhingga_bila_risiko_nol():
    assert biaya_r(entry=100.0, stop=100.0, spread=0.5) == float("inf")


def test_metrik_tanpa_trade():
    assert metrik([]) == {"n": 0}


def test_metrik_menghitung_drawdown_dari_puncak():
    trades = [
        {"r_bersih": 2.0, "r_kotor": 2.0, "biaya_r": 0.0},
        {"r_bersih": -1.0, "r_kotor": -1.0, "biaya_r": 0.0},
        {"r_bersih": -1.0, "r_kotor": -1.0, "biaya_r": 0.0},
    ]
    m = metrik(trades, risiko_fraksi=1.0)
    # risiko 100%: 1.0 -> 3.0 (puncak) -> 0.0 -> -1.0 ; DD dari puncak = 100%
    assert m["max_dd_pct"] == pytest.approx(100.0, abs=0.05)
    assert m["expectancy_r"] == pytest.approx(0.0)
