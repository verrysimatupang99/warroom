"""Tes: gerbang Laya lewat cache harus FAIL-CLOSED (R3 + isolasi model).

Regresi yang dijaga:
1. `evaluate_laya()` pernah mengembalikan `True, 0.85` saat model mati — angka itu
   tidak pernah dihitung dari data apa pun.
2. Model 421M pernah dimuat di dalam proses API: 30 detik cold start, ~1 GB RSS,
   sementara timeout WebRequest EA hanya 3 detik. Sekarang inferensi dipindahkan ke
   job terjadwal dan strategi hanya membaca berkas cache.

Setiap jalur yang tidak bisa membuktikan keamanan harus mengembalikan False.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from warroom_core.forex import laya_verdict
from warroom_core.forex.strategies.multi_session_laya import (
    MultiSessionLayaScalperStrategy,
)


@pytest.fixture()
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "laya_verdict.json"
    monkeypatch.setenv("WARROOM_LAYA_VERDICT_PATH", str(p))
    monkeypatch.setenv("WARROOM_LAYA_VERDICT_TTL_SEC", "180")
    return p


def _tulis(p: Path, **override: object) -> None:
    data = {
        "ts": int(time.time()),
        "session": "LONDON",
        "verdicts": {
            "LONG": {"choice": "EXECUTE", "confidence": 0.91},
            "SHORT": {"choice": "SKIP", "confidence": 0.20},
        },
    }
    data.update(override)
    p.write_text(json.dumps(data), encoding="utf-8")


def test_tanpa_berkas_memblokir(cache: Path) -> None:
    layak, keyakinan, alasan = laya_verdict.ambil("LONG", "LONDON")
    assert layak is False
    assert keyakinan == 0.0
    assert "belum tersedia" in alasan
    assert "DIBLOKIR" in alasan


def test_verdict_basi_memblokir(cache: Path) -> None:
    _tulis(cache, ts=int(time.time()) - 600)
    layak, _, alasan = laya_verdict.ambil("LONG", "LONDON")
    assert layak is False
    assert "BASI" in alasan


def test_sesi_tidak_cocok_memblokir(cache: Path) -> None:
    _tulis(cache, session="ASIA")
    layak, _, alasan = laya_verdict.ambil("LONG", "LONDON")
    assert layak is False
    assert "sesi" in alasan.lower()


def test_arah_tidak_ada_di_cache_memblokir(cache: Path) -> None:
    _tulis(cache, verdicts={"LONG": {"choice": "EXECUTE", "confidence": 0.9}})
    layak, _, alasan = laya_verdict.ambil("SHORT", "LONDON")
    assert layak is False
    assert "tidak memuat arah" in alasan


def test_verdict_tak_dikenal_memblokir(cache: Path) -> None:
    _tulis(cache, verdicts={"LONG": {"choice": "MUNGKIN", "confidence": 0.9}})
    layak, _, alasan = laya_verdict.ambil("LONG", "LONDON")
    assert layak is False
    assert "tidak dikenali" in alasan


def test_skip_memblokir(cache: Path) -> None:
    _tulis(cache)
    layak, keyakinan, alasan = laya_verdict.ambil("SHORT", "LONDON")
    assert layak is False
    assert keyakinan == pytest.approx(0.20)
    assert "SKIP" in alasan


def test_execute_segar_lolos(cache: Path) -> None:
    _tulis(cache)
    layak, keyakinan, alasan = laya_verdict.ambil("LONG", "LONDON")
    assert layak is True
    assert keyakinan == pytest.approx(0.91)
    assert "EXECUTE" in alasan


def test_keyakinan_di_bawah_ambang_memblokir(cache: Path) -> None:
    _tulis(cache, verdicts={"LONG": {"choice": "EXECUTE", "confidence": 0.40}})
    layak, keyakinan, _ = laya_verdict.ambil("LONG", "LONDON")
    assert layak is False
    assert keyakinan == pytest.approx(0.40)


def test_strategi_memakai_cache_bukan_model(cache: Path) -> None:
    """Strategi tidak boleh memuat model; ia hanya membaca cache."""
    _tulis(cache)
    s = MultiSessionLayaScalperStrategy(enable_laya=True, laya_min_confidence=0.60)

    assert s._evaluator is None, "strategi tidak boleh menyimpan evaluator model"
    assert s._laya_loaded is False

    layak, keyakinan, alasan = s.evaluate_laya({"side": "LONG", "session": "LONDON"})
    assert layak is True
    assert keyakinan == pytest.approx(0.91)
    assert alasan.startswith("Laya EXECUTE")


def test_strategi_tanpa_cache_memblokir(cache: Path) -> None:
    s = MultiSessionLayaScalperStrategy(enable_laya=True)
    layak, keyakinan, alasan = s.evaluate_laya({"side": "LONG", "session": "LONDON"})
    assert layak is False
    assert keyakinan == 0.0
    assert "DIBLOKIR" in alasan


def test_laya_dinonaktifkan_memblokir(cache: Path) -> None:
    s = MultiSessionLayaScalperStrategy(enable_laya=False)
    layak, _, alasan = s.evaluate_laya({"side": "LONG", "session": "LONDON"})
    assert layak is False
    assert "dinonaktifkan" in alasan
