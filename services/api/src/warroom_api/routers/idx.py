"""Router proxy read-only ke Hermes Data API di node MiniMax (Tencent).

Sumber tunggal intelijen pasar Indonesia (IDX/IHSG): MiniMax sudah menjalankan
scanner IDX, ledger sinyal, kurva equity, dan aliran dana — semua dengan
akses database mode=ro. War Room TIDAK menghitung ulang angka sendiri
(ADR-005: angka hanya dari facts), jadi router ini meneruskan apa adanya.

Jalur: node MiniMax via Tailscale (`http://100.126.10.74:8790`) — sama seperti
router `tencent.py`. Tidak ada kredensial yang dibuka di sisi War Room.
"""

from typing import Any

from fastapi import APIRouter, Query

from warroom_api.routers.tencent import TIMEOUT_S_LARGE, _fetch_tencent

router = APIRouter(prefix="/api/v1/idx", tags=["idx"])


@router.get("/stats")
async def idx_stats() -> dict[str, Any]:
    """Agregat run scanner, ticker terlacak, dan jumlah sinyal."""
    return await _fetch_tencent("/idx/stats")


@router.get("/signals")
async def idx_signals(
    limit: int = Query(50, ge=1, le=500),
    preset: str | None = Query(None, description="Filter preset pemicu, contoh: FAKTOR"),
) -> dict[str, Any]:
    """Daftar sinyal hasil scan IDX, opsional disaring per preset."""
    params: dict[str, Any] = {"limit": limit}
    if preset:
        params["preset"] = preset
    return await _fetch_tencent("/idx/signals", params=params)


@router.get("/market")
async def idx_market() -> dict[str, Any]:
    """Snapshot market IDX per fase (pra/regular/post)."""
    return await _fetch_tencent("/idx/market")


@router.get("/flow")
async def idx_flow(
    ticker: str = Query(..., description="Ticker IDX, contoh: BBCA"),
) -> dict[str, Any]:
    """Aliran dana per ticker."""
    return await _fetch_tencent("/idx/flow", params={"ticker": ticker}, timeout_s=TIMEOUT_S_LARGE)


@router.get("/ledger")
async def idx_ledger() -> dict[str, Any]:
    """Metrik ledger sinyal: filled/pending/closed, win rate, expectancy, PF."""
    return await _fetch_tencent("/idx/ledger")


@router.get("/equity")
async def idx_equity() -> dict[str, Any]:
    """Kurva equity dan metrik risiko (R, max drawdown)."""
    return await _fetch_tencent("/idx/equity")


@router.get("/feed")
async def idx_feed() -> dict[str, Any]:
    """Feed ringkas sinyal + metadata kebijakan sumber."""
    return await _fetch_tencent("/idx/feed")


@router.get("/news")
async def idx_news() -> dict[str, Any]:
    """Berita IDX relevan."""
    return await _fetch_tencent("/idx/news")


@router.get("/scanners")
async def idx_scanners() -> dict[str, Any]:
    """Status scanner aktif (FCA/ARA) dan hasil pindaiannya."""
    return await _fetch_tencent("/idx/scanners")


@router.get("/official")
async def idx_official() -> dict[str, Any]:
    """Data resmi: daftar indeks, top volume, dan data TradingView."""
    return await _fetch_tencent("/idx/official")


@router.get("/latest/{job_id}")
async def idx_latest(job_id: str) -> dict[str, Any]:
    """Sinyal terakhir dari satu job scan."""
    return await _fetch_tencent(f"/idx/latest/{job_id}")


@router.get("/history/{job_id}")
async def idx_history(job_id: str) -> dict[str, Any]:
    """Riwayat sinyal dari satu job scan."""
    return await _fetch_tencent(f"/idx/history/{job_id}")
