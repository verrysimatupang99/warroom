"""Tes R7: `rrr_min` harus jadi penjaga keras, bukan sekadar pengali reward.

Sebelumnya `rrr_min` hanya dipakai untuk MENGHITUNG `reward = risk * rrr_min`.
Bila pembulatan atau clamp menghasilkan rasio di bawah minimum, sinyal tetap
dikirim ke EA. Sekarang rasio diverifikasi ulang dan sinyal dibatalkan.

Selain itu urutan level divalidasi: LONG wajib sl < entry < tp1 < tp2 dan SHORT
wajib sl > entry > tp1 > tp2, supaya kesalahan tanda tidak pernah sampai ke EA.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from warroom_core.forex.strategies.multi_session_laya import (
    MultiSessionLayaScalperStrategy,
)


@pytest.fixture()
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "verdict.json"
    monkeypatch.setenv("WARROOM_LAYA_VERDICT_PATH", str(p))
    monkeypatch.setenv("WARROOM_LAYA_VERDICT_TTL_SEC", "600")
    p.write_text(
        json.dumps(
            {
                "ts": int(time.time()),
                "session": "ASIA",
                "verdicts": {
                    "LONG": {"choice": "EXECUTE", "confidence": 0.95},
                    "SHORT": {"choice": "EXECUTE", "confidence": 0.95},
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def _candles(n: int = 20, harga: float = 4000.0) -> list[dict[str, float]]:
    return [
        {"high": harga + 1.0, "low": harga - 1.0, "open": harga, "close": harga}
        for _ in range(n)
    ]


def _market(price: float, ema9: float) -> dict[str, Any]:
    return {
        "price": price,
        "ema9": ema9,
        "ema21": ema9,
        "atr14": 1.0,
        "candles": _candles(),
    }


def _strategi(**kwargs: Any) -> MultiSessionLayaScalperStrategy:
    s = MultiSessionLayaScalperStrategy(min_rrr=1.8, **kwargs)
    # Paksa sesi ASIA agar deterministik (tidak bergantung jam saat tes jalan)
    s.get_current_session = lambda: "ASIA"  # type: ignore[method-assign]
    return s


def test_rasio_minimum_terpenuhi_dan_urutan_benar(cache: Path) -> None:
    s = _strategi()
    # price jauh di atas ema9 -> skenario Asia Range Top Reversal -> SHORT
    sinyal = s.evaluate(_market(price=4000.0, ema9=3990.0))

    assert sinyal is not None, s.last_block_reason
    assert sinyal["side"] == "SHORT"

    rasio = sinyal["reward"] / sinyal["risk"]
    assert rasio + 1e-9 >= 1.8, f"R:R {rasio} di bawah minimum"

    # Invarian arah SHORT
    assert sinyal["sl"] > sinyal["entry"] > sinyal["tp1"] > sinyal["tp2"]


def test_risk_tidak_valid_membatalkan_sinyal(cache: Path) -> None:
    # max_sl_points sangat kecil -> risk terbulatkan jadi 0.00 -> harus ditolak
    s = _strategi(max_sl_points=0.001)
    sinyal = s.evaluate(_market(price=4000.0, ema9=3990.0))

    assert sinyal is None
    assert s.last_block_reason is not None
    assert "tidak valid" in s.last_block_reason


def test_alasan_blokir_dibersihkan_saat_lolos(cache: Path) -> None:
    s = _strategi()
    s.last_block_reason = "sisa blokir lama"
    sinyal = s.evaluate(_market(price=4000.0, ema9=3990.0))

    assert sinyal is not None
    assert s.last_block_reason is None
