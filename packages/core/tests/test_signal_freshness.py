"""Tes: sinyal OK wajib membawa `generated_at` (R2 — penolakan sinyal basi).

EA menolak sinyal yang lebih tua dari `InpMaxSignalAgeSec`. Tanpa stempel waktu,
sinyal lama dieksekusi ke pasar yang sudah bergerak — akar drift harga yang
memperburuk R:R (insiden trade #6, 21 Okt 2026).
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from warroom_core.forex import engine


class _StrategyStub:
    """Strategi palsu yang selalu memberi sinyal LONG valid."""

    name = "Stub Strategy"
    timeframe = "5m"

    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any]:
        price = market_data["price"]
        return {
            "side": "LONG",
            "entry": price,
            "sl": round(price - 3.0, 2),
            "tp1": round(price + 5.4, 2),
            "tp2": round(price + 9.0, 2),
            "risk": 3.0,
            "reward": 5.4,
            "reason": "stub",
            "confidence": 0.9,
        }


class _RegistryStub:
    def get_active_strategy(self) -> _StrategyStub:
        return _StrategyStub()


def _candles(n: int = 60) -> list[dict[str, float]]:
    """Candle naik monoton supaya indikator terhitung wajar."""
    out = []
    for i in range(n):
        base = 4000.0 + i
        out.append(
            {
                "o": base,
                "h": base + 1.0,
                "l": base - 1.0,
                "c": base + 0.5,
                "v": 100.0,
            }
        )
    return out


@pytest.mark.asyncio
async def test_signal_ok_membawa_generated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_klines(symbol: str, interval: str, range_period: str):  # noqa: ANN001
        return _candles()

    monkeypatch.setattr(engine, "fetch_klines_direct", fake_klines)
    monkeypatch.setattr(engine, "pnp_registry", _RegistryStub())

    sebelum = int(time.time())
    hasil = await engine.generate_forex_levels(symbol="XAUUSD", mode="scalping")
    sesudah = int(time.time())

    assert hasil["status"] == "OK", hasil
    assert "generated_at" in hasil, "sinyal OK wajib punya generated_at"
    assert isinstance(hasil["generated_at"], int)
    assert sebelum <= hasil["generated_at"] <= sesudah


@pytest.mark.asyncio
async def test_generated_at_tidak_ada_saat_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """WAITING_SETUP bukan sinyal; tidak perlu stempel waktu."""

    async def fake_klines(symbol: str, interval: str, range_period: str):  # noqa: ANN001
        return _candles()

    class _NoSignal(_StrategyStub):
        def evaluate(self, market_data: dict[str, Any]) -> None:
            return None

    class _Reg:
        def get_active_strategy(self) -> _NoSignal:
            return _NoSignal()

    monkeypatch.setattr(engine, "fetch_klines_direct", fake_klines)
    monkeypatch.setattr(engine, "pnp_registry", _Reg())

    hasil = await engine.generate_forex_levels(symbol="XAUUSD", mode="scalping")
    assert hasil["status"] == "WAITING_SETUP"
    assert "generated_at" not in hasil
