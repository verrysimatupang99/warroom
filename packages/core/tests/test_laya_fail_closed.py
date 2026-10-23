"""Tes: gerbang Laya harus FAIL-CLOSED (R3).

Regresi yang dijaga: `evaluate_laya()` pernah mengembalikan `True, 0.85` ketika
model tidak tersedia. Angka 0.85 itu tidak pernah dihitung dari data apa pun,
sehingga seluruh nilai "middleware Laya" menjadi ilusi — sinyal tetap dieksekusi
dan tidak ada yang tahu gerbangnya sedang mati.

Aturan yang ditegakkan di sini:
- model tidak termuat / dimatikan  -> BLOKIR
- verdict tidak dikenali           -> BLOKIR
- inferensi melempar exception     -> BLOKIR
- EXECUTE dengan keyakinan rendah  -> BLOKIR
"""

from __future__ import annotations

from typing import Any

import pytest
from warroom_core.forex.strategies.multi_session_laya import (
    MultiSessionLayaScalperStrategy,
)

STATE: dict[str, Any] = {"side": "LONG", "session": "LONDON", "price": 4000.0}


def _strategi_tanpa_model() -> MultiSessionLayaScalperStrategy:
    """Strategi dengan Laya dipaksa mati, tanpa memuat model 421M."""
    s = MultiSessionLayaScalperStrategy(enable_laya=False)
    s._laya_loaded = False
    s._evaluator = None
    return s


def test_model_tidak_tersedia_memblokir() -> None:
    layak, keyakinan, alasan = _strategi_tanpa_model().evaluate_laya(STATE)

    assert layak is False, "model mati TIDAK boleh meloloskan sinyal"
    assert keyakinan == 0.0, "keyakinan harus 0.0, bukan angka karangan"
    assert "TIDAK TERSEDIA" in alasan
    assert "DIBLOKIR" in alasan


def test_evaluator_none_memblokir() -> None:
    s = MultiSessionLayaScalperStrategy(enable_laya=True)
    s._evaluator = None
    s._laya_loaded = True  # kontradiksi sengaja: evaluator tetap None

    layak, keyakinan, alasan = s.evaluate_laya(STATE)
    assert layak is False
    assert keyakinan == 0.0
    assert "DIBLOKIR" in alasan


class _EvaluatorError:
    def invoke(self, _state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("model meledak")


class _EvaluatorTanpaVerdict:
    def invoke(self, _state: dict[str, Any]) -> dict[str, Any]:
        return {"verdict": {"choice": "MUNGKIN", "probabilities": {"EXECUTE": 0.9}}}


class _EvaluatorYakin:
    def invoke(self, _state: dict[str, Any]) -> dict[str, Any]:
        return {"verdict": {"choice": "EXECUTE", "probabilities": {"EXECUTE": 0.93}}}


class _EvaluatorRagu:
    def invoke(self, _state: dict[str, Any]) -> dict[str, Any]:
        return {"verdict": {"choice": "EXECUTE", "probabilities": {"EXECUTE": 0.41}}}


def _dengan_evaluator(ev: Any) -> MultiSessionLayaScalperStrategy:
    s = MultiSessionLayaScalperStrategy(enable_laya=True, laya_min_confidence=0.60)
    s._evaluator = ev
    s._laya_loaded = True
    return s


def test_inferensi_error_memblokir() -> None:
    layak, keyakinan, alasan = _dengan_evaluator(_EvaluatorError()).evaluate_laya(STATE)
    assert layak is False
    assert keyakinan == 0.0
    assert "ERROR" in alasan


def test_verdict_tidak_dikenali_memblokir() -> None:
    layak, _, alasan = _dengan_evaluator(_EvaluatorTanpaVerdict()).evaluate_laya(STATE)
    assert layak is False
    assert "tidak dikenali" in alasan


def test_execute_dengan_keyakinan_tinggi_lolos() -> None:
    layak, keyakinan, alasan = _dengan_evaluator(_EvaluatorYakin()).evaluate_laya(STATE)
    assert layak is True
    assert keyakinan == pytest.approx(0.93)
    assert alasan.startswith("Laya EXECUTE")


def test_execute_dengan_keyakinan_rendah_memblokir() -> None:
    layak, keyakinan, _ = _dengan_evaluator(_EvaluatorRagu()).evaluate_laya(STATE)
    assert layak is False
    assert keyakinan == pytest.approx(0.41)
