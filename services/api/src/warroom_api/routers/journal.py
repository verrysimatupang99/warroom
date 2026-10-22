"""Router proxy read-only ke Forex Journal di node MiniMax (Tencent).

Journal XAUUSD/NAS100 di node MiniMax sudah lengkap: statistik, trade
open/closed, watchlist, edge per sesi, scan log alasan sinyal ditolak,
performa, sesi market, multi-pair, dan daftar chart.

War Room tidak menghitung ulang angka jurnal (ADR-005). Router ini meneruskan
apa adanya lewat Tailscale, sama seperti `tencent.py` dan `idx.py`.
"""

from typing import Any

from fastapi import APIRouter

from warroom_api.routers.tencent import _fetch_tencent

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


@router.get("/stats")
async def journal_stats() -> dict[str, Any]:
    """Statistik jurnal: jumlah sinyal, closed/open, win rate."""
    return await _fetch_tencent("/forex/journal/stats")


@router.get("/trades")
async def journal_trades() -> dict[str, Any]:
    """Trade open dan closed dari jurnal."""
    return await _fetch_tencent("/forex/journal/trades")


@router.get("/watchlist")
async def journal_watchlist() -> dict[str, Any]:
    """Watchlist zone aktif beserta usia dan status basi."""
    return await _fetch_tencent("/forex/journal/watchlist")


@router.get("/edge")
async def journal_edge() -> dict[str, Any]:
    """Edge per sesi, excursion, dan hasil backtest jurnal."""
    return await _fetch_tencent("/forex/journal/edge")


@router.get("/scanlog")
async def journal_scanlog() -> dict[str, Any]:
    """Alasan sinyal ditolak (gate reject, blackout, ATR tipis, dsb)."""
    return await _fetch_tencent("/forex/journal/scanlog")


@router.get("/performance")
async def journal_performance() -> dict[str, Any]:
    """Performa per pair beserta konversi R."""
    return await _fetch_tencent("/forex/journal/performance")


@router.get("/session")
async def journal_session() -> dict[str, Any]:
    """Sesi market aktif, killzone, dan jadwal run berikutnya."""
    return await _fetch_tencent("/forex/journal/session")


@router.get("/multipair")
async def journal_multipair() -> dict[str, Any]:
    """Snapshot multi-pair (XAUUSD, NAS100) beserta entry aktif."""
    return await _fetch_tencent("/forex/journal/multipair")


@router.get("/charts")
async def journal_charts() -> list[dict[str, Any]]:
    """Daftar chart jurnal yang tersedia di node MiniMax."""
    raw = await _fetch_tencent("/forex/journal/charts")
    return raw if isinstance(raw, list) else []


@router.get("/symbol/{symbol}")
async def journal_symbol(symbol: str) -> dict[str, Any]:
    """Ringkasan jurnal untuk satu pair."""
    raw = await _fetch_tencent("/forex/journal/performance")
    pairs = raw.get("pairs", []) if isinstance(raw, dict) else []
    for row in pairs:
        if isinstance(row, dict) and row.get("pair", "").upper() == symbol.upper():
            return row
    return {"pair": symbol.upper(), "found": False}
