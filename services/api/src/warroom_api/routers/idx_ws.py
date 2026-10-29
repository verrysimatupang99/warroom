"""Endpoint running-trade IDX (WebSocket)."""

from typing import Any

from fastapi import APIRouter, Depends

from warroom_api import auth, idx_ws

router = APIRouter(
    prefix="/api/v1/idx-ws", tags=["idx"], dependencies=[Depends(auth.current_user)]
)


@router.get("/running-trade")
async def running_trade() -> dict[str, Any]:
    """Transaksi terakhir + top 5 teraktif dari stream. Tanpa kuota request."""
    snap = idx_ws.snapshot()
    return {"sumber": "idx-ws:running-trade", "status_pendengar": idx_ws.status_benang(), **snap}


@router.post("/mulai")
async def mulai() -> dict[str, Any]:
    """Nyalakan pendengar latar. Aman dipanggil berulang."""
    baru = idx_ws.mulai_latar()
    return {
        "sumber": "idx-ws",
        "baru_dinyalakan": baru,
        "status_pendengar": idx_ws.status_benang(),
    }
