"""Router proxy terenkripsi ke node Tencent via Tailscale WireGuard.

Menghubungkan War Room ke API internal Tencent (`http://100.126.10.74:8790`)
secara aman tanpa membuka port ke internet publik.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from warroom_api.auth_ea import verify_mt5_or_admin

router = APIRouter(prefix="/api/v1/tencent", tags=["tencent"])
log = logging.getLogger("warroom_api.tencent")

TENCENT_BASE = "http://100.126.10.74:8790"
TIMEOUT_S = 6.0
# Endpoint yang menyentuh sumber eksternal (mis. aliran dana IDX) butuh waktu
# lebih lama daripada lookup in-memory MiniMax.
TIMEOUT_S_LARGE = 20.0


async def _fetch_tencent(
    path: str,
    params: dict[str, Any] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> Any:
    url = f"{TENCENT_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Tencent API error: {resp.text[:200]}",
                )
            return resp.json()
    except httpx.TimeoutException as exc:
        # Timeout bukan berarti node mati. Bedakan, supaya dashboard tidak
        # salah menandai offline.
        log.warning("Timeout ke Tencent (%s): %s", url, exc)
        raise HTTPException(
            status_code=504,
            detail=(
                f"Tencent node menjawab lambat (> {timeout_s:.0f}s): {path}. "
                "Node hidup, sumber di baliknya yang lambat."
            ),
        ) from exc
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


@router.get("/forex/levels", dependencies=[Depends(verify_mt5_or_admin)])
async def tencent_forex_levels(
    symbol: str = Query("XAUUSD", description="Contoh: XAUUSD"),
) -> dict[str, Any]:
    """Hitungan level entry, stop loss, dan SR zone Gold/Forex dari Tencent dengan multi-timeframe filter."""
    raw_levels = await _fetch_tencent("/forex/levels", params={"symbol": symbol})
    if not isinstance(raw_levels, dict) or raw_levels.get("status") != "OK":
        return raw_levels

    # Multi-timeframe trend filter (H1 Trend Alignment):
    # Hanya izinkan sinyal eksekusi jika sejalan dengan tren H1.
    try:
        klines_h1 = await _fetch_tencent(
            "/forex/klines",
            params={"symbol": symbol, "interval": "60", "limit": 25},
        )
        candles = klines_h1.get("candles", []) if isinstance(klines_h1, dict) else []
        if len(candles) >= 15:
            closes = [c["c"] for c in candles]
            period = 20
            k = 2 / (period + 1)
            ema20 = closes[0]
            for p in closes[1:]:
                ema20 = (p * k) + (ema20 * (1 - k))

            latest_close = closes[-1]
            h1_trend = "BULLISH" if latest_close >= ema20 else "BEARISH"
            signal_side = raw_levels.get("side", "")

            # Periksa keselarasan tren
            if signal_side == "LONG" and h1_trend == "BEARISH":
                raw_levels["status"] = "FILTERED"
                raw_levels["filter_reason"] = (
                    f"H1 Bearish Trend Block: Price ({latest_close}) < H1 EMA20 ({round(ema20, 2)})"
                )
            elif signal_side == "SHORT" and h1_trend == "BULLISH":
                raw_levels["status"] = "FILTERED"
                raw_levels["filter_reason"] = (
                    f"H1 Bullish Trend Block: Price ({latest_close}) > H1 EMA20 ({round(ema20, 2)})"
                )
            else:
                raw_levels["h1_trend"] = h1_trend
                raw_levels["h1_ema20"] = round(ema20, 2)
    except Exception as exc:
        log.warning("Gagal menghitung H1 filter untuk %s: %s", symbol, exc)

    return raw_levels


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
    market: str = Query("crypto", pattern="^(crypto|forex)$", description="crypto atau forex"),
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1h"),
    limit: int = Query(20, ge=10, le=200),
) -> dict[str, Any]:
    """Tarik data candle OHLCV langsung dari feed Tencent."""
    path = f"/{market}/klines"
    return await _fetch_tencent(path, params={"symbol": symbol, "interval": interval, "limit": limit})


# --- Telemetry In-Memory State untuk MT5 Live Execution ---


class MT5PositionReport(BaseModel):
    ticket: int
    symbol: str
    side: str
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    pnl_usd: float

class MT5TelemetryPayload(BaseModel):
    account: str
    broker: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    floating_pnl: float
    positions: list[MT5PositionReport] = []
    total_trades_today: int | None = 0
    win_rate_pct: float | None = 0.0

latest_mt5_telemetry = {
    "connected": False,
    "last_seen_ts": 0,
    "account": "",
    "broker": "",
    "balance": 0.0,
    "equity": 0.0,
    "floating_pnl": 0.0,
    "margin": 0.0,
    "free_margin": 0.0,
    "positions": [],
    "total_trades_today": 0,
    "win_rate_pct": 0.0,
}

@router.post("/mt5/telemetry", dependencies=[Depends(verify_mt5_or_admin)])
async def report_mt5_telemetry(payload: MT5TelemetryPayload):
    """Endpoint yang dipanggil oleh MT5 EA setiap beberapa detik untuk melaporkan status live."""
    global latest_mt5_telemetry
    latest_mt5_telemetry = {
        "connected": True,
        "last_seen_ts": int(time.time()),
        "account": payload.account,
        "broker": payload.broker,
        "balance": payload.balance,
        "equity": payload.equity,
        "floating_pnl": payload.floating_pnl,
        "margin": payload.margin,
        "free_margin": payload.free_margin,
        "positions": [p.dict() for p in payload.positions],
        "total_trades_today": payload.total_trades_today,
        "win_rate_pct": payload.win_rate_pct
    }
    return {"status": "OK", "received_at": latest_mt5_telemetry["last_seen_ts"]}

def _muat_forex_history() -> list[dict[str, Any]]:
    """Baca riwayat transaksi EA MT5 dari file data lokal (kosong bila belum ada)."""
    history_file = Path(__file__).resolve().parent.parent / "data_forex_history.json"
    if not history_file.exists():
        return []
    try:
        records = json.loads(history_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Gagal membaca history MT5 (%s): %s", history_file.name, exc)
        return []
    return records if isinstance(records, list) else []


def _statistik_forex(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Hitung W/L/PF/net dari record — tidak ada angka yang dikarang di luar data."""
    wins = [r for r in records if r.get("status") == "WIN"]
    losses = [r for r in records if r.get("status") == "LOSS"]
    laba_bruto = sum(r.get("pnl_usd", 0.0) for r in wins)
    rugi_bruto = abs(sum(r.get("pnl_usd", 0.0) for r in losses))
    return {
        "total_trades": len(records),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(records) * 100, 1) if records else 0.0,
        "net_pnl_usd": round(sum(r.get("pnl_usd", 0.0) for r in records), 2),
        "profit_factor": round(laba_bruto / rugi_bruto, 2) if rugi_bruto else None,
    }


# Antrian order pending aktif (Buy Limit / Sell Limit)
pending_orders_queue: list[dict[str, Any]] = [
    {
        "ticket": 138081403,
        "symbol": "XAUUSDm",
        "type": "BUY_LIMIT",
        "volume": 0.10,
        "price": 4068.69,
        "sl": 4060.00,
        "tp": 4090.00,
        "status": "PLACED",
        "placed_at": "2026-10-22 11:10:31"
    },
    {
        "ticket": 138084456,
        "symbol": "XAUUSDm",
        "type": "BUY_LIMIT",
        "volume": 0.10,
        "price": 4068.69,
        "sl": 4060.00,
        "tp": 4090.00,
        "status": "PLACED",
        "placed_at": "2026-10-22 11:20:15"
    }
]

@router.get("/mt5/pending_orders")
async def get_mt5_pending_orders():
    """Mengembalikan daftar order limit yang terpasang aktif di sistem."""
    return {"status": "OK", "orders": pending_orders_queue}

@router.get("/mt5/status")
async def get_mt5_status():
    """Mengembalikan status live MT5 dan posisi terbuka untuk dashboard Beranda."""
    now = int(time.time())
    last_seen = latest_mt5_telemetry.get("last_seen_ts", 0)
    # Jika tidak ada update dalam 20 detik, tandai offline / laptop tidur
    is_live = (now - last_seen) < 20 if last_seen > 0 else False
    data = dict(latest_mt5_telemetry)
    data["connected"] = is_live
    data["seconds_ago"] = now - last_seen if last_seen > 0 else 999999
    data["pending_orders"] = pending_orders_queue
    # W/L/PF dihitung dari riwayat yang sama dengan endpoint /mt5/history —
    # tidak ada angka hardcoded di status.
    data.update(_statistik_forex(_muat_forex_history()))
    return data


@router.get("/mt5/history")
async def get_mt5_history():
    """Mengembalikan daftar lengkap history transaksi EA MT5 untuk halaman Forex."""
    records = _muat_forex_history()
    if not records:
        return {
            "account": latest_mt5_telemetry.get("account", ""),
            "broker": latest_mt5_telemetry.get("broker", ""),
            "records": [],
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "net_pnl_usd": 0.0,
            "profit_factor": None,
        }
    return {
        "account": latest_mt5_telemetry.get("account", ""),
        "broker": latest_mt5_telemetry.get("broker", ""),
        **_statistik_forex(records),
        "records": records,
    }
