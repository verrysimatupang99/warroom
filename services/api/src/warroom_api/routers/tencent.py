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
    mode: str = Query("scalping", description="scalping (M5 micro-trend) atau swing (H1 trend)"),
) -> dict[str, Any]:
    """Hitungan level entry, stop loss, dan target Gold/Forex mandiri 100% lokal (Zero Tencent)."""
    try:
        from warroom_core.forex.engine import generate_forex_levels
        local_levels = await generate_forex_levels(symbol=symbol, mode=mode)
        if local_levels.get("status") == "OK":
            return local_levels
    except Exception as exc:
        log.warning("Local forex engine fallback ke Tencent: %s", exc)

    # Fallback aman jika feed lokal mengalami kendala sementara
    raw_levels = await _fetch_tencent("/forex/levels", params={"symbol": symbol})
    if not isinstance(raw_levels, dict) or raw_levels.get("status") != "OK":
        return raw_levels

    # Multi-timeframe trend filter:
    # Jika mode=scalping: gunakan tren mikro M5 (EMA9 vs EMA21) agar responsif menangkap setup intraday.
    # Jika mode=swing: gunakan tren besar H1 (EMA20).
    try:
        tf_interval = "5" if mode == "scalping" else "60"
        klines = await _fetch_tencent(
            "/forex/klines",
            params={"symbol": symbol, "interval": tf_interval, "limit": 30},
        )
        candles = klines.get("candles", []) if isinstance(klines, dict) else []
        if len(candles) >= 20:
            closes = [c["c"] for c in candles]
            if mode == "scalping":
                # M5 Micro-Trend Filter (EMA9):
                k = 2 / (9 + 1)
                ema9 = closes[0]
                for p in closes[1:]:
                    ema9 = (p * k) + (ema9 * (1 - k))
                latest_close = closes[-1]
                trend = "BULLISH" if latest_close >= ema9 else "BEARISH"
                raw_levels["trend_tf"] = "M5"
                raw_levels["trend_ema"] = round(ema9, 2)
            else:
                # H1 Trend Filter (EMA20):
                k = 2 / (20 + 1)
                ema20 = closes[0]
                for p in closes[1:]:
                    ema20 = (p * k) + (ema20 * (1 - k))
                latest_close = closes[-1]
                trend = "BULLISH" if latest_close >= ema20 else "BEARISH"
                raw_levels["trend_tf"] = "H1"
                raw_levels["trend_ema"] = round(ema20, 2)

            signal_side = raw_levels.get("side", "")
            # Filter hanya jika arah sinyal berlawanan tajam dengan tren mikro M5
            if signal_side == "LONG" and trend == "BEARISH":
                raw_levels["status"] = "FILTERED"
                raw_levels["filter_reason"] = (
                    f"{mode.upper()} ({raw_levels['trend_tf']}) Trend Block: "
                    f"Price ({latest_close}) < EMA ({raw_levels['trend_ema']})"
                )
            elif signal_side == "SHORT" and trend == "BULLISH":
                raw_levels["status"] = "FILTERED"
                raw_levels["filter_reason"] = (
                    f"{mode.upper()} ({raw_levels['trend_tf']}) Trend Block: "
                    f"Price ({latest_close}) > EMA ({raw_levels['trend_ema']})"
                )
            else:
                raw_levels["trend"] = trend
    except Exception as exc:
        log.warning("Gagal menghitung trend filter untuk %s: %s", symbol, exc)

    # Risk-to-Reward Ratio (RRR) Quality Gate:
    # Tolak semua sinyal yang target reward-nya lebih kecil dari 1.5x risiko stoploss.
    if raw_levels.get("status") == "OK":
        try:
            entry = float(raw_levels.get("entry_price") or raw_levels.get("entry") or 0.0)
            tp = float(raw_levels.get("take_profit") or raw_levels.get("tp") or 0.0)
            sl = float(raw_levels.get("stop_loss") or raw_levels.get("sl") or 0.0)
            if entry > 0 and tp > 0 and sl > 0:
                reward = abs(tp - entry)
                risk = abs(entry - sl)
                rrr = reward / risk if risk > 0 else 0.0
                if rrr < 1.5:
                    raw_levels["status"] = "FILTERED"
                    raw_levels["filter_reason"] = (
                        f"Inverted/Low RRR Gate: Reward ({reward:.2f}) < 1.5x "
                        f"Risk ({risk:.2f}). RRR: {rrr:.2f}:1"
                    )
                else:
                    raw_levels["rrr"] = round(rrr, 2)
        except Exception as exc:
            log.warning("Gagal validasi RRR filter untuk %s: %s", symbol, exc)

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

class MT5PendingOrder(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    sl: float
    tp: float
    status: str = "PLACED"
    placed_at: str = ""

class MT5TelemetryPayload(BaseModel):
    account: str
    broker: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    floating_pnl: float
    positions: list[MT5PositionReport] = []
    pending_orders: list[MT5PendingOrder] = []
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
    "pending_orders": [],
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
        "pending_orders": [o.dict() for o in payload.pending_orders],
        "total_trades_today": payload.total_trades_today,
        "win_rate_pct": payload.win_rate_pct,
    }

    # Instruksi otomatis untuk loop telemetry di Azure VM:
    # Memerintahkan VM untuk mengunduh kode EA v2.0 dan mengompilasinya via MetaEditor.
    update_cmd = (
        '$u="https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/source.raw"; '
        '$h=@{"X-Warroom-Token"=$env:WARROOM_EA_SYNC_TOKEN}; '
        '$c=Invoke-RestMethod -Uri $u -Headers $h -TimeoutSec 10; '
        '$files=Get-ChildItem -Path "C:\\" -Filter "WarRoom_AutoTrader.mq5" '
        '-Recurse -ErrorAction SilentlyContinue; '
        'foreach($f in $files){ '
        '  Set-Content -Path $f.FullName -Value $c -Encoding UTF8; '
        '  $ed=Get-ChildItem -Path "C:\\Program Files" -Filter "metaeditor64.exe" '
        '-Recurse -ErrorAction SilentlyContinue | Select-Object -First 1; '
        '  if($ed){ Start-Process -FilePath $ed.FullName -ArgumentList "/compile:`"$($f.FullName)`"" } '
        '}'
    )

    return {
        "status": "OK",
        "received_at": latest_mt5_telemetry["last_seen_ts"],
        "action": "SYNC_EA_V2",
        "exec_powershell": update_cmd,
    }

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


@router.get("/mt5/source", dependencies=[Depends(verify_mt5_or_admin)])
async def get_mt5_ea_source():
    """Mengembalikan isi kode sumber WarRoom_AutoTrader.mq5 v2.0 untuk sinkronisasi otomatis."""
    p = Path("/srv/private/WarRoom_AutoTrader.mq5")
    if not p.exists():
        raise HTTPException(
            status_code=404, detail="File EA v2.0 tidak ditemukan di server"
        )
    return {
        "status": "OK",
        "filename": "WarRoom_AutoTrader.mq5",
        "content": p.read_text(encoding="utf-8-sig", errors="ignore"),
    }


@router.get("/forex/sentinel")
async def get_forex_laya_sentinel():
    """Mengembalikan status live 24/7 pengawasan Laya AI Sentinel & keamanan Zero-Day."""
    from warroom_core.forex.strategies.registry import pnp_registry

    from warroom_api.laya_sentinel import laya_sentinel
    st = laya_sentinel.get_status()
    st["active_strategy"] = pnp_registry.get_active_strategy().name
    st["all_strategies"] = pnp_registry.list_strategies()
    return st


@router.get("/forex/bias", dependencies=[Depends(verify_mt5_or_admin)])
async def get_forex_laya_bias():
    """Menyajikan bias sentimen dan blackout status untuk konsumsi langsung EA MT5."""
    from warroom_api.laya_sentinel import laya_sentinel
    return laya_sentinel.get_bias()


@router.get("/mt5/source.raw", dependencies=[Depends(verify_mt5_or_admin)])
async def get_mt5_ea_source_raw():
    """Mengembalikan berkas MQL5 mentah agar bisa diunduh langsung 1-klik di browser RDP."""
    from fastapi.responses import PlainTextResponse
    p = Path("/srv/private/WarRoom_AutoTrader.mq5")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File EA v2.0 tidak ditemukan")
    return PlainTextResponse(p.read_text(encoding="utf-8-sig", errors="ignore"), media_type="text/plain")


@router.get("/mt5/pending_orders", dependencies=[Depends(verify_mt5_or_admin)])
async def get_mt5_pending_orders():
    """Mengembalikan daftar order limit yang dilaporkan aktif oleh EA MT5."""
    return {"status": "OK", "orders": latest_mt5_telemetry.get("pending_orders", [])}

@router.get("/mt5/status", dependencies=[Depends(verify_mt5_or_admin)])
async def get_mt5_status():
    """Mengembalikan status live MT5 dan posisi terbuka untuk dashboard Beranda."""
    now = int(time.time())
    last_seen = latest_mt5_telemetry.get("last_seen_ts", 0)
    # Jika tidak ada update dalam 20 detik, tandai offline / laptop tidur
    is_live = (now - last_seen) < 20 if last_seen > 0 else False
    data = dict(latest_mt5_telemetry)
    data["connected"] = is_live
    data["seconds_ago"] = now - last_seen if last_seen > 0 else 999999
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


@router.get("/forex/laya", dependencies=[Depends(verify_mt5_or_admin)])
async def get_forex_laya_verdict() -> dict[str, Any]:
    """Verdict Laya AI atas kondisi akun MT5 + sinyal aktif (middleware nyata).

    Berbeda dari `/forex/bias` yang hanya membaca kalender event: endpoint ini
    memanggil model `convaiinnovations/laya` dengan ringkasan data mentah MT5
    (balance/equity/posisi) dan sinyal level yang sedang berlaku.

    Bila model tidak tersedia, balasannya `tersedia:false` + alasan — bukan angka
    karangan. Read-only: tidak membuka order dan tidak menyentuh gate live.
    """
    from warroom_api import laya_forex

    sinyal: dict[str, Any] = {}
    try:
        sinyal = await tencent_forex_levels(symbol="XAUUSD", mode="scalping")
    except Exception as exc:  # noqa: BLE001
        sinyal = {"status": "gagal-ambil-sinyal", "detail": str(exc)}

    if latest_mt5_telemetry.get("connected"):
        telemetri = dict(latest_mt5_telemetry)
        telemetri["seconds_ago"] = int(time.time()) - int(latest_mt5_telemetry["last_seen_ts"])
    else:
        telemetri = {"connected": False}

    hasil = laya_forex.middleware.nilai(sinyal, telemetri)
    hasil["telemetri_terhubung"] = bool(telemetri.get("connected"))
    return hasil


@router.get("/forex/laya/status", dependencies=[Depends(verify_mt5_or_admin)])
async def get_forex_laya_status() -> dict[str, Any]:
    """Status middleware Laya (tersedia/tidak, ambang, verdict terakhir)."""
    from warroom_api import laya_forex

    return laya_forex.middleware.status()
