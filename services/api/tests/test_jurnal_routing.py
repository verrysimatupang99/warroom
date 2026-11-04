"""Tes routing jurnal: crypto dilayani lokal, forex tetap ke Tencent.

Kelas bug yang dicegah: `_ambil` meneruskan SEMUA market ke Tencent, sehingga
`market=crypto` menjawab dari layanan forex dan 106 trade paper crypto di
`crypto_equity.jsonl` tidak pernah tampil di UI (temuan 4 Nov 2026).
"""

import asyncio
from typing import Any

import pytest
from warroom_api.routers import journal


def _jl(*a: Any, **k: Any) -> Any:
    return asyncio.run(journal._ambil(*a, **k))


@pytest.fixture
def jejak(monkeypatch):
    """Catat siapa yang dipanggil dan kembalikan bentuk respons yang wajar."""
    calls: list[tuple[Any, ...]] = []

    async def _fake_tencent(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append(("tencent", path, params))
        return {"closed": [{"iso": "2026-11-01 00:00:00", "symbol": "XAUUSD"}],
                "entries": [], "n": 1, "sumber": "tencent"}

    async def _fake_lokal(market: str = "all") -> dict[str, Any]:
        calls.append(("lokal", market))
        return {"closed": [{"iso": "2026-11-04 17:30:08", "symbol": "CRVUSDT"}],
                "entries": [], "n": 1, "sumber": "lokal"}

    monkeypatch.setattr(journal, "_fetch_tencent", _fake_tencent)
    monkeypatch.setattr(
        journal, "_LOKAL", {"/forex/journal/trades": _fake_lokal}
    )
    return calls


def test_crypto_dilayani_lokal_bukan_tencent(jejak):
    hasil = _jl("/forex/journal/trades", "crypto")
    assert [c[0] for c in jejak] == ["lokal"]
    assert jejak[0][1] == "crypto"
    assert hasil["sumber"] == "lokal"


def test_forex_tetap_ke_tencent(jejak):
    hasil = _jl("/forex/journal/trades", "forex")
    assert [c[0] for c in jejak] == ["tencent"]
    assert jejak[0][2]["market"] == "forex"
    assert hasil["sumber"] == "tencent"


def test_all_menggabung_forex_dan_crypto(jejak):
    hasil = _jl("/forex/journal/trades", "all")
    assert [c[0] for c in jejak] == ["tencent", "lokal"]
    # Urut terbaru lebih dulu, dan `n` dihitung dari hasil gabungan.
    assert hasil["n"] == 2
    assert [r["symbol"] for r in hasil["closed"]] == ["CRVUSDT", "XAUUSD"]
    assert "tencent" in hasil["sumber"] and "lokal" in hasil["sumber"]


def test_all_aman_bila_salah_satu_bukan_dict(monkeypatch):
    async def _fake_str(path: str, params: dict[str, Any] | None = None) -> Any:
        return "bukan dict"

    async def _fake_lokal(market: str = "all") -> dict[str, Any]:
        return {"closed": [], "n": 0}

    monkeypatch.setattr(journal, "_fetch_tencent", _fake_str)
    monkeypatch.setattr(journal, "_LOKAL", {"/forex/journal/trades": _fake_lokal})
    # Tidak boleh melempar; kembalikan respons forex apa adanya.
    assert _jl("/forex/journal/trades", "all") == "bukan dict"


def test_path_tak_dikenal_tetap_ke_tencent(jejak):
    _jl("/forex/journal/watchlist", "crypto")
    assert [c[0] for c in jejak] == ["tencent"]
