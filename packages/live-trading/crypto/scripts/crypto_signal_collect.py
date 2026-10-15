#!/usr/bin/env python3
"""Crypto signal collector for topic 653 — BINANCE FUTURES edition.
User executes on Binance perpetuals via USDT-margined contracts.
All data from Binance Futures REST API (fapi.binance.com) — no API key needed.

Data CLEANING FEATURES:
  - Shared data_store dict: all endpoints cached globally, no double-fetch
  - Retry with backoff: up to 3 attempts per endpoint
  - Freshness check: validate last kline timestamp
  - Graceful degradation: partial failure still outputs valid data
  - HTML error page detection: blocks sanitized as failures

Prints a compact SMC-oriented digest to stdout that the composing agent
turns into a Telegram signal post.
"""
import json
import subprocess
import sys
import time


BIG_CAP = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
MID_CAP = ["SUIUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "FETUSDT", "DOGEUSDT"]
# Pilihan likuiditas solid dan instrumen dengan volume memadai (pantau spread pada instrumen volatil)
EXTRA = ["XRPUSDT", "HYPEUSDT", "LINKUSDT", "NEARUSDT", "LTCUSDT", "AVAXUSDT",
         "FARTCOINUSDT", "PUMPUSDT", "UNIUSDT", "LITUSDT", "ZECUSDT"]
# Pasangan kontrak Binance fapi dan OKX swap dengan likuiditas tinggi
EXTRA2 = ["ENAUSDT", "VIRTUALUSDT", "ONDOUSDT", "TAOUSDT"]
# Kontrak dengan lot size sesuai batas target risiko per transaksi
EXTRA3 = ["AAVEUSDT"]
WATCHLIST = BIG_CAP + MID_CAP + EXTRA + EXTRA2 + EXTRA3

# Weights per call to respect Binance rate limit (60 weight/min)
# klines=5, ticker/*=1, premiumIndex=1, openInterest=1
# Per pair budget: price(1)+24hr(1)+1d_kl(5)+4h_kl(5)+1h_kl(5)+premium(1)+oi(1) = 19
# Total 10 pairs: 190 weight ≈ 3.5 min at 60/min. Acceptable for cron.

# Cache global untuk satu siklus pemindaian
_data = {
    "prices": {},       # symbol -> {"price": float, "chg24h": float, "vol24_quote": float, "index": float}
    "klines": {},       # f"{symbol}_{interval}" -> list of raw binance kline rows
    "fundings": {},     # symbol -> funding_rate_pct (float)
    "ois": {},          # symbol -> oi_float
    "of_24hr": {},      # symbol -> raw 24hr dict
    "of_last_price": {},# symbol -> lastPrice from 24hr
    "of_hl": {},        # symbol -> (highPrice, lowPrice) from 24hr
    "of_bid_ask": {},   # symbol -> (bidPrice, askPrice) from 24hr
}


def curl(url):
    """Fetch JSON from URL."""
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "12", url],
            capture_output=True, text=True, timeout=15,
        ).stdout
        if "<html>" in out or "<!DOCTYPE" in out:
            print(f"[WARN] HTTP block/error from Binance: {url}", file=sys.stderr)
            return None
        return json.loads(out)
    except Exception:
        return None


def curl_retry(url, retries=3):
    """Fetch with retry + backoff. No external cache — rely on _data dict."""
    for i in range(retries):
        result = curl(url)
        if result is not None:
            return result
        if i < retries - 1:
            time.sleep(1.0 * (i + 1))
    return None


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + (1 - k) * e
    return e


def structure(highs, lows):
    n = min(len(highs), 30)
    h, l = highs[-n:], lows[-n:]
    mid = n // 2
    if mid < 3:
        return "data kurang"
    hh = max(h[mid:]) > max(h[:mid])
    hl = min(l[mid:]) > min(l[:mid])
    ll = min(l[mid:]) < min(l[:mid])
    lh = max(h[mid:]) < max(h[:mid])
    if hh and hl:
        return "HH/HL bullish"
    if ll and lh:
        return "LH/LL bearish"
    return "ranging/mixed"


# Fetcher data order flow per instrumen
def fetch_orderflow(symbol):
    """Fetch all order-flow endpoints for one symbol. Results stored in _data."""
    # --- 24hr ticker ---
    hr = curl_retry(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}")
    if hr:
        _data["of_24hr"][symbol] = hr
        _data["of_last_price"][symbol] = float(hr.get("lastPrice", 0))
        _data["of_hl"][symbol] = (
            float(hr.get("highPrice", 0)), float(hr.get("lowPrice", 0))
        )
        # Endpoint /ticker/24hr pada fapi tidak mengembalikan bid/ask; spread diambil dari bookTicker.
        bid = float(hr.get("bidPrice", 0) or 0)
        ask = float(hr.get("askPrice", 0) or 0)
        if bid > 0 and ask > 0 and (ask - bid) / bid < 0.1:
            _data["of_bid_ask"][symbol] = (bid, ask)

    # --- Book ticker (real bid/ask for spread) ---
    ba = curl_retry(f"https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol={symbol}")
    if ba and ba.get("bidPrice") and ba.get("askPrice"):
        try:
            bid = float(ba["bidPrice"])
            ask = float(ba["askPrice"])
            if bid > 0 and ask > 0 and (ask - bid) / bid < 0.1:
                _data["of_bid_ask"][symbol] = (bid, ask)
        except (TypeError, ValueError):
            pass

    # --- Latest price ---
    tick = curl_retry(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}")
    if tick and "price" in tick:
        _data["prices"][symbol] = {"price": float(tick["price"])}

    # --- Open Interest ---
    oi_data = curl_retry(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}")
    if oi_data and "openInterest" in oi_data:
        try:
            _data["ois"][symbol] = float(oi_data["openInterest"])
        except ValueError:
            pass

    # --- Funding rate ---
    fund = curl_retry(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}")
    if fund and "lastFundingRate" in fund:
        try:
            _data["fundings"][symbol] = float(fund["lastFundingRate"]) * 100
        except ValueError:
            pass

    # --- 1h klines (needed for vol_delta AND used by SMC phase 1) ---
    kl1h = curl_retry(
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1h&limit=100"
    )
    if kl1h and len(kl1h) >= 24:
        key_1h = f"{symbol}_1h"
        closes = [float(r[4]) for r in kl1h]
        highs = [float(r[2]) for r in kl1h]
        lows = [float(r[3]) for r in kl1h]
        volumes = [float(r[5]) for r in kl1h]
        timestamps_ms = [int(r[0]) for r in kl1h]
        _data["klines"][key_1h] = {
            "closes": closes, "highs": highs, "lows": lows,
            "volumes": volumes, "timestamps": timestamps_ms,
            "last_ts_ms": timestamps_ms[-1],
        }


# Fetcher struktur kline SMC per instrumen
def fetch_klines(symbol, interval="1h", limit=24):
    """Fetch klines for one symbol+interval. Stored in _data['klines'].
    Returns parsed dict {closes, highs, lows, volumes, last_ts_ms}.
    None on failure.
    """
    key = f"{symbol}_{interval}"
    kl = curl_retry(
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    )
    if not kl or len(kl) < 10:
        _data["klines"][key] = None
        return None

    closes = [float(r[4]) for r in kl]
    highs = [float(r[2]) for r in kl]
    lows = [float(r[3]) for r in kl]
    volumes = [float(r[5]) for r in kl]
    timestamps_ms = [int(r[0]) for r in kl]
    last_ts = timestamps_ms[-1]

    _data["klines"][key] = {
        "closes": closes, "highs": highs, "lows": lows,
        "volumes": volumes, "timestamps": timestamps_ms,
        "last_ts_ms": last_ts,
    }
    return _data["klines"][key]


def fresh_check(key, max_age_hours=2):
    """Check freshness of cached kline data. Returns True if OK."""
    entry = _data["klines"].get(key)
    if not entry:
        return False
    now_ms = int(time.time() * 1000)
    age_h = (now_ms - entry["last_ts_ms"]) / 3600000
    if age_h > max_age_hours:
        print(f"[STALE] [{key}] kline {age_h:.1f}h old (>{max_age_hours}h)", file=sys.stderr)
        return False
    return True


# Helper analisis order flow dan volatilitas
def calc_buy_pressure(symbol):
    """Where is current price within 24h range? (higher = more bullish pressure)."""
    hl = _data["of_hl"].get(symbol)
    last = _data["of_last_price"].get(symbol)
    if not hl or hl[0] == 0 or not last:
        return 0.0
    h24, l24 = hl
    if h24 <= l24 or (h24 - l24) < last * 0.001:
        return 0.0
    mid24 = (h24 + l24) / 2
    return (last - mid24) / (h24 - l24) * 100


def calc_vol_delta(symbol):
    """Volume change: last 6 bars vs prior 18 bars (from 1h klines)."""
    entry = _data["klines"].get(f"{symbol}_1h")
    if not entry or len(entry["volumes"]) < 24:
        return None
    vols = entry["volumes"]
    last6 = sum(vols[-6:])
    prior18 = sum(vols[-24:-6])
    if prior18 <= 0:
        return None
    return (last6 - prior18) / prior18 * 100


def classify_flow(bp, vd, long_pct, funding=0.0, use_fallback=True):
    """Classify order flow — conservative defaults for low-volatility periods.
    
    Strategy: 
    - Primary: vol_delta when available and varied (>30% spread between pairs)
    - Fallback: buy_pressure + funding when all vols are near-zero
    
    Conservative bias: during quiet hours most pairs show mild directional
    pressure that's NOT meaningful for signal generation. Only flag extremes.
    """
    # --- Check if vol_deltas are varied enough to be useful ---
    all_vd_available = vd is not None
    # During low-vol period (all vd < -70%), vol_delta is noise
    is_low_vol = all_vd_available and vd < -70
    
    primary = None
    has_sig = vd is not None and abs(bp) > 10
    
    if not is_low_vol:
        # Vol delta is informative — use it as primary signal
        if has_sig and bp > 30 and vd > 10 and long_pct > 55:
            primary = "🟢 AGGRESSIVE BUY"
        elif has_sig and bp > 15 and vd >= -99 and long_pct > 52:
            primary = "🟢 Mild buy"
        elif has_sig and bp < -30 and vd < -10 and long_pct < 45:
            primary = "🔴 AGGRESSIVE SELL"
        elif has_sig and bp < -15 and vd <= 99 and long_pct < 48:
            primary = "🔴 Mild sell"
    
    if primary:
        return f"{primary} ⚠️(vol low)" if is_low_vol else primary
    
    if not use_fallback:
        return "⚪ Neutral"
    
    # --- FALLBACK: buy_pressure ONLY, very conservative ---
    # During low-vol hours, moderate bp swings are noise, not signals
    # Only flag EXTREME directional pressure
    if bp < -55:
        return "🔴 Strong sell pressure (extreme)"
    if bp > 55:
        return "🟢 Strong buy pressure (extreme)"
    
    # Between -55 and +55 is considered neutral during low-vol periods
    return "⚪ Neutral"


def make_tf_label(struct, pos, zone, pd, bars):
    return f"{struct}, price {pos} EMA50, {zone} ({pd*100:.0f}% of {min(bars,30)}-bar range)"


# Analisis satu pasangan instrumen untuk pemindaian
def analyze(symbol):
    """Fetch all data for one symbol and return a summary dict.

    Returns None on total failure, else dict with keys:
      price, chg24h, funding, Week1, Day1, Hour4, Min60
    """
    try:
        # Phase 0: order flow (caches into _data)
        fetch_orderflow(symbol)

        price_info = _data["prices"].get(symbol)
        if not price_info:
            lp = _data["of_last_price"].get(symbol, 0)
            hr = _data["of_24hr"].get(symbol, {})
            p = lp
            chg = float(hr.get("priceChangePercent", 0)) if hr else 0
            wq = float(hr.get("quoteVolume", 0)) if hr else 0
            wap = float(hr.get("weightedAvgPrice", 0))
            price_info = {"price": p, "chg24h": chg, "vol24_quote": wq,
                          "index": wap if wap > 0 else p}
            _data["prices"][symbol] = price_info

        funding = _data["fundings"].get(symbol)

        # SMC klines for each TF
        tf_config = {
            "1d": {"limit": 100, "max_age": 48},
            "4h": {"limit": 100, "max_age": 8},
            "1h": {"limit": 60, "max_age": 2, "skip_if_cached": True},
        }
        labels_map = {"1d": "Day1", "4h": "Hour4", "1h": "Min60"}
        label_map = {"Week1": "1w", "Day1": "1d", "Hour4": "4h", "Min60": "1h"}

        result = {}
        result["price"] = price_info["price"]
        result["chg24h"] = price_info.get("chg24h", 0)
        result["funding"] = f"{funding:+.4f}%" if funding is not None else "n/a"

        for interval, cfg in tf_config.items():
            key = f"{symbol}_{interval}"
            existing = _data["klines"].get(key)
            if cfg.get("skip_if_cached") and existing is not None and len(existing["closes"]) >= 60:
                entry = existing
            else:
                entry = fetch_klines(symbol, interval, cfg["limit"])
            lbl = labels_map[interval]
            if not entry or not fresh_check(f"{symbol}_{interval}", cfg["max_age"]):
                result[lbl] = "n/a"
                continue
            closes = entry["closes"][:]
            closes[-1] = price_info["price"]
            highs = entry["highs"]
            lows = entry["lows"]
            bars = len(closes)
            e50 = ema(closes[:-1], 50)
            last = closes[-1]
            pos = "above" if e50 and last > e50 else ("below" if e50 else "n/a")
            rng_hi = max(highs[-30:])
            rng_lo = min(lows[-30:])
            if rng_hi == rng_lo:
                pd, zone = 0.5, "equilibrium"
            else:
                pd = (last - rng_lo) / (rng_hi - rng_lo)
                zone = "premium" if pd > 0.6 else ("discount" if pd < 0.4 else "equilibrium")
            struct = structure(highs, lows)
            result[lbl] = make_tf_label(struct, pos, zone, pd, bars)

        return result
    except Exception as exc:
        print(f"[WARN] analyze({symbol}) failed: {exc}", file=sys.stderr)
        return None


# Pipeline utama pengumpulan sinyal
def main():
    lines = ["=== CRYPTO SIGNAL COLLECTOR DIGEST (BINANCE PERP) ==="]
    lines.append("Semua harga dari kontrak perp Binance (USDT), sesuai venue eksekusi user.")
    lines.append(f"Scope: {len(BIG_CAP)} big cap + {len(MID_CAP)} mid cap (10 pairs total).")

    # ---- Phase 0: Order Flow (all pairs) ----
    print("[INFO] Fetching order flow data...", file=sys.stderr)
    for sym in WATCHLIST:
        fetch_orderflow(sym)

    # Print BTC index reference
    btc_price = _data["prices"].get("BTCUSDT", {}).get("price")
    if btc_price:
        btc_24hr = _data["of_24hr"].get("BTCUSDT", {})
        idx = float(btc_24hr.get("weightedAvgPrice", btc_price))
        lines.append(f"BTC index price: ${idx:,.0f} | BTC perp last: ${btc_price:,.1f}")

    lines.append("\n=== FASE 0: ORDER FLOW SCAN (filter awal sebelum SMC) ===")
    flow_rows = []
    all_bps = []

    for sym in WATCHLIST:
        bp = calc_buy_pressure(sym)
        vd = calc_vol_delta(sym)
        funding = _data["fundings"].get(sym, 0.0)
        oi = _data["ois"].get(sym, 0.0)
        # topLongShortAccountRatio mencerminkan rasio akun global (long/short), bukan persentase langsung.
        top_ratio = None
        ls = curl_retry(
            f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={sym}&period=1h&limit=1"
        )
        if isinstance(ls, list) and ls:
            try:
                top_ratio = float(ls[-1].get("longShortRatio", 0))
            except (TypeError, ValueError):
                top_ratio = None
        if top_ratio and top_ratio > 0:
            long_pct = round(100 * top_ratio / (1 + top_ratio), 1)
            short_pct = round(100 - long_pct, 1)

        spread = 0.0
        ba = _data["of_bid_ask"].get(sym)
        if ba:
            spread = (ba[1] - ba[0]) / ba[0] * 100

        flow = classify_flow(bp, vd, long_pct, funding=funding, use_fallback=True)
        flow_rows.append((sym, bp, vd, funding, oi, long_pct, flow))
        all_bps.append(bp)

        vd_str = f"{vd:+.1f}%" if vd is not None else "n/a"
        lines.append(
            f"  {sym:12s} | bp {bp:+5.1f}% | vol Δ6h {vd_str:>7s} | "
            f"funding {funding:+.4f}% | OI {oi:>12,.0f} | "
            f"L={long_pct:5.1f}% | {flow}"
        )

    # Quality check
    non_none_vd = [r[2] for r in flow_rows if r[2] is not None]
    if len(non_none_vd) >= 3:
        unique_vd = set(round(v, 1) for v in non_none_vd)
        if len(unique_vd) <= 2:
            lines.append("\n*** STALE ALERT: vol_delta values nearly identical — possible rate limit ***")
    print(f"\n[INFO] Order flow scan complete, {len(flow_rows)}/{len(WATCHLIST)} pairs OK\n", file=sys.stderr)

    # ---- Phase 1: SMC Structure (all pairs, reuse cached prices where available) ----
    print("[INFO] Fetching SMC kline data (1D/4H)...", file=sys.stderr)
    tf_config = {
        "1d": {"limit": 100, "max_age": 48},
        "4h": {"limit": 100, "max_age": 8},
        # Note: 1h kline already fetched in Phase 0 with 100 bars (enough for EMA50).
        # Skip re-fetch here to avoid overwriting with only 24 bars.
        "1h": {"limit": 60, "max_age": 2, "skip_if_cached": True},
    }

    lines.append("\n=== FASE 1: SMC STRUCTURE (semua 10 pair) ===")
    for sym in WATCHLIST:
        # Use price from orderflow if analysis price not set yet
        if sym not in _data["prices"]:
            lp = _data["of_last_price"].get(sym, 0)
            hr = _data["of_24hr"].get(sym, {})
            wap = float(hr.get("weightedAvgPrice", 0))
            p = lp
            chg = float(hr.get("priceChangePercent", 0)) if hr else 0
            wq = float(hr.get("quoteVolume", 0)) if hr else 0
            _data["prices"][sym] = {"price": p, "chg24h": chg, "vol24_quote": wq,
                                     "index": wap if wap > 0 else p}

        price_info = _data["prices"][sym]
        chg_label = f" | 24h {price_info['chg24h']:+.2f}%" if price_info.get('chg24h') else ""
        fund_label = _data["fundings"].get(sym)
        fund_text = f" | funding {fund_label:+.4f}%" if fund_label is not None else ""

        print(f"\n--- {sym} | perp ${price_info['price']:,.4g}{chg_label}{fund_text} ---", file=sys.stderr)
        lines.append(f"\n--- {sym} | perp ${price_info['price']:,.4g}{chg_label}{fund_text} ---")

        line_parts = []
        for interval, cfg in tf_config.items():
            # Skip if already cached with sufficient bars (1h from Phase 0)
            key = f"{sym}_{interval}"
            existing = _data["klines"].get(key)
            if cfg.get("skip_if_cached") and existing is not None and len(existing["closes"]) >= 60:
                entry = existing
            else:
                entry = fetch_klines(sym, interval, cfg["limit"])
            label = {"1d": "1D", "4h": "4H", "1h": "1H"}[interval]

            if not entry or not fresh_check(f"{sym}_{interval}", cfg["max_age"]):
                parts_line = f"[{label}] n/a"
                if sym not in _data["klines"]:
                    parts_line += " (failed fetch)"
                line_parts.append(parts_line)
                continue

            # Replace last close with ticker price
            closes = entry["closes"][:]  # copy so we don't mutate shared data
            closes[-1] = price_info["price"]
            highs = entry["highs"]
            lows = entry["lows"]
            bars = len(closes)

            e50 = ema(closes[:-1], 50)
            last = closes[-1]
            pos = "above" if e50 and last > e50 else ("below" if e50 else "n/a")

            rng_hi = max(highs[-30:])
            rng_lo = min(lows[-30:])
            if rng_hi == rng_lo:
                pd, zone = 0.5, "equilibrium"
            else:
                pd = (last - rng_lo) / (rng_hi - rng_lo)
                zone = "premium" if pd > 0.6 else ("discount" if pd < 0.4 else "equilibrium")

            struct = structure(highs, lows)
            part = make_tf_label(struct, pos, zone, pd, bars)
            line_parts.append(f"[{label}] {part}")

        for pline in line_parts:
            lines.append(f"  {pline}")

    print("\n[INFO] Full collection complete.", file=sys.stderr)
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
