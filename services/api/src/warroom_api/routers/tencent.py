"""Router proxy terenkripsi ke node Tencent via Tailscale WireGuard.

Menghubungkan War Room ke API internal Tencent (`http://100.126.10.74:8790`)
secara aman tanpa membuka port ke internet publik.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/api/v1/tencent", tags=["tencent"])
log = logging.getLogger("warroom_api.tencent")

TENCENT_BASE = "http://100.126.10.74:8790"
TIMEOUT_S = 6.0


async def _fetch_tencent(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{TENCENT_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Tencent API error: {resp.text[:200]}")
            return resp.json()
    except httpx.RequestError as exc:
        log.warning("Gagal koneksi ke Tencent Tailscale (%s): %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Tencent node via Tailscale unreachable (100.126.10.74:8790): {type(exc).__name__}",
        ) from exc


@router.get("/health")
async def tencent_health() -> dict[str, Any]:
    """Cek koneksi Tailscale WireGuard ke daemon Tencent."""
    return await _fetch_tencent("/health")


@router.get("/universe")
async def tencent_universe() -> dict[str, Any]:
    """Daftar universe koin crypto aktif yang dipantau Tencent node."""
    return await _fetch_tencent("/crypto/universe")


@router.get("/crypto/levels")
async def tencent_crypto_levels(
    symbol: str = Query(..., description="Contoh: BTCUSDT, SOLUSDT"),
    play: str = Query("scalping", description="scalping atau swing"),
) -> dict[str, Any]:
    """Hitungan level entry, stop loss, target, dan verdict aturan dari Tencent."""
    return await _fetch_tencent("/crypto/levels", params={"symbol": symbol, "play": play})


@router.get("/forex/levels")
async def tencent_forex_levels(
    symbol: str = Query("XAUUSD", description="Contoh: XAUUSD"),
) -> dict[str, Any]:
    """Hitungan level entry, stop loss, dan SR zone Gold/Forex dari Tencent."""
    return await _fetch_tencent("/forex/levels", params={"symbol": symbol})


@router.get("/forex/dxy")
async def tencent_forex_dxy() -> dict[str, Any]:
    """Perubahan indeks dolar DXY langsung dari TradingView feed Tencent."""
    return await _fetch_tencent("/forex/dxy")


@router.get("/ticker")
async def tencent_crypto_ticker(symbol: str = Query("BTCUSDT")) -> dict[str, Any]:
    """Ticker harga real-time 24 jam dari Binance via Tencent."""
    return await _fetch_tencent("/crypto/ticker", params={"symbol": symbol})


@router.get("/klines")
async def tencent_klines(
    market: str = Query("crypto", description="crypto atau forex"),
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1h"),
    limit: int = Query(20, ge=10, le=200),
) -> dict[str, Any]:
    """Tarik data candle OHLCV langsung dari feed Tencent."""
    path = f"/{market}/klines"
    return await _fetch_tencent(path, params={"symbol": symbol, "interval": interval, "limit": limit})
