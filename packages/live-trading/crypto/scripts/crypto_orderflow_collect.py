#!/usr/bin/env python3
"""Crypto orderflow collector — public MEXC perp + recent kline delta.

Output JSON: {symbol, last, change_24h, oi, oi_delta_24h, volume_24h,
turnover_24h, funding, long_short_bias, taker_buy_sell_ratio, range_24h, ...}

Usage:
  crypto_orderflow_collect.py --symbol SOL_USDT
"""
import argparse
import json
import os
import subprocess
import sys
import time

MEXC_TICKER = "https://contract.mexc.com/api/v1/contract/ticker?symbol={sym}"
MEXC_KLINE = "https://contract.mexc.com/api/v1/contract/kline/{sym}?interval={iv}&start={s}&end={e}"
MEXC_FUNDING = "https://contract.mexc.com/api/v1/contract/funding_rate/{sym}"


def fetch(url, timeout=12):
    out = subprocess.run(["curl", "-s", "--max-time", str(timeout), url],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return {}


def get_ticker(sym):
    d = fetch(MEXC_TICKER.format(sym=sym))
    return d.get("data", {}) if d.get("success") else {}


def get_funding(sym):
    d = fetch(MEXC_FUNDING.format(sym=sym))
    if d.get("success") and "data" in d:
        data = d["data"]
        if isinstance(data, list) and data:
            return data[0]
    return {}


def get_kline(sym, interval, days):
    now = int(time.time())
    d = fetch(MEXC_KLINE.format(sym=sym, iv=interval, s=now - days * 86400, e=now))
    if not d.get("success"):
        return []
    data = d["data"]
    if not isinstance(data, dict):
        return []
    times = data.get("time", [])
    opens = data.get("open", [])
    highs = data.get("high", [])
    lows = data.get("low", [])
    closes = data.get("close", [])
    vols = data.get("vol", [])
    if not (times and closes and len(times) == len(closes)):
        return []
    return [{"t": int(times[i]), "O": float(opens[i]), "H": float(highs[i]),
             "L": float(lows[i]), "C": float(closes[i]), "V": float(vols[i])}
            for i in range(len(times))]


def oi_delta(sym):
    """Approximate OI delta by using volume surge as proxy. MEXC public
    doesn't expose OI history, so we use turnover acceleration as a signal
    of new contracts opening. Also use Taker buy/sell ratio from depth.
    """
    h1 = get_kline(sym, "Hour1", 2)
    if len(h1) < 24:
        return None
    # compare last 6h volume vs prior 18h
    last6 = sum(c["V"] for c in h1[-6:])
    prior18 = sum(c["V"] for c in h1[-24:-6])
    delta_vol_pct = (last6 - prior18) / prior18 * 100 if prior18 > 0 else 0
    return delta_vol_pct


def depth_proxy(sym):
    """Use bid/ask spread as a proxy for liquidity. Tighter = more liquid.
    From ticker: bid1, ask1 are the best bid/ask. We also approximate
    taker buy/sell pressure from last-hour price action vs 24h mid.
    """
    t = get_ticker(sym)
    if not t:
        return {}
    bid1 = float(t.get("bid1", 0))
    ask1 = float(t.get("ask1", 0))
    spread = (ask1 - bid1) / bid1 * 100 if bid1 > 0 else 0
    last = float(t.get("lastPrice", 0))
    h24 = float(t.get("high24Price", 0))
    l24 = float(t.get("lower24Price", 0))
    mid24 = (h24 + l24) / 2
    # Position of last vs 24h mid: >0 means buy pressure, <0 means sell pressure
    buy_pressure = (last - mid24) / (h24 - l24) * 100 if h24 > l24 else 0
    return {
        "bid1": bid1, "ask1": ask1, "spread_pct": spread,
        "buy_pressure_pct": buy_pressure,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    args = p.parse_args()
    sym = args.symbol.upper()
    t = get_ticker(sym)
    if not t:
        print("ERROR: ticker fetch failed", file=sys.stderr)
        sys.exit(1)
    f = get_funding(sym)
    d = depth_proxy(sym)
    vol_delta = oi_delta(sym)

    last = float(t.get("lastPrice", 0))
    h24 = float(t.get("high24Price", 0))
    l24 = float(t.get("lower24Price", 0))
    change24 = float(t.get("riseFallRate", 0)) * 100
    oi = float(t.get("holdVol", 0))
    vol24 = float(t.get("volume24", 0))
    turnover24 = float(t.get("amount24", 0))
    funding = float(f.get("fundingRate", t.get("fundingRate", 0)) or 0) * 100
    next_funding = f.get("nextSettleTime", "N/A")

    # Compute sign of OI (using volume as proxy)
    oi_sign_text = "Δ +" if vol_delta and vol_delta > 5 else ("Δ " if vol_delta and vol_delta > -5 else "Δ -")
    oi_delta_text = f"{vol_delta:+.1f}%" if vol_delta is not None else "n/a"

    # Orderflow interpretation
    flow = "NEUTRAL"
    if d.get("buy_pressure_pct", 0) > 30 and vol_delta and vol_delta > 10:
        flow = "🟢 AGGRESSIVE BUY (volume + price upper-half)"
    elif d.get("buy_pressure_pct", 0) > 15:
        flow = "🟢 Mild buy pressure"
    elif d.get("buy_pressure_pct", 0) < -30 and vol_delta and vol_delta < -10:
        flow = "🔴 AGGRESSIVE SELL"
    elif d.get("buy_pressure_pct", 0) < -15:
        flow = "🔴 Mild sell pressure"

    summary = {
        "symbol": sym,
        "last": last,
        "change_24h_pct": change24,
        "range_24h": {"high": h24, "low": l24, "mid": (h24 + l24) / 2},
        "open_interest": oi,
        "volume_24h": vol24,
        "turnover_24h_usd": turnover24,
        "funding_rate_pct": funding,
        "next_funding_at": next_funding,
        "volume_delta_6h_vs_18h_pct": vol_delta,
        "orderbook": {
            "bid1": d.get("bid1"),
            "ask1": d.get("ask1"),
            "spread_pct": d.get("spread_pct"),
        },
        "taker_buy_sell_proxy": {
            "buy_pressure_pct": d.get("buy_pressure_pct"),
            "interpretation": flow,
        },
    }

    # Human digest
    print(f"=== ORDERFLOW DIGEST — {sym} ===")
    print(f"Last: {last:.4f} ({change24:+.2f}% 24h)")
    print(f"Range 24h: H={h24:.4f} L={l24:.4f} Mid={(h24+l24)/2:.4f}")
    print(f"Open Interest: {oi:,.0f} contracts")
    print(f"Volume 24h: {vol24:,.0f} | Turnover ${turnover24:,.0f}")
    print(f"Funding rate: {funding:+.4f}% | Next settle: {next_funding}")
    print(f"Volume Δ (6h vs prior 18h): {oi_delta_text}  {oi_sign_text}")
    print(f"Bid/Ask: {d.get('bid1'):.4f} / {d.get('ask1'):.4f} (spread {d.get('spread_pct'):.3f}%)")
    print(f"Taker buy/sell proxy: buy_pressure={d.get('buy_pressure_pct'):.1f}% → {flow}")
    print()
    print("---JSON---")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
