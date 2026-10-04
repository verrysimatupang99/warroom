#!/usr/bin/env python3
"""Render an XAUUSD OUTLOOK chart — SMC structure only, NO trade levels.

Used by the morning briefing and ad-hoc outlook queries. Shows the same SMC
overlays as plot_signal.py (OB, FVG, BOS/CHoCH, EQH/EQL, premium/discount EQ)
but without the entry/SL/TP/BE lines.

Usage:
  plot_outlook.py --tf 1H --bars 120 --out /tmp/outlook_1h.png
  plot_outlook.py --tf 4H --bars 80  --out /tmp/outlook_4h.png
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
TV_FEED = os.path.join(HERE, "tv_feed.py")

BG = "#0d1117"
GRID = "#1f2733"
FG = "#c9d1d9"
UP = "#26a69a"
DOWN = "#ef5350"
C_OB_BULL = "#3fb950"
C_OB_BEAR = "#f85149"
C_FVG_BULL = "#3fb95044"
C_FVG_BEAR = "#f8514944"
C_BOS = "#d29922"
C_BOS_BEAR = "#f85149"
C_EQH = "#a371f7"
C_EQL = "#a371f7"
C_EQM = "#6e7681"
C_TREND = "#58a6ff"


def fetch(resolution, bars):
    proc = subprocess.run(
        [sys.executable, TV_FEED, "TVC:GOLD", resolution, str(bars)],
        capture_output=True, text=True, timeout=90,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"feed failed: {proc.stderr[-200:]}")
    return json.loads(proc.stdout)


def find_swing_highs(rows, lookback=3, max_keep=4):
    out = []
    for i in range(lookback, len(rows) - lookback):
        hi = rows[i]["h"]
        if all(hi >= rows[i - k]["h"] for k in range(1, lookback + 1)) and \
           all(hi >= rows[i + k]["h"] for k in range(1, lookback + 1)) and \
           hi > rows[i]["l"]:
            out.append((i, hi))
    return out[-max_keep:]


def find_swing_lows(rows, lookback=3, max_keep=4):
    out = []
    for i in range(lookback, len(rows) - lookback):
        lo = rows[i]["l"]
        if all(lo <= rows[i - k]["l"] for k in range(1, lookback + 1)) and \
           all(lo <= rows[i + k]["l"] for k in range(1, lookback + 1)) and \
           lo < rows[i]["h"]:
            out.append((i, lo))
    return out[-max_keep:]


def find_swing_structure(rows):
    """Classify recent structure: BULLISH (HH+HL), BEARISH (LH+LL), EXPANDING, RANGING."""
    h = find_swing_highs(rows, lookback=3, max_keep=3)
    l = find_swing_lows(rows, lookback=3, max_keep=3)
    if len(h) < 2 or len(l) < 2:
        return "RANGING", h, l
    hh = h[-1][1] > h[-2][1]
    hl = l[-1][1] > l[-2][1]
    lh = h[-1][1] < h[-2][1]
    ll = l[-1][1] < l[-2][1]
    if hh and hl:
        return "BULLISH", h, l
    if lh and ll:
        return "BEARISH", h, l
    if hh and ll:
        return "EXPANDING", h, l
    if lh and hl:
        return "CONTRACTING", h, l
    return "RANGING", h, l


def find_order_blocks(rows, swings_h, swings_l, max_keep=3):
    """Detect recent bullish/bearish OBs and KEEP ONLY unmitigated, relevant ones.

    SMC rule: an OB is "active" only if price has NOT returned to it after
    formation. A bullish OB is demand -> must sit BELOW current price. A
    bearish OB is supply -> must sit ABOVE current price. OBs the market has
    already traded back through (mitigated) are dropped, and overlapping
    same-type OBs are merged so the chart stays clean.
    """
    last = rows[-1]["c"]
    raw = []
    for sidx, _ in swings_h[-max_keep:]:
        for i in range(sidx - 1, max(0, sidx - 6), -1):
            r = rows[i]
            if r["c"] < r["o"]:
                top, bot = max(r["o"], r["c"]), min(r["o"], r["c"])
                raw.append((i, top, bot, "bull"))
                break
    for sidx, _ in swings_l[-max_keep:]:
        for i in range(sidx - 1, max(0, sidx - 6), -1):
            r = rows[i]
            if r["c"] > r["o"]:
                top, bot = max(r["o"], r["c"]), min(r["o"], r["c"])
                raw.append((i, top, bot, "bear"))
                break

    # Mitigation check: setelah candle OB, apakah HARGA (wick) sudah masuk zona?
    # SMC: sentuhan wick = mitigasi. Sebelumnya cuma pakai close → zona mati
    # masih kebaca "aktif" (bug koreksi 25 Sep, req Dumbledore).
    kept = []
    for idx, top, bot, kind in raw:
        mitigated = False
        for j in range(idx + 1, len(rows)):
            c = rows[j]
            if kind == "bull" and c["l"] <= top:      # wick turun masuk bull OB
                mitigated = True
                break
            if kind == "bear" and c["h"] >= bot:      # wick naik masuk bear OB
                mitigated = True
                break
        if mitigated:
            continue
        # relevance: bull OB must be below price (demand), bear OB above (supply)
        if kind == "bull" and bot >= last:
            continue
        if kind == "bear" and top <= last:
            continue
        kept.append((idx, top, bot, kind))

    # Merge overlapping same-type OBs
    merged = []
    for idx, top, bot, kind in sorted(kept, key=lambda x: x[1]):
        if merged and merged[-1][3] == kind and bot <= merged[-1][2] + 1:
            lo = min(merged[-1][1], top)
            hi = max(merged[-1][2], bot)
            merged[-1] = (merged[-1][0], lo, hi, kind)
        else:
            merged.append((idx, top, bot, kind))

    # Keep at most 3 (2 below, 1 above or vice versa) — most relevant
    return merged[:4]


def find_fvgs(rows, max_keep=4):
    """FVG + deteksi inversion (iFVG).

    Zona yang sudah terisi (harga pernah masuk) TIDAK lagi imbalance: statusnya
    flip jadi iFVG — bull FVG yang filled = supply (resistance), bear FVG yang
    filled = demand (support). Tanpa ini chart bikin salah baca (koreksi 25 Sep).
    Output tuple tetap: (idx, top, bot, kind, filled, inverted)
    """
    fvgs = []
    for i in range(2, len(rows)):
        a, c = rows[i - 2], rows[i]
        if c["l"] > a["h"]:
            fvgs.append((i - 1, c["l"], a["h"], "bull"))
        elif c["h"] < a["l"]:
            fvgs.append((i - 1, a["l"], c["h"], "bear"))
    # keep only most recent + merge overlaps
    fvgs = fvgs[-max_keep * 2:]
    merged = []
    for idx, top, bot, kind in sorted(fvgs, key=lambda x: x[1]):
        if merged and merged[-1][3] == kind and bot <= merged[-1][2] + 1:
            merged[-1] = (merged[-1][0], min(merged[-1][1], top),
                          max(merged[-1][2], bot), kind)
        else:
            merged.append((idx, top, bot, kind))

    out = []
    last = rows[-1]["c"]
    for idx, top, bot, kind in merged[-max_keep:]:
        # filled? harga pernah masuk zona setelah terbentuk
        filled = False
        for j in range(idx + 2, len(rows)):
            if rows[j]["l"] <= top and rows[j]["h"] >= bot:
                filled = True
                break
        # inverted hanya kalau filled DAN harga sudah keluar sisi seberangnya
        inverted = False
        if filled:
            if kind == "bull" and last < bot:     # bull FVG di atas harga → supply
                inverted = True
            elif kind == "bear" and last > top:   # bear FVG di bawah harga → demand
                inverted = True
        out.append((idx, top, bot, kind, filled, inverted))
    return out


def find_eqh_eql(rows, tolerance=0.5, lookback=60, max_keep=2):
    eqh, eql = [], []
    recent = rows[-lookback:]
    for i in range(2, len(recent)):
        for j in range(i - 1, max(0, i - 4), -1):
            if abs(recent[i]["h"] - recent[j]["h"]) <= tolerance:
                eqh.append((len(rows) - lookback + i, recent[i]["h"]))
                break
        for j in range(i - 1, max(0, i - 4), -1):
            if abs(recent[i]["l"] - recent[j]["l"]) <= tolerance:
                eql.append((len(rows) - lookback + i, recent[i]["l"]))
                break
    return eqh[-max_keep:], eql[-max_keep:]


def find_bos_choch(rows, swings_h, swings_l, max_keep=4):
    """Return [(idx, label, price, kind)] — kind in {BOS, CHoCH}.

    ICT-correct semantics:
      BOS (Break of Structure) = price breaks a prior swing in the TREND
        direction. Line is drawn at the level of the swing that got broken.
          - uptrend + new high > prior high -> BOS up at the PRIOR HIGH (a high)
          - downtrend + new low < prior low  -> BOS down at the PRIOR LOW (a low)
      CHoCH (Change of Character) = price breaks a prior swing AGAINST the
        trend, signalling reversal. Line drawn at the level that, once broken,
        confirms the reversal.
          - uptrend + lower high (LH) -> CHoCH down at the PRIOR LOW (a low)
          - downtrend + higher low (HL) -> CHoCH up at the PRIOR HIGH (a high)

    CONSEQUENCE (the bug we fixed): an up-arrow line is ALWAYS at a HIGH level
    (above), and a down-arrow line is ALWAYS at a LOW level (below). Never the
    inverse.
    """
    events = []
    if len(swings_h) < 2 and len(swings_l) < 2:
        return events
    all_swings = sorted(
        [(i, "H", p) for i, p in swings_h] +
        [(i, "L", p) for i, p in swings_l],
        key=lambda x: x[0]
    )
    if len(all_swings) < 2:
        return events
    last_h = all_swings[0][2] if all_swings[0][1] == "H" else None
    last_l = all_swings[0][2] if all_swings[0][1] == "L" else None
    last_h_idx = all_swings[0][0] if all_swings[0][1] == "H" else None
    last_l_idx = all_swings[0][0] if all_swings[0][1] == "L" else None
    prev_dir = None
    for i, kind, price in all_swings[1:]:
        if kind == "H":
            if last_h is None:
                last_h, last_h_idx = price, i
                continue
            if price > last_h:
                # broke ABOVE prior high -> continuation up, line at that high
                events.append((last_h_idx, "BOS up", last_h, "BOS"))
                prev_dir = "UP"
            else:
                # lower high: if we were up, first crack -> CHoCH down at prior LOW
                if prev_dir == "UP":
                    events.append((last_l_idx, "CHoCH down", last_l, "CHoCH"))
                prev_dir = "DOWN"
            last_h, last_h_idx = price, i
        else:
            if last_l is None:
                last_l, last_l_idx = price, i
                continue
            if price < last_l:
                # broke BELOW prior low -> continuation down, line at that low
                events.append((last_l_idx, "BOS down", last_l, "BOS"))
                prev_dir = "DOWN"
            else:
                # higher low: if we were down, first crack -> CHoCH up at prior HIGH
                if prev_dir == "DOWN":
                    events.append((last_h_idx, "CHoCH up", last_h, "CHoCH"))
                prev_dir = "UP"
            last_l, last_l_idx = price, i
    return events[-max_keep:]

def draw(rows, args):
    fig, ax = plt.subplots(figsize=(13, 7.4), facecolor=BG)
    ax.set_facecolor(BG)

    n = len(rows)
    width = 0.62

    for i, r in enumerate(rows):
        up = r["c"] >= r["o"]
        col = UP if up else DOWN
        ax.plot([i, i], [r["l"], r["h"]], color=col, linewidth=0.9,
                solid_capstyle="round", zorder=3)
        lo, hi = min(r["o"], r["c"]), max(r["o"], r["c"])
        h = max(hi - lo, 0.01)
        ax.add_patch(Rectangle((i - width / 2, lo), width, h,
                               facecolor=col, edgecolor=col, linewidth=0.5,
                               zorder=4))

    x0, x1 = -1, n + 14

    structure, swings_h, swings_l = find_swing_structure(rows)
    obs = find_order_blocks(rows, swings_h, swings_l)
    fvgs = find_fvgs(rows)
    eqh, eql = find_eqh_eql(rows)
    events = find_bos_choch(rows, swings_h, swings_l)

    # Order block zones (extend right edge so visible)
    for idx, top, bot, kind in obs:
        col = C_OB_BULL if kind == "bull" else C_OB_BEAR
        ax.add_patch(Rectangle((idx, min(top, bot)), x1 - idx,
                               abs(top - bot),
                               facecolor=col, alpha=0.18, zorder=1,
                               edgecolor=col, linewidth=0.7))
        ax.text(idx + 0.3, (top + bot) / 2,
                f"{'BULL' if kind == 'bull' else 'BEAR'} OB {min(top, bot):.2f}-{max(top, bot):.2f}",
                color=col, fontsize=6.3, fontweight="bold",
                va="center", ha="left", zorder=7)

    # FVG rectangles — zona filled dilabeli iFVG (status flip) supaya tidak
    # disalahbaca sebagai demand/supply yang masih aktif.
    for idx, top, bot, kind, filled, inverted in fvgs:
        if inverted:
            col = C_OB_BEAR if kind == "bull" else C_OB_BULL
            tag = "iFVG->SUPPLY" if kind == "bull" else "iFVG->DEMAND"
            alpha = 0.14
        else:
            col = C_FVG_BULL if kind == "bull" else C_FVG_BEAR
            tag = "FVG"
            alpha = 0.20
        ax.add_patch(Rectangle((idx, min(top, bot)), x1 - idx,
                               abs(top - bot),
                               facecolor=col, alpha=alpha, zorder=1))
        mid = (top + bot) / 2
        suffix = "" if not filled else (" · filled" if not inverted else "")
        ax.text(idx + 0.3, mid, f"{tag} {min(top, bot):.2f}-{max(top, bot):.2f}{suffix}",
                color=col, fontsize=6.0, fontweight="bold",
                va="center", ha="left", zorder=7)

    # BOS / CHoCH — subtle line at broken swing level, short tail + small label.
    for idx, label, price, kind in events:
        if idx is None:
            continue
        is_up = "up" in label
        col = "#3fb950" if is_up else "#f85149"
        ls = "-" if kind == "BOS" else "--"
        x_end = min(idx + 8, n - 1)
        ax.plot([idx, x_end], [price, price], color=col, linewidth=0.9,
                linestyle=ls, alpha=0.75, zorder=6)
        ax.annotate(label, xy=(x_end, price), xytext=(x_end + 0.3, price),
                    color=col, fontsize=6, va="center", ha="left", zorder=8)

    # EQH / EQL liquidity — subtle anchored line + small label
    for idx, price in eqh:
        ax.plot([idx, x1], [price, price], color=C_EQH, linestyle=":",
                linewidth=0.9, alpha=0.7, zorder=2)
        ax.annotate(f"EQH {price:.2f}", xy=(idx, price),
                    xytext=(idx - 1, price + price * 0.0008),
                    color=C_EQH, fontsize=6.5, va="bottom", ha="right",
                    zorder=7)
    for idx, price in eql:
        ax.plot([idx, x1], [price, price], color=C_EQL, linestyle=":",
                linewidth=0.9, alpha=0.7, zorder=2)
        ax.annotate(f"EQL {price:.2f}", xy=(idx, price),
                    xytext=(idx - 1, price - price * 0.0008),
                    color=C_EQL, fontsize=6.5, va="top", ha="right",
                    zorder=7)

    # Premium / discount midpoint
    h_max = max(r["h"] for r in rows)
    l_min = min(r["l"] for r in rows)
    eqm = (h_max + l_min) / 2
    ax.axhline(eqm, color=C_EQM, linestyle="--", linewidth=0.9, alpha=0.6, zorder=1)
    ax.text(x1, eqm, f" EQM {eqm:.2f} (premium/discount midpoint)",
            color=C_EQM, fontsize=8.5, va="center", ha="left", zorder=7)

    # Premium / discount shaded zones
    last = rows[-1]["c"]
    if last > eqm:
        ax.text(x1 + 1, h_max - (h_max - eqm) * 0.3, "PREMIUM",
                color="#f85149", fontsize=9, fontweight="bold", alpha=0.55, zorder=7)
    else:
        ax.text(x1 + 1, l_min + (eqm - l_min) * 0.3, "DISCOUNT",
                color="#3fb950", fontsize=9, fontweight="bold", alpha=0.55, zorder=7)

    # Current price marker
    ax.axhline(last, color=C_TREND, linestyle="-", linewidth=1.0, alpha=0.9, zorder=8)
    ax.text(x1 + 1, last, f" {last:,.2f}", color=C_TREND, fontsize=10.5,
            fontweight="bold", va="center", ha="left", zorder=8)

    # X axis
    step = max(1, n // 10)
    ticks, labels = [], []
    for i in range(0, n, step):
        ticks.append(i)
        dt = datetime.datetime.utcfromtimestamp(rows[i]["t"]) + datetime.timedelta(hours=7)
        labels.append(dt.strftime("%d/%m\n%H:%M"))
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color=FG, fontsize=8.5)

    ax.set_xlim(x0, x1 + 11)
    pad = (h_max - l_min) * 0.08
    ax.set_ylim(l_min - pad, h_max + pad)
    ax.tick_params(colors=FG, labelsize=9)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.55, zorder=0)
    ax.yaxis.tick_left()

    # Title + structure badge
    structure_col = {
        "BULLISH": "#3fb950", "BEARISH": "#f85149",
        "EXPANDING": "#d29922", "CONTRACTING": "#a371f7",
        "RANGING": "#6e7681"
    }.get(structure, "#c9d1d9")
    ax.set_title(
        f"XAUUSD  ·  TVC:GOLD (spot)  ·  {args.tf}  ·  OUTLOOK (SMC only — no trade levels)",
        color=FG, fontsize=14, fontweight="bold", loc="left", pad=20,
    )
    ax.text(1.0, 1.02, structure, transform=ax.transAxes, color=structure_col,
            fontsize=14, fontweight="bold", ha="right", va="bottom")
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    ax.text(1.0, -0.08, now.strftime("%d %b %Y  %H:%M WIB"),
            transform=ax.transAxes, color="#6e7681", fontsize=9,
            ha="right", va="top")

    # Legend
    legend_items = [
        Line2D([0], [0], color=C_OB_BULL, lw=4, alpha=0.5, label="Bullish OB (demand)"),
        Line2D([0], [0], color=C_OB_BEAR, lw=4, alpha=0.5, label="Bearish OB (supply)"),
        Line2D([0], [0], color=C_FVG_BULL, lw=4, alpha=0.5, label="FVG / imbalance (aktif)"),
        Line2D([0], [0], color=C_OB_BEAR, lw=4, alpha=0.35, label="iFVG (filled - flip supply/demand)"),
        Line2D([0], [0], color="#3fb950", lw=2, label="BOS/CHoCH up (green)"),
        Line2D([0], [0], color="#f85149", lw=2, linestyle="--", label="BOS/CHoCH down (red)"),
        Line2D([0], [0], color=C_EQH, linestyle=":", lw=1.5, label="EQH / EQL (liquidity)"),
        Line2D([0], [0], color=C_TREND, lw=1.5, label="Live price"),
    ]
    ax.legend(handles=legend_items, loc="lower left", facecolor=BG,
              edgecolor=GRID, labelcolor=FG, fontsize=9, framealpha=0.9, ncol=3)

    if args.note:
        ax.text(0.005, -0.10, args.note, transform=ax.transAxes,
                color="#8b949e", fontsize=9, va="top", ha="left")

    fig.tight_layout()
    fig.savefig(args.out, dpi=130, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tf", default="1H", choices=["15M", "1H", "4H", "1D"])
    p.add_argument("--bars", type=int, default=120)
    p.add_argument("--note", default="")
    p.add_argument("--out", default="/tmp/xauusd_outlook.png")
    args = p.parse_args()

    res = {"15M": "15", "1H": "60", "4H": "240", "1D": "1D"}.get(args.tf.upper(), "60")
    rows = fetch(res, max(args.bars, 60))
    rows = rows[-args.bars:]
    draw(rows, args)
    print(args.out)


if __name__ == "__main__":
    main()
