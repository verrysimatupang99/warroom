"""Feed dan Engine Kuantitatif Mandiri untuk Forex & Emas (XAUUSD) dengan PNP Strategy.

Berjalan 100% lokal di server War Room tanpa bergantung pada node Tencent (Tailscale).
Mendukung arsitektur Plug-and-Play (PNP) di mana strategi bisa dibongkar-pasang dengan mudah.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from warroom_core.forex.strategies.registry import pnp_registry

log = logging.getLogger("warroom_core.forex.engine")

SYMBOL_MAP = {
    "XAUUSD": "GC=F",      # Gold Futures (COMEX)
    "EURUSD": "EURUSD=X",  # Euro / USD
    "GBPUSD": "GBPUSD=X",  # GBP / USD
    "USDJPY": "JPY=X",     # USD / JPY
    "DXY": "DX-Y.NYB",     # US Dollar Index
}


async def fetch_klines_direct(
    symbol: str = "XAUUSD", interval: str = "5m", range_period: str = "1d"
) -> list[dict[str, Any]]:
    """Tarik data candle OHLCV langsung dari feed institusional tanpa perantara Tencent."""
    mapped_sym = SYMBOL_MAP.get(symbol.upper(), symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{mapped_sym}"
    params = {"interval": interval, "range": range_period}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                log.warning("Feed candle gagal (%s): HTTP %d", symbol, resp.status_code)
                return []
            data = resp.json()
            chart = data.get("chart", {}).get("result", [])
            if not chart:
                return []
            res = chart[0]
            timestamps = res.get("timestamp", [])
            quotes = res.get("indicators", {}).get("quote", [{}])[0]
            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            candles = []
            for i in range(len(timestamps)):
                if None not in (opens[i], highs[i], lows[i], closes[i]):
                    candles.append({
                        "t": timestamps[i],
                        "o": round(float(opens[i]), 3),
                        "h": round(float(highs[i]), 3),
                        "l": round(float(lows[i]), 3),
                        "c": round(float(closes[i]), 3),
                        "v": float(volumes[i] or 0),
                    })
            return candles
    except Exception as exc:
        log.error("Error fetching direct klines for %s: %s", symbol, exc)
        return []


def calculate_indicators(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Hitung EMA9, EMA21, dan ATR14 secara deterministik dari klines."""
    if len(candles) < 15:
        return {}

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]

    # EMA 9
    k9 = 2 / (9 + 1)
    ema9 = closes[0]
    for c in closes[1:]:
        ema9 = (c * k9) + (ema9 * (1 - k9))

    # EMA 21
    k21 = 2 / (21 + 1)
    ema21 = closes[0]
    for c in closes[1:]:
        ema21 = (c * k21) + (ema21 * (1 - k21))

    # ATR 14
    tr_list = []
    for i in range(1, len(candles)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    atr14 = sum(tr_list[-14:]) / 14 if len(tr_list) >= 14 else (tr_list[-1] if tr_list else 1.0)
    current_price = closes[-1]

    return {
        "price": current_price,
        "ema9": round(ema9, 2),
        "ema21": round(ema21, 2),
        "atr14": round(atr14, 2),
        "atr_pct": round((atr14 / current_price) * 100, 4) if current_price > 0 else 0.0,
        "trend_m5": "BULLISH" if current_price >= ema9 else "BEARISH",
    }


def _indikator_dari_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Ubah snapshot broker menjadi struktur indikator yang sama dengan Yahoo.

    Mengembalikan None bila ada field wajib yang hilang/tidak wajar, sehingga
    pemanggil jatuh ke Yahoo. Sengaja TIDAK mengisi nilai default: nol palsu pada
    ATR akan menghasilkan jarak SL nol dan sinyal yang salah ukuran.
    """
    if not isinstance(snapshot, dict):
        return None

    wajib = ("bid", "atr_m5", "ema9_m5", "ema21_m5", "high_12", "low_12")
    nilai: dict[str, float] = {}
    for k in wajib:
        v = snapshot.get(k)
        if not isinstance(v, (int, float)) or v <= 0:
            return None
        nilai[k] = float(v)

    price = nilai["bid"]
    atr = nilai["atr_m5"]
    return {
        "price": price,
        "ema9": nilai["ema9_m5"],
        "ema21": nilai["ema21_m5"],
        "atr14": atr,
        "atr_pct": round(atr / price * 100.0, 4) if price > 0 else 0.0,
        "trend_m5": "BULLISH" if price >= nilai["ema9_m5"] else "BEARISH",
        "recent_high": nilai["high_12"],
        "recent_low": nilai["low_12"],
    }


async def generate_forex_levels(
    symbol: str = "XAUUSD",
    mode: str = "scalping",
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate sinyal order menggunakan Strategi PNP yang aktif.

    `snapshot` = snapshot BROKER dari telemetri EA (bid/atr_m5/ema9_m5/...).
    Bila diberikan dan lengkap, indikator TIDAK diambil dari Yahoo `GC=F`
    (futures), melainkan dari instrumen yang benar-benar dieksekusi. Yahoo hanya
    dipakai sebagai cadangan bila snapshot tidak ada/tidak lengkap.
    """
    ind_source = "yahoo:GC=F"
    market_data: dict[str, Any] = {"symbol": symbol.upper()}

    snap = _indikator_dari_snapshot(snapshot) if snapshot else None
    if snap is not None:
        ind = snap
        ind_source = "broker:mt5"
        market_data.update({"candles": [], **ind})
    else:
        candles_m5 = await fetch_klines_direct(symbol, interval="5m", range_period="1d")
        if not candles_m5 or len(candles_m5) < 15:
            return {"status": "REJECTED", "reason": "Data candle tidak cukup"}
        ind = calculate_indicators(candles_m5)
        market_data.update({"candles": candles_m5, **ind})

    # Evaluasi via Plug-and-Play Strategy Engine
    active_strategy = pnp_registry.get_active_strategy()
    signal = active_strategy.evaluate(market_data)

    if not signal:
        return {
            "symbol": symbol.upper(),
            "play": mode,
            "status": "WAITING_SETUP",
            "price": ind["price"],
            "trend": ind["trend_m5"],
            "strategy": active_strategy.name,
            "reason": "Kondisi pasar saat ini belum memenuhi kriteria strategi PNP aktif",
            # Audit R6: bila sinyal ditolak oleh gerbang (mis. Laya mati), sebutkan
            # alasannya. Tanpa ini, penolakan gerbang tidak bisa dibedakan dari
            # "pasar memang belum ada setup".
            "blocked_reason": getattr(active_strategy, "last_block_reason", None),
            # Audit: dari mana indikator diambil. "broker:mt5" berarti memakai
            # snapshot EA (instrumen yang benar-benar dieksekusi).
            "indicator_source": ind_source,
        }

    entry = signal["entry"]
    sl = signal["sl"]
    tp1 = signal["tp1"]
    tp2 = signal["tp2"]
    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp1 - entry), 2)
    rrr = round(reward / risk, 2) if risk > 0 else 1.5

    return {
        "symbol": symbol.upper(),
        "play": mode,
        "side": signal["side"],
        "tf": active_strategy.timeframe.replace("m", ""),
        "price": ind["price"],
        "atr": ind["atr14"],
        "atr_pct": ind["atr_pct"],
        "status": "OK",
        # R4 (23-24 Okt 2026): HARGA ABSOLUT TIDAK LAGI DIKIRIM SEBAGAI SUMBER
        # KEBENARAN. Engine mengambil data dari Yahoo `GC=F` (kontrak berjangka
        # emas), sedangkan EA mengeksekusi `XAUUSDm` (spot broker). Selisih
        # terukur $12,04 sementara jarak SL strategi hanya $2,53 — SL/TP dari
        # snapshot futures tidak ada artinya untuk simbol spot.
        #
        # Kontrak baru: engine mengirim NIAT (side) + JARAK (risk/reward) + stempel
        # waktu. EA menghitung sendiri level dari ask/bid broker, sehingga rasio
        # selalu utuh pada harga yang benar-benar dieksekusi.
        #
        # `levels` tetap dikirim untuk kompatibilitas/pembacaan manusia, tetapi
        # EA WAJIB mengabaikannya selama `levels_mode == "relative"`.
        "indicator_source": ind_source,
        "levels_mode": "relative",
        "risk": risk,
        "reward": reward,
        # R2: EA menolak sinyal yang lebih tua dari InpMaxSignalAgeSec. Tanpa
        # stempel waktu, sinyal lama dieksekusi ke pasar yang sudah bergerak.
        "generated_at": int(time.time()),
        "levels": {
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "risk": risk,
            "reward": reward,
            "order_type": "MARKET",
        },
        "trend_tf": "M5",
        "trend_ema": ind["ema9"],
        "trend": ind["trend_m5"],
        "rrr": rrr,
        "strategy": active_strategy.name,
        "confidence": signal.get("confidence", 0.8),
        "source": "WarRoom PNP Engine (Zero Tencent)",
    }
