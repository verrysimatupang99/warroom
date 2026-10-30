"""Router proxy terenkripsi ke node Tencent via Tailscale WireGuard.

Menghubungkan War Room ke API internal node data (env `WARROOM_TENCENT_BASE`)
secara aman tanpa membuka port ke internet publik.
"""

from __future__ import annotations
import os

import json
import logging
import csv
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from warroom_api import lokal
from warroom_api.auth_ea import verify_mt5_or_admin

router = APIRouter(prefix="/api/v1/tencent", tags=["tencent"])
log = logging.getLogger("warroom_api.tencent")

TENCENT_BASE = os.environ.get("WARROOM_TENCENT_BASE", "").rstrip("/")
TIMEOUT_S = 6.0
# Endpoint yang menyentuh sumber eksternal (mis. aliran dana IDX) butuh waktu
# lebih lama daripada lookup in-memory MiniMax.
TIMEOUT_S_LARGE = 20.0

# Telemetri EA sebelumnya hanya hidup di memori: begitu API restart, seluruh
# riwayat ekuitas dan PnL hilang. Sekarang diringkas ke tabel facts, dibatasi
# sekali per menit supaya tidak membanjiri DB (EA mengirim tiap ~5 detik).
_MT5_SIMPAN_TERAKHIR = 0.0
_MT5_JEDA_SIMPAN = 60.0


def _simpan_snapshot_mt5(data: dict[str, Any]) -> None:
    global _MT5_SIMPAN_TERAKHIR
    sekarang = time.time()
    if sekarang - _MT5_SIMPAN_TERAKHIR < _MT5_JEDA_SIMPAN:
        return
    _MT5_SIMPAN_TERAKHIR = sekarang
    try:
        import hashlib
        from datetime import UTC, datetime

        from warroom_core.db import session_scope
        from warroom_core.db.models import Fact

        ringkas = {
            k: data.get(k)
            for k in (
                "account", "broker", "balance", "equity", "floating_pnl",
                "margin", "free_margin", "net_pnl_today_usd", "total_trades_today",
                "wins_today", "losses_today", "win_rate_today_pct",
                "spread_pts", "bid", "ask", "digits",
                "eval_at", "eval_alasan", "eval_sesi", "eval_atr", "eval_spread",
                "eval_rsi", "eval_ema_fast", "eval_ema_slow", "eval_tren",
                "server_time",
            )
        }
        ringkas["posisi"] = len(data.get("positions") or [])
        ringkas["pending"] = len(data.get("pending_orders") or [])
        isi = json.dumps(ringkas, sort_keys=True, default=str)
        with session_scope() as s:
            s.add(
                Fact(
                    kind="mt5_snapshot",
                    key="ringkas",
                    value_json=ringkas,
                    source="EA telemetry",
                    observed_at=datetime.now(UTC),
                    ttl_s=300,
                    hash=hashlib.sha256(f"{isi}|{int(sekarang)}".encode()).hexdigest(),
                )
            )
    except Exception as exc:  # noqa: BLE001
        # Kegagalan mencatat tidak boleh menggagalkan telemetri EA.
        log.warning("gagal simpan snapshot mt5: %s", exc)


async def _fetch_tencent(
    path: str,
    params: dict[str, Any] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> Any:
    if not TENCENT_BASE:
        # Tidak ada node upstream. Ambil dari sumber publik langsung
        # (MEXC untuk crypto, Yahoo untuk forex dan IHSG). Kalau sebuah data
        # memang tidak punya padanan lokal, jawab 503 dengan alasannya,
        # bukan angka karangan.
        try:
            return await lokal.sebar(path, params)
        except lokal.SumberKosong as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "not_available", "message": str(exc)},
            ) from exc
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
            detail=(
                f"Node data upstream tidak terjangkau ({TENCENT_BASE}): "
                f"{type(exc).__name__}"
            ),
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

        # Snapshot BROKER hanya dipakai bila segar. EA mengirim telemetri tiap ~5 s;
        # batas 60 s memberi toleransi tanpa memakai harga basi (pasar tutup/EA mati
        # akan otomatis jatuh ke Yahoo, dan itu ditandai lewat `indicator_source`).
        snapshot = None
        seen = int(latest_mt5_telemetry.get("last_seen_ts") or 0)
        if seen and (int(time.time()) - seen) <= 60 and latest_mt5_telemetry.get("atr_m5"):
            snapshot = dict(latest_mt5_telemetry)

        local_levels = await generate_forex_levels(symbol=symbol, mode=mode, snapshot=snapshot)
        # WAITING_SETUP adalah JAWABAN SAH ("belum ada setup"), bukan kegagalan.
        # Dulu hanya status "OK" yang diterima, sehingga setiap kali pasar tidak
        # memberi setup, endpoint jatuh ke fallback Tencent yang menggantung dan
        # ikut membekukan seluruh API (insiden 23 Okt 2026: /api/v1/build balas 000).
        # Sekarang status apa pun dari engine lokal dikembalikan apa adanya, kecuali
        # memang tidak ada hasil.
        if isinstance(local_levels, dict) and local_levels.get("status"):
            return local_levels
    except Exception as exc:
        log.warning("Local forex engine gagal total, fallback ke Tencent: %s", exc)

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
    # Statistik nyata dari riwayat broker (menggantikan konstanta hardcode lama)
    # Diberi akhiran _today agar TIDAK bertabrakan dengan statistik jurnal
    # all-time yang di-inject /mt5/status lewat _statistik_forex(). Dulu
    # `wins`/`losses` saling menimpa sehingga tampil "wins=4" di samping
    # "total_trades_today=0".
    wins_today: int | None = None
    losses_today: int | None = None
    win_rate_today_pct: float | None = None
    net_pnl_today_usd: float | None = None
    # Snapshot broker: sumber kebenaran harga untuk instrumen yang dieksekusi.
    bid: float | None = None
    ask: float | None = None
    spread_pts: int | None = None
    digits: int | None = None
    atr_m5: float | None = None
    ema9_m5: float | None = None
    ema21_m5: float | None = None
    high_12: float | None = None
    low_12: float | None = None
    # Evaluasi sinyal Reaper terakhir (dikirim EA v3.1). Semua opsional supaya
    # EA lama tetap diterima tanpa error.
    server_time: int | None = None
    eval_at: int | None = None
    eval_alasan: str | None = None
    eval_sesi: bool | None = None
    eval_atr: float | None = None
    eval_spread: float | None = None
    eval_rsi: float | None = None
    eval_ema_fast: float | None = None
    eval_ema_slow: float | None = None
    eval_tren: str | None = None

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

# --- Logger telemetri (spread per jam) -------------------------------------
# Telemetri EA datang tiap 1-5 detik dan sebelumnya hanya disimpan di memori,
# sehingga histori spread hilang setiap poll. Baris di bawah menambahkan
# pencatatan ke CSV dengan throttle 10 detik supaya berkas tidak membengkak.
TELEMETRY_LOG = Path("/var/lib/warroom/telemetry_log.csv")
_telemetry_log_last = 0.0
TELEMETRY_LOG_INTERVAL_S = 10.0


def _catat_telemetri(t: dict[str, Any]) -> None:
    global _telemetry_log_last
    sekarang = time.time()
    if sekarang - _telemetry_log_last < TELEMETRY_LOG_INTERVAL_S:
        return
    _telemetry_log_last = sekarang
    try:
        TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        baru = not TELEMETRY_LOG.exists()
        with TELEMETRY_LOG.open("a", newline="") as f:
            import csv as _csv

            w = _csv.writer(f)
            if baru:
                w.writerow(["ts", "iso", "bid", "ask", "spread_pts", "digits",
                            "atr_m5", "positions", "net_pnl_today_usd", "equity"])
            w.writerow([
                int(sekarang),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sekarang)),
                t.get("bid"), t.get("ask"), t.get("spread_pts"), t.get("digits"),
                t.get("atr_m5"), len(t.get("positions") or []),
                t.get("net_pnl_today_usd"), t.get("equity"),
            ])
    except OSError as exc:  # pragma: no cover - jangan ganggu jalur telemetri
        log.warning("Gagal menulis log telemetri: %s", exc)


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
        "wins_today": payload.wins_today,
        "losses_today": payload.losses_today,
        "win_rate_today_pct": payload.win_rate_today_pct,
        "net_pnl_today_usd": payload.net_pnl_today_usd,
        # Snapshot broker (dipakai untuk jarak risk/reward pada instrumen nyata)
        "bid": payload.bid,
        "ask": payload.ask,
        "spread_pts": payload.spread_pts,
        "digits": payload.digits,
        "atr_m5": payload.atr_m5,
        "ema9_m5": payload.ema9_m5,
        "ema21_m5": payload.ema21_m5,
        "high_12": payload.high_12,
        "low_12": payload.low_12,
        "server_time": payload.server_time,
        "eval_at": payload.eval_at,
        "eval_alasan": payload.eval_alasan,
        "eval_sesi": payload.eval_sesi,
        "eval_atr": payload.eval_atr,
        "eval_spread": payload.eval_spread,
        "eval_rsi": payload.eval_rsi,
        "eval_ema_fast": payload.eval_ema_fast,
        "eval_ema_slow": payload.eval_ema_slow,
        "eval_tren": payload.eval_tren,
    }
    _simpan_snapshot_mt5(latest_mt5_telemetry)

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

    _catat_telemetri(latest_mt5_telemetry)

    return {
        "status": "OK",
        "received_at": latest_mt5_telemetry["last_seen_ts"],
        "action": "SYNC_EA_V2",
        "exec_powershell": update_cmd,
    }

class MT5FillPayload(BaseModel):
    """Satu kejadian eksekusi (entry) yang dilaporkan EA."""

    ticket: int = 0
    symbol: str = ""
    side: str = ""
    volume: float = 0.0
    price_requested: float = 0.0
    price_filled: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    spread_pts: int = 0
    digits: int = 0
    latency_ms: int = 0
    retcode: int = 0
    execution_mode: int = -1
    open_positions: int = 0
    equity: float = 0.0


FILL_LOG = Path("/var/lib/warroom/fills.csv")


@router.post("/mt5/fill", dependencies=[Depends(verify_mt5_or_admin)])
async def report_mt5_fill(payload: MT5FillPayload) -> dict[str, Any]:
    """Catat kualitas eksekusi: harga diminta vs harga didapat + latensi.

    Dipakai untuk mengukur slippage nyata per jam dan per kondisi pasar.
    Tidak mengubah perilaku EA.
    """
    arah = 1.0 if payload.side.upper() in ("BUY", "LONG") else -1.0
    point = 10.0 ** (-payload.digits) if payload.digits >= 0 else 0.0
    slip_pts = ((payload.price_filled - payload.price_requested) * arah / point) if point else 0.0
    try:
        FILL_LOG.parent.mkdir(parents=True, exist_ok=True)
        baru = not FILL_LOG.exists()
        with FILL_LOG.open("a", newline="") as f:
            import csv as _csv

            w = _csv.writer(f)
            if baru:
                w.writerow(["ts", "iso", "ticket", "symbol", "side", "volume",
                            "price_requested", "price_filled", "slippage_pts",
                            "spread_pts", "latency_ms", "retcode", "execution_mode",
                            "open_positions", "equity", "sl", "tp"])
            w.writerow([
                int(time.time()), time.strftime("%Y-%m-%d %H:%M:%S"),
                payload.ticket, payload.symbol, payload.side, payload.volume,
                payload.price_requested, payload.price_filled, round(slip_pts, 2),
                payload.spread_pts, payload.latency_ms, payload.retcode,
                payload.execution_mode, payload.open_positions, payload.equity,
                payload.sl, payload.tp,
            ])
    except OSError as exc:
        log.warning("Gagal menulis log fill: %s", exc)
        raise HTTPException(status_code=500, detail="gagal menulis log fill") from exc

    return {"status": "OK", "slippage_pts": round(slip_pts, 2)}


class MT5DealPayload(BaseModel):
    """Deal tertutup yang dilaporkan EA (posisi sudah final)."""

    ticket: int
    position: int = 0
    symbol: str = ""
    side: str = ""
    volume: float = 0.0
    open_time: str = ""
    open_price: float = 0.0
    close_time: str = ""
    close_price: float = 0.0
    profit: float = 0.0
    swap: float = 0.0
    commission: float = 0.0
    magic: int = 0
    comment: str = ""


DEAL_LOG = Path("/var/lib/warroom/deals.csv")
_DEAL_HEADER = [
    "ts", "iso", "ticket", "position", "symbol", "side", "volume",
    "open_time", "open_price", "close_time", "close_price",
    "profit", "swap", "commission", "net", "magic", "comment",
]
_DEAL_LOCK = threading.Lock()


@router.post("/mt5/deal", dependencies=[Depends(verify_mt5_or_admin)])
async def report_mt5_deal(payload: MT5DealPayload) -> dict[str, Any]:
    """Catat deal tertutup (satu baris per posisi) untuk jurnal forex.

    Idempoten per `ticket`: EA boleh mengirim ulang setelah restart tanpa
    menggandakan baris di `deals.csv`.
    """
    if payload.ticket <= 0:
        raise HTTPException(status_code=400, detail="ticket deal tidak valid")
    net = payload.profit + payload.swap + payload.commission
    with _DEAL_LOCK:
        sudah: set[int] = set()
        baru = not DEAL_LOG.exists()
        if not baru:
            try:
                with DEAL_LOG.open(newline="") as f:
                    for row in csv.DictReader(f):
                        try:
                            sudah.add(int(row.get("ticket") or 0))
                        except (TypeError, ValueError):
                            continue
            except OSError as exc:
                log.warning("gagal baca deals.csv: %s", exc)
                raise HTTPException(status_code=500, detail="gagal baca log deal") from exc
        if payload.ticket in sudah:
            return {"status": "duplikat", "ticket": payload.ticket, "net": round(net, 2)}
        try:
            DEAL_LOG.parent.mkdir(parents=True, exist_ok=True)
            with DEAL_LOG.open("a", newline="") as f:
                w = csv.writer(f)
                if baru:
                    w.writerow(_DEAL_HEADER)
                w.writerow([
                    int(time.time()),
                    payload.close_time or time.strftime("%Y-%m-%d %H:%M:%S"),
                    payload.ticket,
                    payload.position,
                    payload.symbol,
                    payload.side,
                    payload.volume,
                    payload.open_time,
                    payload.open_price,
                    payload.close_time,
                    payload.close_price,
                    payload.profit,
                    payload.swap,
                    payload.commission,
                    round(net, 2),
                    payload.magic,
                    payload.comment,
                ])
        except OSError as exc:
            log.warning("gagal tulis deals.csv: %s", exc)
            raise HTTPException(status_code=500, detail="gagal menulis log deal") from exc
    return {"status": "OK", "ticket": payload.ticket, "net": round(net, 2)}


PANEL_STATE = Path("/var/lib/warroom/panels.json")
MOMENTUM_STATE = Path("/var/lib/warroom/momentum_paper.json")
MOMENTUM_TRADES = Path("/var/lib/warroom/momentum_trades.csv")


@router.get("/mt5/panels", dependencies=[Depends(verify_mt5_or_admin)])
async def get_panel_sim() -> dict[str, Any]:
    """Ringkasan 3 panel simulator (A/B/C) untuk ditampilkan di dashboard."""
    if not PANEL_STATE.exists():
        return {"panels": [], "catatan": "simulator belum pernah berjalan"}
    try:
        data = json.loads(PANEL_STATE.read_text())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="state panel tidak terbaca") from exc

    hasil = []
    for nama in sorted(data):
        p = data[nama]
        basis = p["ekuitas"] - p.get("pnl_hari", 0.0)
        hasil.append({
            "nama": nama,
            "risk_pct": p["risk_pct"],
            "target_pct": p["target_pct"],
            "stop_pct": p["stop_pct"],
            "ekuitas": round(p["ekuitas"], 2),
            "total_pct": round(100 * (p["ekuitas"] / p["modal_awal"] - 1), 2),
            "hari_pct": round(100 * p.get("pnl_hari", 0.0) / basis, 2) if basis else 0.0,
            "trades_hari": p["trades_hari"],
            "max_trades": p["max_trades"],
            "berhenti": bool(p["berhenti"]),
            "alasan": p.get("alasan_berhenti", ""),
        })
    return {"panels": hasil}


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

    hasil = await laya_forex.middleware.nilai_async(sinyal, telemetri)
    hasil["telemetri_terhubung"] = bool(telemetri.get("connected"))
    return hasil


@router.get("/forex/laya/status", dependencies=[Depends(verify_mt5_or_admin)])
async def get_forex_laya_status() -> dict[str, Any]:
    """Status middleware Laya (tersedia/tidak, ambang, verdict terakhir)."""
    from warroom_api import laya_forex

    return laya_forex.middleware.status()


@router.get("/crypto/momentum", dependencies=[Depends(verify_mt5_or_admin)])
async def get_momentum_paper() -> dict[str, Any]:
    """Ringkasan paper trader momentum (40 koin) untuk dashboard Crypto.

    Sumber: state yang ditulis ops/momentum_paper.py tiap jam.
    Tidak ada order nyata — ini pencatatan.
    """
    if not MOMENTUM_STATE.exists():
        return {"aktif": False, "catatan": "paper trader belum pernah berjalan"}

    try:
        st = json.loads(MOMENTUM_STATE.read_text())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="state momentum tidak terbaca") from exc

    # ekuitas butuh harga terakhir; pakai entry sebagai perkiraan konservatif
    ekuitas = 0.0
    posisi: list[dict[str, Any]] = []
    for sym, p in st.items():
        harga = p.get("harga") or p["entry"] or 0.0
        nilai = p["kas"] + p["qty"] * harga
        ekuitas += nilai
        if p["qty"] > 0:
            posisi.append({
                "koin": sym,
                "entry": round(p["entry"], 8),
                "harga": round(harga, 8),
                "qty": round(p["qty"], 8),
                "puncak": round(p["puncak"], 8),
                "pl_pct": round((harga / p["entry"] - 1) * 100, 2) if p["entry"] else 0.0,
            })

    modal = 500.0 * len(st) if st else 0.0
    dagang: list[dict[str, str]] = []
    if MOMENTUM_TRADES.exists():
        baris = MOMENTUM_TRADES.read_text().strip().splitlines()
        kepala = baris[0].split(",") if baris else []
        for r in baris[1:][-20:]:
            nilai_baris = r.split(",")
            dagang.append(dict(zip(kepala, nilai_baris, strict=False)))

    posisi.sort(key=lambda x: x["koin"])
    return {
        "aktif": True,
        "jumlah_koin": len(st),
        "modal": round(modal, 2),
        "ekuitas_perkiraan": round(ekuitas, 2),
        "return_pct": round((ekuitas / modal - 1) * 100, 2) if modal else 0.0,
        "posisi_terbuka": len(posisi),
        "posisi": posisi[:20],
        "trade_terakhir": dagang,
        "catatan": "paper trading 40 koin, tanpa order nyata; harga dari candle harian terakhir",
    }
