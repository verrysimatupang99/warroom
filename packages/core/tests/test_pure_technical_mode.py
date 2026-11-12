"""Unit tests untuk BE-01 / US-01: Pure Technical Mode Fallback (WARROOM_LAYA_INFERENSI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from warroom_core.forex import laya_verdict
from warroom_core.forex.strategies.multi_session_laya import MultiSessionLayaScalperStrategy


def test_alias_warroom_laya_inferensi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Memverifikasi alias WARROOM_LAYA_INFERENSI dan WARROOM_LAYA_ENABLE."""
    # Default jika unset
    monkeypatch.delenv("WARROOM_LAYA_INFERENSI", raising=False)
    monkeypatch.delenv("WARROOM_LAYA_ENABLE", raising=False)
    assert laya_verdict.is_laya_enabled() is False

    # WARROOM_LAYA_ENABLE=1
    monkeypatch.setenv("WARROOM_LAYA_ENABLE", "1")
    assert laya_verdict.is_laya_enabled() is True

    # WARROOM_LAYA_INFERENSI=0 meng-override ENABLE=1
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    assert laya_verdict.is_laya_enabled() is False

    # WARROOM_LAYA_INFERENSI=1
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "1")
    assert laya_verdict.is_laya_enabled() is True


def test_pure_technical_mode_evaluates_criteria_when_laya_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 1: Sinyal dievaluasi saat Laya AI dinonaktifkan (WARROOM_LAYA_INFERENSI=0)."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    s = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6, max_sl_points=3.0)

    # 1. Sesi valid (LONDON), RRR >= 1.6, SL <= 3.0 -> Lolos
    layak, conf, alasan = s.evaluate_laya({
        "side": "LONG",
        "session": "LONDON",
        "rrr": 1.8,
        "risk": 2.5,
    })
    assert layak is True
    assert conf == 1.0
    assert "Mode teknis murni (WARROOM_LAYA_INFERENSI=0) — lolos filter teknis" in alasan

    # 2. Sesi tidak sah (LIBUR / WEEKEND) -> Ditolak
    layak_sesi, _, alasan_sesi = s.evaluate_laya({
        "side": "LONG",
        "session": "WEEKEND",
        "rrr": 1.8,
        "risk": 2.0,
    })
    assert layak_sesi is False
    assert "DIBLOKIR" in alasan_sesi

    # 3. RRR di bawah 1.6 -> Ditolak
    layak_rrr, _, alasan_rrr = s.evaluate_laya({
        "side": "LONG",
        "session": "ASIA",
        "rrr": 1.4,
        "risk": 2.0,
    })
    assert layak_rrr is False
    assert "DIBLOKIR" in alasan_rrr
    assert "di bawah batas minimal 1.60" in alasan_rrr

    # 4. SL melebihi toleransi maksimal 3.0 -> Ditolak
    layak_sl, _, alasan_sl = s.evaluate_laya({
        "side": "SHORT",
        "session": "NEW_YORK",
        "rrr": 2.0,
        "risk": 3.8,
    })
    assert layak_sl is False
    assert "DIBLOKIR" in alasan_sl
    assert "melebihi toleransi maksimal" in alasan_sl


def test_fallback_when_verdict_cache_not_written_yet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 2: Fallback saat Laya aktif tapi cache verdict belum tersedia."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "1")
    monkeypatch.setenv("WARROOM_LAYA_VERDICT_PATH", str(tmp_path / "nonexistent.json"))

    s = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6)
    layak, conf, alasan = s.evaluate_laya({
        "side": "LONG",
        "session": "NEW_YORK",
        "rrr": 1.8,
        "risk": 2.2,
    })
    assert layak is True
    assert conf == 1.0
    assert "Mode teknis murni" in alasan


def test_pure_technical_mode_rejects_zero_or_negative_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa risk 0.0 atau negatif diblokir demi keamanan modal."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    s = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6)

    # 1. risk = 0.0
    layak_zero, conf_zero, alasan_zero = s.evaluate_laya({
        "side": "LONG",
        "session": "LONDON",
        "rrr": 2.0,
        "risk": 0.0,
    })
    assert layak_zero is False
    assert conf_zero == 0.0
    assert "DIBLOKIR" in alasan_zero
    assert "jarak SL 0.00 tidak valid" in alasan_zero

    # 2. sl_points = 0.0 (fallback saat risk tidak diset)
    layak_sl_zero, conf_sl_zero, alasan_sl_zero = s.evaluate_laya({
        "side": "LONG",
        "session": "LONDON",
        "rrr": 2.0,
        "sl_points": 0.0,
    })
    assert layak_sl_zero is False
    assert conf_sl_zero == 0.0
    assert "DIBLOKIR" in alasan_sl_zero
    assert "jarak SL 0.00 tidak valid" in alasan_sl_zero

    # 3. negative risk
    layak_neg, conf_neg, alasan_neg = s.evaluate_laya({
        "side": "LONG",
        "session": "LONDON",
        "rrr": 2.0,
        "risk": -1.5,
    })
    assert layak_neg is False
    assert conf_neg == 0.0
    assert "DIBLOKIR" in alasan_neg


def test_pure_technical_mode_strips_session_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa string sesi dengan whitespace di awal/akhir dibersihkan dan disetujui."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    s = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6)

    layak, conf, alasan = s.evaluate_laya({
        "side": "LONG",
        "session": " LONDON ",
        "rrr": 2.0,
        "risk": 2.0,
    })
    assert layak is True
    assert conf == 1.0
    assert "lolos filter teknis" in alasan


def test_pure_technical_mode_floating_point_rrr_precision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa RRR 1.60 dari setup realistis (ATR 2.0, risk 2.2, reward 3.52)
    tidak gugur oleh presisi float.
    """
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    s = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6)

    # 3.52 / 2.2 = 1.5999999999999999
    rasio = 3.52 / 2.2
    layak, conf, alasan = s.evaluate_laya({
        "side": "LONG",
        "session": "LONDON",
        "rrr": rasio,
        "risk": 2.2,
    })
    assert layak is True
    assert conf == 1.0
    assert "lolos filter teknis" in alasan

    # Verifikasi end-to-end melalui evaluate()
    s_e2e = MultiSessionLayaScalperStrategy(enable_laya=False, min_rrr=1.6)
    s_e2e.get_current_session = lambda: "LONDON"
    market_data = {
        "price": 2650.0,
        "ema9": 2645.0,
        "ema21": 2640.0,
        "atr14": 2.0,
        "recent_high": 2655.0,
        "recent_low": 2635.0,
    }
    sig = s_e2e.evaluate(market_data)
    assert sig is not None
    assert sig["risk"] == 2.2
    assert sig["reward"] == 3.52
    assert sig["session"] == "LONDON"
