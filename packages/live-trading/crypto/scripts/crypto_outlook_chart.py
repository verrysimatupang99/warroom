#!/usr/bin/env python3
"""Render an outlook chart for BTC/ETH perp BINANCE (dark theme, Telegram-sized).

Pulls daily klines from the Binance Futures API (same source as the signal
collector) and draws candlesticks + EMA50 + key liquidity levels.

Usage:
  crypto_outlook_chart.py --symbol BTC_USDT --levels 80000:res,77500:sup \
      --title "BTCUSDT Outlook" --out /tmp/btc.png

Level spec: price:label-tag pairs, tag in {res,sup}. Repeat --levels freely.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG = "#0d1117"
GRID = "#1f2733"
FG = "#c9d1d9"
UP = "#26a69a"
DOWN = "#ef5350"
C_RES = "#f85149"
C_SUP = "#3fb950"
C_EMA = "#d29922"


def fetch_klines(symbol, interval="Day1", span_days=120):
    # Map MEXC-style interval names to Binance kline intervals
    interval_map = {"Day1": "1d", "Hour4": "4h", "Min60": "1h", "Week1": "1w"}
    binance_interval = interval_map.get(interval, "1d")
    limit = max(span_days // (1 if binance_interval == "1d" else 6), 50)
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={binance_interval}&limit={limit}"
    out = subprocess.run(
        ["curl", "-s", "--max-time", "15", url],
        capture_output=True, text=True, timeout=25,
    ).stdout
    d = json.loads(out)
    if not d or len(d) < 10:
        raise RuntimeError(f"kline failed for {symbol}: returned {len(d)} bars")
    # Binance kline: [open_time_ms, open, high, low, close, vol, ...]
    rows = list(zip(
        [r[0] for r in d],   # open_time (ms)
        [float(r[1]) for r in d],   # open
        [float(r[2]) for r in d],   # high
        [float(r[3]) for r in d],   # low
        [float(r[4]) for r in d],   # close
    ))
    return rows


def ema(values, period=50):
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    out = [None] * (period - 1)
    e = sum(values[:period]) / period
    out.append(e)
    for v in values[period:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def draw(rows, title, levels, out_path):
    # Convert ms to seconds for datetime
    times = [datetime.datetime.utcfromtimestamp(r[0] / 1000) for r in rows]
    opens = [float(r[1]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    closes = [float(r[4]) for r in rows]
    e50 = ema(closes[:-1], 50)

    fig, ax = plt.subplots(figsize=(12, 6.8), facecolor=BG)
    ax.set_facecolor(BG)
    x = range(len(rows))
    w = 0.65
    up_fill = UP
    down_fill = DOWN
    for i in x:
        color = up_fill if closes[i] >= opens[i] else down_fill
        # wick
        ax.vlines(i, lows[i], highs[i], color=color, linewidth=0.9, alpha=0.95)
        # body
        bottom = min(opens[i], closes[i])
        height = max(abs(closes[i] - opens[i]), (max(highs) - min(lows)) * 0.0008)
        ax.add_patch(plt.Rectangle(
            (i - w / 2, bottom), w, height,
            facecolor=color, edgecolor=color, linewidth=0.5,
        ))

    # EMA50 line (aligned so e50[i] is EMA of closes[:i+1] approx)
    xs = [i + 1 for i, v in enumerate(e50) if v is not None]
    ys = [v for v in e50 if v is not None]
    if ys:
        ax.plot(xs, ys, color=C_EMA, linewidth=1.3, label="EMA50", alpha=0.9)

    for price, tag, label in levels:
        color = C_RES if tag == "res" else C_SUP
        ls = "--" if tag == "res" else "-"
        ax.axhline(price, color=color, linestyle=ls, linewidth=1.1, alpha=0.85)
        ax.annotate(
            f" {label} {price:,.0f}",
            xy=(len(rows) - 1, price),
            xytext=(len(rows) + 0.5, price),
            color=color, fontsize=9, va="center", annotation_clip=False,
        )

    last = closes[-1]
    ax.axhline(last, color="#58a6ff", linestyle=":", linewidth=1.2)
    ax.annotate(
        f" LAST ${last:,.0f}", xy=(len(rows) - 1, last),
        xytext=(len(rows) + 0.5, last),
        color="#58a6ff", fontsize=10, fontweight="bold", va="center",
        annotation_clip=False,
    )

    pad = (max(highs) - min(lows)) * 0.06
    ax.set_ylim(min(lows) - pad, max(max(highs), max(p for p, _, _ in levels)) + pad)
    ax.set_xlim(-1, len(rows) + 14)
    step = max(len(rows) // 6, 1)
    ticks = list(range(0, len(rows), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [times[i].strftime("%d %b") for i in ticks],
        color=FG, fontsize=9,
    )
    ax.tick_params(colors=FG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.5, alpha=0.6)
    ax.set_title(title, color=FG, fontsize=13, fontweight="bold", loc="left", pad=12)
    legend = ax.legend(loc="upper left", facecolor=BG, edgecolor=GRID)
    for t in legend.get_texts():
        t.set_color(FG)
    fig.text(
        0.99, 0.01, "source: MEXC perp · auto-generated",
        color="#6e7681", fontsize=7.5, ha="right",
    )
    fig.subplots_adjust(left=0.07, right=0.84, top=0.93, bottom=0.08)
    fig.savefig(out_path, dpi=110, facecolor=BG)
    print(out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--interval", default="Day1")
    p.add_argument("--span", type=int, default=120)
    p.add_argument("--levels", action="append", default=[],
                   help="price:tag:label, tag res|sup")
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    levels = []
    for spec in args.levels:
        parts = spec.split(":")
        price = float(parts[0])
        tag = parts[1] if len(parts) > 1 else "res"
        label = parts[2] if len(parts) > 2 else ("RES" if tag == "res" else "SUP")
        levels.append((price, tag, label))

    rows = fetch_klines(args.symbol, args.interval, args.span)
    draw(rows, args.title, levels, args.out)


if __name__ == "__main__":
    sys.exit(main())
