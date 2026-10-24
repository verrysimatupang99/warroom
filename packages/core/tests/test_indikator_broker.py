"""Tes: engine memakai snapshot BROKER lebih dulu, Yahoo hanya cadangan.

Alasan: engine semula mengambil indikator dari Yahoo `GC=F` (kontrak berjangka
emas), sedangkan EA mengeksekusi `XAUUSDm` (spot). Selisih harga terukur $11-12
sementara jarak SL strategi hanya ~$2,5. Snapshot broker kini tersedia di
telemetri EA dan dipakai bila segar.
"""

from __future__ import annotations

from typing import Any

import pytest
from warroom_core.forex import engine


class _StrategyStub:
    name = "Stub"
    timeframe = "5m"

    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any]:
        p = market_data["price"]
        return {
            "side": "LONG",
            "entry": p,
            "sl": round(p - 3.0, 2),
            "tp1": round(p + 5.4, 2),
            "tp2": round(p + 9.0, 2),
            "risk": 3.0,
            "reward": 5.4,
        }


class _RegistryStub:
    def get_active_strategy(self) -> _StrategyStub:
        return _StrategyStub()


SNAPSHOT = {
    "bid": 3996.057,
    "ask": 3996.317,
    "atr_m5": 2.452,
    "ema9_m5": 3996.104,
    "ema21_m5": 3996.771,
    "high_12": 3999.978,
    "low_12": 3992.074,
}


def _larang_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bila Yahoo dipanggil, tes harus gagal — bukan diam-diam lolos."""

    async def boom(*a: Any, **k: Any) -> list[dict[str, Any]]:
        raise AssertionError("Yahoo tidak boleh dipanggil saat snapshot broker tersedia")

    monkeypatch.setattr(engine, "fetch_klines_direct", boom)


@pytest.mark.asyncio
async def test_pakai_snapshot_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    _larang_yahoo(monkeypatch)
    monkeypatch.setattr(engine, "pnp_registry", _RegistryStub())

    hasil = await engine.generate_forex_levels(symbol="XAUUSD", snapshot=SNAPSHOT)

    assert hasil["status"] == "OK", hasil
    assert hasil["indicator_source"] == "broker:mt5"
    assert hasil["price"] == pytest.approx(3996.057)
    assert hasil["atr"] == pytest.approx(2.452)
    assert hasil["side"] == "LONG"


@pytest.mark.asyncio
async def test_recent_high_low_broker_dipakai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy harus menerima recent_high/low walau daftar candle kosong."""
    _larang_yahoo(monkeypatch)
    monkeypatch.setattr(engine, "pnp_registry", _RegistryStub())

    ind = engine._indikator_dari_snapshot(SNAPSHOT)
    assert ind is not None
    assert ind["recent_high"] == pytest.approx(3999.978)
    assert ind["recent_low"] == pytest.approx(3992.074)


@pytest.mark.parametrize("hilang", ["bid", "atr_m5", "ema9_m5", "high_12", "low_12"])
def test_snapshot_tidak_lengkap_ditolak(hilang: str) -> None:
    snap = dict(SNAPSHOT)
    snap.pop(hilang)
    assert engine._indikator_dari_snapshot(snap) is None


def test_snapshot_nilai_tidak_wajar_ditolak() -> None:
    tanpa_bid = {k: v for k, v in SNAPSHOT.items() if k != "bid"}
    assert engine._indikator_dari_snapshot({**tanpa_bid, "bid": 0}) is None

    tanpa_atr = {k: v for k, v in SNAPSHOT.items() if k != "atr_m5"}
    assert engine._indikator_dari_snapshot({**tanpa_atr, "atr_m5": -1}) is None


@pytest.mark.asyncio
async def test_tanpa_snapshot_tetap_pakai_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    dipanggil = {"n": 0}

    async def fake_klines(*a: Any, **k: Any) -> list[dict[str, float]]:
        dipanggil["n"] += 1
        return [
            {"o": 4000 + i, "h": 4001 + i, "l": 3999 + i, "c": 4000.5 + i, "v": 10}
            for i in range(60)
        ]

    monkeypatch.setattr(engine, "fetch_klines_direct", fake_klines)
    monkeypatch.setattr(engine, "pnp_registry", _RegistryStub())

    hasil = await engine.generate_forex_levels(symbol="XAUUSD", snapshot=None)

    assert dipanggil["n"] == 1
    assert hasil["indicator_source"] == "yahoo:GC=F"
