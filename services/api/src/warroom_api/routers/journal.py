"""Router jurnal eksekusi lintas market.

Sumber: data lokal di server ini.
  - Forex  : telemetri MT5 (facts `mt5_snapshot`) + catatan fill `/var/lib/warroom/fills.csv`
  - Crypto : paper trader momentum (`momentum_paper.json`, `momentum_trades.csv`)

Lima endpoint menerima `market=all|forex|crypto`; sisanya khusus forex karena
hanya forex yang punya antrean order nyata (slippage, latensi, sesi).
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from warroom_api import auth
from warroom_api.routers.tencent import _fetch_tencent

router = APIRouter(
    prefix="/api/v1/journal", tags=["journal"], dependencies=[Depends(auth.current_user)]
)

MarketQ = Query("all", pattern="^(all|forex|crypto)$", description="Filter market")

# Endpoint yang mengerti filter market.
_FILTER = (
    "/forex/journal/stats",
    "/forex/journal/trades",
    "/forex/journal/edge",
    "/forex/journal/performance",
    "/forex/journal/multipair",
    "/forex/journal/scanlog",
)


async def _ambil(path: str, market: str | None = None) -> Any:
    if market is not None and path in _FILTER:
        return await _fetch_tencent(path, params={"market": market})
    return await _fetch_tencent(path)


@router.get("/stats")
async def journal_stats(market: str = MarketQ) -> dict[str, Any]:
    """Statistik jurnal per market: ekuitas, PnL, trade, win rate."""
    return await _ambil("/forex/journal/stats", market)


@router.get("/trades")
async def journal_trades(market: str = MarketQ) -> dict[str, Any]:
    """Trade tercatat dari kedua market, terbaru lebih dulu."""
    return await _ambil("/forex/journal/trades", market)


@router.get("/watchlist")
async def journal_watchlist() -> dict[str, Any]:
    """Posisi dan pending order yang sedang terbuka di terminal MT5."""
    return await _ambil("/forex/journal/watchlist")


@router.get("/edge")
async def journal_edge(market: str = MarketQ) -> dict[str, Any]:
    """Slippage dan latensi per jam, dari fill nyata."""
    return await _ambil("/forex/journal/edge", market)


@router.get("/scanlog")
async def journal_scanlog(market: str = MarketQ) -> dict[str, Any]:
    """Riwayat keputusan: forex = evaluasi EA, crypto = verdicts. Tidak dicampur."""
    return await _ambil("/forex/journal/scanlog", market)


@router.get("/performance")
async def journal_performance(market: str = MarketQ) -> dict[str, Any]:
    """Kurva ekuitas forex dari snapshot per menit."""
    return await _ambil("/forex/journal/performance", market)


@router.get("/session")
async def journal_session() -> dict[str, Any]:
    """Kondisi sesi terakhir: spread, bid/ask, posisi."""
    return await _ambil("/forex/journal/session")


@router.get("/multipair")
async def journal_multipair(market: str = MarketQ) -> dict[str, Any]:
    """Rekap per simbol dari kedua market."""
    return await _ambil("/forex/journal/multipair", market)


@router.get("/charts")
async def journal_charts() -> list[dict[str, Any]]:
    """Deret ekuitas untuk grafik."""
    raw = await _ambil("/forex/journal/charts")
    return raw if isinstance(raw, list) else []


@router.get("/symbol/{symbol}")
async def journal_symbol(symbol: str) -> dict[str, Any]:
    """Ringkasan jurnal untuk satu simbol."""
    raw = await _ambil("/forex/journal/multipair")
    pairs = raw.get("per_simbol", {}) if isinstance(raw, dict) else {}
    for nama, row in pairs.items():
        if str(nama).upper() == symbol.upper():
            return {"pair": symbol.upper(), "found": True, **row}
    return {"pair": symbol.upper(), "found": False}
