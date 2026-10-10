#!/usr/bin/env python3
"""Crypto orderflow collector — public OKX swap + recent kline delta (10 Okt).

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

OKX_TICKER = "https://www.okx.com/api/v5/market/ticker?instId={sym}"
OKX_KLINE = "https://www.okx.com/api/v5/market/candles?instId={sym}&bar={iv}&limit={limit}"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate?instId={sym}"


def okx_inst(pair):
    """MEXC "BTC_USDT" / "BTCUSDT" -> OKX "BTC-USDT-SWAP"."""
    p = str(pair).upper().strip()
    if "-" in p:
        return p
    p = p.replace("_", "")
    if p.endswith("USDT") and len(p) > 4:
        return f"{p[:-4]}-USDT-SWAP"
    return p


# OKX bar: 1H/4H/1D dst. Pemanggil lama mengirim "Hour1"/"Min60" gaya MEXC.
_BAR_OKX = {"Min1": "1m", "Min5": "5m", "Min15": "15m", "Min30": "30m",
            "Min60": "1H", "Hour1": "1H", "Hour4": "4H", "Day1": "1D"}


def bar_okx(iv):
    return _BAR_OKX.get(str(iv), str(iv))


def fetch(url, timeout=12):
    out = subprocess.run(["curl", "-s", "--max-time", str(timeout), url],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return {}


def get_ticker(sym):
    d = fetch(OKX_TICKER.format(sym=okx_inst(sym)))
    data = d.get("data") or []
    return data[0] if (str(d.get("code")) == "0" and data) else {}


def get_funding(sym):
    d = fetch(OKX_FUNDING.format(sym=okx_inst(sym)))
    data = d.get("data") or []
    return data[0] if (str(d.get("code")) == "0" and data) else {}


def get_kline(sym, interval, days):
    """Candle OKX. OKX kirim TERBARU DULU (descending) -> dibalik jadi MENAIK,
    sama seperti bentuk MEXC dulu, supaya pemakai di bawah tak perlu diubah."""
    limit = min(100, max(24, days * 24))
    d = fetch(OKX_KLINE.format(sym=okx_inst(sym), iv=bar_okx(interval), limit=limit))
    if str(d.get("code")) != "0":
        return []
    rows = d.get("data") or []
    rows = [r for r in rows if len(r) >= 6]
    rows.sort(key=lambda r: int(r[0]))  # menaik (paling tua dulu)
    return [{"t": int(r[0]), "O": float(r[1]), "H": float(r[2]),
             "L": float(r[3]), "C": float(r[4]), "V": float(r[5])}
            for r in rows]


def oi_delta(sym):
    """Approximate OI delta by using volume surge as proxy. OKX public
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
    bid1 = float(t.get("bidPx", 0) or 0)
    ask1 = float(t.get("askPx", 0) or 0)
    spread = (ask1 - bid1) / bid1 * 100 if bid1 > 0 else 0
    last = float(t.get("last", 0) or 0)
    h24 = float(t.get("high24h", 0) or 0)
    l24 = float(t.get("low24h", 0) or 0)
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

    last = float(t.get("last", 0) or 0)
    h24 = float(t.get("high24h", 0) or 0)
    l24 = float(t.get("low24h", 0) or 0)
    # OKX tak kirim % perubahan; hitung dari open24h (apa adanya, dari 2 angka OKX).
    open24 = float(t.get("open24h", 0) or 0)
    change24 = ((last - open24) / open24 * 100) if open24 > 0 else 0.0
    # OKX tak punya "open interest"/"holdVol" di ticker; biarkan 0 apa adanya.
    oi = 0.0
    vol24 = float(t.get("vol24h", 0) or 0)
    turnover24 = float(t.get("volCcy24h", 0) or 0)
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
