"""Unit tests untuk BE-01 / US-01: Pure Technical Mode Fallback (WARROOM_LAYA_INFERENSI)."""

from __future__ import annotations

import os
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
