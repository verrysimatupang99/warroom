#!/usr/bin/env python3
"""Render a crypto outlook chart with TWO panels: 1D (3M) + 4H (30D).
Dark theme, Telegram-sized. Auto-pulls from OKX API, fallback yfinance.

Usage:
  crypto_outlook_chart_v2.py --symbol BTC_USDT --title "BTC Outlook" \
      --levels 80000:res,77500:sup --out /tmp/btc103.png

Level spec: price:tag where tag in {res, sup}. Multiple --levels allowed.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BG = "#0d1117"
GRID = "#1f2733"
FG = "#c9d1d9"
UP = "#22c55e"
DOWN = "#ef4444"
C_RES = "#f85149"
C_SUP = "#3fb950"
C_EMA = "#d29922"
C_EMA2 = "#a78bfa"

YFIN = {"BTC_USDT": "BTC-USD", "ETH_USDT": "ETH-USD", "SOL_USDT": "SOL-USD",
        "BNB_USDT": "BNB-USD", "XRP_USDT": "XRP-USD", "ADA_USDT": "ADA-USD",
        "DOGE_USDT": "DOGE-USD", "AVAX_USDT": "AVAX-USD", "LINK_USDT": "LINK-USD",
        "MATIC_USDT": "MATIC-USD", "DOT_USDT": "DOT-USD", "LTC_USDT": "LTC-USD"}


_BAR_OKX = {"Min1": "1m", "Min5": "5m", "Min15": "15m", "Min30": "30m",
            "Min60": "1H", "Hour1": "1H", "Hour4": "4H", "Day1": "1D"}


def okx_inst(pair):
    """MEXC "BTC_USDT" / "BTCUSDT" -> OKX "BTC-USDT-SWAP" (pengganti MEXC, 10 Okt)."""
    p = str(pair).upper().strip()
    if "-" in p:
        return p
    p = p.replace("_", "")
    if p.endswith("USDT") and len(p) > 4:
        return f"{p[:-4]}-USDT-SWAP"
    return p


def fetch_okx(symbol, interval, span_days):
    """Candle OKX (pengganti MEXC). OKX kirim TERBARU DULU -> dibalik menaik."""
    limit = min(300, max(50, span_days * (24 if interval in ("Min60", "Hour1") else 6)))
    url = (f"https://www.okx.com/api/v5/market/candles?instId={okx_inst(symbol)}"
           f"&bar={_BAR_OKX.get(str(interval), '1H')}&limit={limit}")
    out = subprocess.run(["curl", "-s", "--max-time", "15", url],
                         capture_output=True, text=True, timeout=25).stdout
    d = json.loads(out)
    if str(d.get("code")) != "0":
        return None
    rows = [r for r in (d.get("data") or []) if len(r) >= 6]
    if not rows:
        return None
    rows.sort(key=lambda r: int(r[0]))
    return [{"t": int(r[0]), "O": float(r[1]), "H": float(r[2]),
             "L": float(r[3]), "C": float(r[4]), "V": float(r[5])} for r in rows]


def fetch_yf(symbol, interval, span_days):
    try:
        import yfinance as yf
        t = YFIN.get(symbol, symbol.replace("_", "-"))
        tk = yf.Ticker(t)
        period = f"{span_days}d"
        iv = "1d" if interval == "Day1" else "4h"
        df = tk.history(period=period, interval=iv)
        if df is None or len(df) == 0:
            return None
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "t": int(idx.timestamp()),
                "O": float(row["Open"]), "H": float(row["High"]),
                "L": float(row["Low"]), "C": float(row["Close"]),
                "V": float(row.get("Volume", 0)),
            })
        return candles
    except Exception:
        return None


def fetch(symbol, interval, span_days):
    c = fetch_okx(symbol, interval, span_days)
    if c and len(c) > 5:
        return c
    return fetch_yf(symbol, interval, span_days)


def parse_levels(levels):
    out = []
    for spec in levels:
        price, tag = spec.split(":", 1)
        out.append((float(price), tag.strip().lower()))
    return out


def detect_order_blocks(candles, lookback=8, atr_mult=1.5):
    """SMC Order Block detection.

    Bullish OB (demand): last down-candle before an impulsive UP move (ATR-scaled).
    Bearish OB (supply): last up-candle before an impulsive DOWN move.
    Returns list of dicts: {idx, price_low, price_high, type, strength}.
    """
    if len(candles) < lookback + 2:
        return []
    closes = np.array([c["C"] for c in candles])
    highs = np.array([c["H"] for c in candles])
    lows = np.array([c["L"] for c in candles])
    # ATR
    trs = []
    for i in range(1, len(candles)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    atr = np.mean(trs[-14:]) if len(trs) >= 14 else np.mean(trs)
    obs = []
    # scan each candle as potential "impulse start"
    for i in range(lookback, len(candles) - 1):
        # bullish OB: candle i is a bearish candle (O > C), then next move up >= atr*atr_mult
        if candles[i]["O"] >= candles[i]["C"]:
            move = closes[i + 1] - candles[i]["C"]
            if move >= atr * atr_mult:
                obs.append({
                    "idx": i,
                    "low": candles[i]["L"],
                    "high": candles[i]["O"],
                    "type": "bull",
                    "strength": move / (atr + 1e-9),
                })
        # bearish OB: candle i is bullish (O < C), then next move down <= -atr*atr_mult
        else:
            move = closes[i + 1] - candles[i]["C"]
            if move <= -atr * atr_mult:
                obs.append({
                    "idx": i,
                    "low": candles[i]["C"],
                    "high": candles[i]["H"],
                    "type": "bear",
                    "strength": -move / (atr + 1e-9),
                })
    # keep only unmitigated (price hasn't returned to OB zone since)
    kept = []
    for ob in obs:
        start = ob["idx"]
        end = len(candles)
        if ob["type"] == "bull":
            mitigated = any(lows[j] <= ob["high"] for j in range(start + 1, end))
        else:
            mitigated = any(highs[j] >= ob["low"] for j in range(start + 1, end))
        if not mitigated:
            kept.append(ob)
    # sort by recency, keep last 3
    kept.sort(key=lambda o: o["idx"], reverse=True)
    return kept[:3]


def draw_panel(ax, candles, title, levels, tf_label):
    n = len(candles)
    xs = list(range(n))
    # candles
    for i, c in enumerate(candles):
        color = UP if c["C"] >= c["O"] else DOWN
        ax.plot([i, i], [c["L"], c["H"]], color=color, linewidth=0.8, zorder=2)
        body_low = min(c["O"], c["C"])
        body_high = max(c["O"], c["C"])
        h = max(body_high - body_low, (c["H"] - c["L"]) * 0.02)
        ax.add_patch(Rectangle((i - 0.35, body_low), 0.7, h,
                               facecolor=color, edgecolor=color, zorder=3))
    # EMA
    closes = np.array([c["C"] for c in candles])
    ema20 = pd_ewma(closes, 20)
    ema50 = pd_ewma(closes, 50)
    ax.plot(xs, ema20, color=C_EMA, linewidth=1.4, alpha=0.9, label="EMA20", zorder=4)
    ax.plot(xs, ema50, color=C_EMA2, linewidth=1.4, alpha=0.9, label="EMA50", zorder=4)
    # Order Blocks (SMC)
    obs = detect_order_blocks(candles)
    for ob in obs:
        x0 = ob["idx"] - 0.45
        w = 0.9
        y0 = ob["low"]
        yh = ob["high"]
        if ob["type"] == "bull":
            col = "#16a34a"  # dark green demand
            edge = "#4ade80"
            tag = "OB (demand)"
        else:
            col = "#b91c1c"  # dark red supply
            edge = "#f87171"
            tag = "OB (supply)"
        ax.add_patch(Rectangle((x0, y0), w, max(yh - y0, 1e-6),
                               facecolor=col, edgecolor=edge, alpha=0.35,
                               linewidth=1.2, zorder=1))
        ax.text(x0, yh, tag, color=edge, fontsize=7.5, fontweight="bold",
                ha="left", va="bottom")
    # levels
    hi = max(c["H"] for c in candles)
    lo = min(c["L"] for c in candles)
    for price, tag in levels:
        if tag == "res":
            col = C_RES
            lab = f"RES {price:,.0f}"
        else:
            col = C_SUP
            lab = f"SUP {price:,.0f}"
        ax.axhline(y=price, color=col, linestyle="--", linewidth=1.3, alpha=0.8, zorder=1)
        ax.text(n - 0.5, price, lab, color=col, fontsize=9, fontweight="bold",
                ha="right", va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=col))
    # last price
    last = candles[-1]["C"]
    ax.scatter([n - 1], [last], color=C_EMA, s=80, zorder=5,
               edgecolor=BG, linewidth=1.5)
    # style
    ax.set_facecolor(BG)
    ax.grid(True, alpha=0.12, color=GRID, linestyle="--")
    ax.tick_params(colors=FG, labelsize=8)
    ax.set_title(f"{title}  •  {tf_label}", color=FG, fontsize=11, fontweight="bold", pad=8)
    # x labels every ~10%
    step = max(1, n // 6)
    xt = list(range(0, n, step))
    try:
        xl = [datetime.datetime.fromtimestamp(candles[i]["t"]).strftime("%d/%m") for i in xt]
    except Exception:
        xl = [str(i) for i in xt]
    ax.set_xticks(xt)
    ax.set_xticklabels(xl, color=FG, fontsize=8)
    ax.set_ylim(lo * 0.995, hi * 1.005)
    ax.legend(loc="upper left", facecolor="#1e293b", edgecolor=GRID,
              labelcolor=FG, fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))


def pd_ewma(arr, span):
    try:
        import pandas as pd
        return pd.Series(arr).ewm(span=span, adjust=False).mean().to_numpy()
    except Exception:
        # manual ewma
        a = 2 / (span + 1)
        out = np.zeros_like(arr, dtype=float)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = a * arr[i] + (1 - a) * out[i - 1]
        return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--levels", action="append", default=[],
                   help="price:res|sup, repeatable")
    args = p.parse_args()

    symbol = args.symbol.upper()
    title = args.title or symbol
    levels = parse_levels(args.levels)

    # 1D (3 months) + 4H (30 days)
    d1 = fetch(symbol, "Day1", 90)
    h4 = fetch(symbol, "Hour4", 30)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), facecolor=BG)
    fig.suptitle(f"{title}  •  1D + 4H Outlook", color=FG, fontsize=13,
                 fontweight="bold", y=0.98)

    if d1:
        draw_panel(axes[0], d1, title, levels, "1D (90d)")
    else:
        axes[0].text(0.5, 0.5, "1D data unavailable", color=DOWN, ha="center")
    if h4:
        draw_panel(axes[1], h4, title, levels, "4H (30d)")
    else:
        axes[1].text(0.5, 0.5, "4H data unavailable", color=DOWN, ha="center")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(args.out, dpi=110, facecolor=BG, bbox_inches="tight")
    plt.close()
    print(f"chart saved: {args.out} ({os.path.getsize(args.out)} bytes)")


if __name__ == "__main__":
    main()
