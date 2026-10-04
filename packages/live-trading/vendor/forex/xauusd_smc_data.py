#!/usr/bin/env python3
"""XAUUSD multi-timeframe SMC data collector — TVC:GOLD (spot CFD) source.

Emits a compact text report (1W / 1D / 4H / 1H / 15M) that a Hermes cron agent
consumes to produce a daily Smart Money Concepts signal.

DATA SOURCE
-----------
TVC:GOLD via the TradingView chart websocket — the spot gold CFD series
(GOLD US$/OZ, type=commodity) that prop firms and CFD brokers quote. This is the
same instrument the user trades, so NO futures-basis conversion is applied and
every level printed here is directly usable on the broker chart.

Previously this script used COMEX GC=F futures, which sit 50-60 points above spot
(contango) and required an error-prone basis subtraction. That is gone.
"""

import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

SYMBOL = "TVC:GOLD"
TV_FEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_feed.py")
PYTHON = sys.executable
UA = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------- fetch layer

def _get_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def fetch_candles(resolution, bars, retries=3):
    """Pull OHLC from TradingView. resolution: '1W','1D','240','60','15'."""
    last_err = None
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                [PYTHON, TV_FEED, SYMBOL, resolution, str(bars)],
                capture_output=True, text=True, timeout=90,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                rows = json.loads(proc.stdout)
                if rows:
                    return rows
            last_err = (proc.stderr or "empty response").strip()[-200:]
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries - 1:
            time.sleep(2)
    raise RuntimeError(f"TVC:GOLD {resolution} fetch failed: {last_err}")


def fetch_quote():
    """Live TVC:GOLD quote + day range from the TradingView scanner endpoint."""
    fields = ["close", "open", "high", "low", "change", "description",
              "price_52_week_high", "price_52_week_low"]
    url = ("https://scanner.tradingview.com/symbol?symbol="
           + SYMBOL.replace(":", "%3A") + "&fields=" + ",".join(fields)
           + "&no_404=true")
    try:
        return _get_json(url, timeout=20)
    except Exception:
        return {}


# ------------------------------------------------------------- indicator math

def ema(values, period):
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes, period=14):
    if len(closes) < period + 2:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def atr(rows, period=14):
    if len(rows) < period + 2:
        return None
    trs = []
    for i in range(1, len(rows)):
        trs.append(max(
            rows[i]["h"] - rows[i]["l"],
            abs(rows[i]["h"] - rows[i - 1]["c"]),
            abs(rows[i]["l"] - rows[i - 1]["c"]),
        ))
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


# ------------------------------------------------------------- SMC structures

def swing_points(rows, left=2, right=2):
    """Fractal swing highs/lows — raw material for BOS/CHoCH detection."""
    highs, lows = [], []
    for i in range(left, len(rows) - right):
        window = rows[i - left:i + right + 1]
        if rows[i]["h"] == max(r["h"] for r in window):
            highs.append((i, rows[i]["h"], rows[i]["t"]))
        if rows[i]["l"] == min(r["l"] for r in window):
            lows.append((i, rows[i]["l"], rows[i]["t"]))
    return highs, lows


def market_structure(rows):
    """Classify structure from the last swing sequence: HH/HL vs LH/LL."""
    highs, lows = swing_points(rows)
    if len(highs) < 2 or len(lows) < 2:
        return "indeterminate", None, None
    last_h, prev_h = highs[-1][1], highs[-2][1]
    last_l, prev_l = lows[-1][1], lows[-2][1]
    if last_h > prev_h and last_l > prev_l:
        label = "BULLISH (HH + HL)"
    elif last_h < prev_h and last_l < prev_l:
        label = "BEARISH (LH + LL)"
    elif last_h > prev_h and last_l < prev_l:
        label = "EXPANDING range (HH + LL)"
    else:
        label = "CONSOLIDATING (LH + HL)"
    return label, (prev_h, last_h), (prev_l, last_l)


def find_fvg(rows, lookback=60, min_size=0.0):
    """Fair Value Gaps: 3-candle pattern where candle 1 and 3 don't overlap.

    Bullish FVG: low[i+1] > high[i-1]  -> unfilled gap below price
    Bearish FVG: high[i+1] < low[i-1]  -> unfilled gap above price
    Only unmitigated gaps are returned.
    """
    out = []
    scan = rows[-lookback:] if len(rows) > lookback else rows
    for i in range(1, len(scan) - 1):
        a, c = scan[i - 1], scan[i + 1]
        if c["l"] > a["h"]:
            lo, hi, kind = a["h"], c["l"], "bullish"
        elif c["h"] < a["l"]:
            lo, hi, kind = c["h"], a["l"], "bearish"
        else:
            continue
        if hi - lo < min_size:
            continue
        filled = any(r["l"] <= hi and r["h"] >= lo for r in scan[i + 2:])
        if not filled:
            out.append({"kind": kind, "lo": lo, "hi": hi, "t": scan[i]["t"]})
    return out[-6:]


def order_blocks(rows, lookback=60):
    """Order blocks: last opposing candle before an impulsive displacement leg."""
    out = []
    scan = rows[-lookback:] if len(rows) > lookback else rows
    bodies = [abs(r["c"] - r["o"]) for r in scan]
    if not bodies:
        return out
    avg_body = sum(bodies) / len(bodies)
    for i in range(1, len(scan) - 1):
        cur, nxt = scan[i], scan[i + 1]
        if abs(nxt["c"] - nxt["o"]) < avg_body * 1.8:
            continue
        if cur["c"] < cur["o"] and nxt["c"] > nxt["o"]:
            out.append({"kind": "bullish OB", "lo": cur["l"], "hi": cur["h"], "t": cur["t"]})
        elif cur["c"] > cur["o"] and nxt["c"] < nxt["o"]:
            out.append({"kind": "bearish OB", "lo": cur["l"], "hi": cur["h"], "t": cur["t"]})
    return out[-6:]


def liquidity_levels(rows, lookback=80, tol=0.6):
    """Equal highs / equal lows — resting liquidity SMC targets for sweeps."""
    scan = rows[-lookback:] if len(rows) > lookback else rows
    highs, lows = swing_points(scan)
    eqh, eql = [], []
    for i in range(len(highs) - 1):
        for j in range(i + 1, len(highs)):
            if abs(highs[i][1] - highs[j][1]) <= tol:
                eqh.append(round((highs[i][1] + highs[j][1]) / 2, 2))
    for i in range(len(lows) - 1):
        for j in range(i + 1, len(lows)):
            if abs(lows[i][1] - lows[j][1]) <= tol:
                eql.append(round((lows[i][1] + lows[j][1]) / 2, 2))
    return sorted(set(eqh))[-4:], sorted(set(eql))[:4]


def premium_discount(rows, lookback=40):
    """Dealing range + equilibrium. SMC: buy discount, sell premium."""
    scan = rows[-lookback:] if len(rows) > lookback else rows
    hi = max(r["h"] for r in scan)
    lo = min(r["l"] for r in scan)
    eq = (hi + lo) / 2
    cur = scan[-1]["c"]
    if hi == lo:
        return hi, lo, eq, "n/a", 0.0
    pct = (cur - lo) / (hi - lo) * 100
    zone = "PREMIUM (sell zone)" if pct > 50 else "DISCOUNT (buy zone)"
    return hi, lo, eq, zone, pct


def session_ranges(m15):
    """Asian / London / NY ranges for today (UTC) — the SMC killzone framework."""
    if not m15:
        return {}
    today = datetime.datetime.utcfromtimestamp(m15[-1]["t"]).date()
    zones = {
        "Asia (00-07 UTC)": (0, 7),
        "London (07-13 UTC)": (7, 13),
        "NY (13-21 UTC)": (13, 21),
    }
    out = {}
    for name, (start, end) in zones.items():
        bars = [
            r for r in m15
            if datetime.datetime.utcfromtimestamp(r["t"]).date() == today
            and start <= datetime.datetime.utcfromtimestamp(r["t"]).hour < end
        ]
        if bars:
            out[name] = {
                "high": max(b["h"] for b in bars),
                "low": min(b["l"] for b in bars),
                "bars": len(bars),
            }
    return out


# ------------------------------------------------------------ econ calendar

CAL_CACHE = "/home/ubuntu/.hermes/cache/ff_calendar_thisweek.json"
CAL_MAX_AGE = 6 * 3600  # the feed rate-limits hard; refresh at most every 6h


def _load_calendar():
    """Weekly calendar with on-disk cache. Stale cache beats no data."""
    cached, cached_age = None, None
    if os.path.exists(CAL_CACHE):
        try:
            cached_age = time.time() - os.path.getmtime(CAL_CACHE)
            with open(CAL_CACHE) as fh:
                cached = json.load(fh)
        except Exception:
            cached, cached_age = None, None

    if cached is not None and cached_age is not None and cached_age < CAL_MAX_AGE:
        return cached, f"cache {cached_age / 3600:.1f}h"

    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    last_err = None
    for attempt in range(3):
        try:
            events = _get_json(url, timeout=20)
            os.makedirs(os.path.dirname(CAL_CACHE), exist_ok=True)
            with open(CAL_CACHE, "w") as fh:
                json.dump(events, fh)
            return events, "live"
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    if cached is not None:
        return cached, f"STALE cache {cached_age / 3600:.1f}h ({type(last_err).__name__})"
    return None, f"unavailable ({type(last_err).__name__}: {last_err})"


def econ_calendar(tz_offset=7):
    """High/medium-impact USD-relevant events for today and tomorrow, in WIB."""
    events, note = _load_calendar()
    if events is None:
        return [
            f"  DATA TIDAK TERSEDIA — {note}",
            "  -> Anggap ada risiko event tak terlihat; cek kalender manual.",
        ]

    today = datetime.datetime.utcnow().date()
    tomorrow = today + datetime.timedelta(days=1)
    watch = {"USD", "ALL", "EUR", "CNY"}
    out = [f"  [source: {note}]"]

    for ev in events:
        impact = str(ev.get("impact", "")).lower()
        if impact not in ("high", "medium"):
            continue
        if str(ev.get("country", "")).upper() not in watch:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ev.get("date", ""))
            utc = dt.astimezone(datetime.timezone.utc)
        except Exception:
            continue
        if utc.date() not in (today, tomorrow):
            continue
        wib = utc + datetime.timedelta(hours=tz_offset)
        day = "TODAY" if utc.date() == today else "TOMORROW"
        flag = "!!!" if impact == "high" else " ! "
        out.append(
            f"  {flag} {day:8s} {wib:%H:%M} WIB  {ev.get('country'):3s}  "
            f"{ev.get('title','')}  (fc {ev.get('forecast') or '-'} / "
            f"prev {ev.get('previous') or '-'})"
        )

    if len(out) == 1:
        out.append("  (no high/medium impact USD events today or tomorrow)")
    return out


# ------------------------------------------------------------------- reporting

def fmt_tf(name, rows, ema_periods=(20, 50), show_bars=6, tf_label=""):
    closes = [r["c"] for r in rows]
    lines = [f"\n### {name}  ({len(rows)} candles)"]

    struct, hpair, lpair = market_structure(rows)
    lines.append(f"Structure: {struct}")
    if hpair:
        lines.append(f"  last two swing highs: {hpair[0]:.2f} -> {hpair[1]:.2f}")
    if lpair:
        lines.append(f"  last two swing lows : {lpair[0]:.2f} -> {lpair[1]:.2f}")

    parts = []
    for p in ema_periods:
        e = ema(closes, p)
        if e:
            parts.append(f"EMA{p}={e:.2f}")
    r = rsi(closes)
    if r:
        parts.append(f"RSI14={r:.1f}")
    a = atr(rows)
    if a:
        parts.append(f"ATR14={a:.2f}")
    if parts:
        lines.append("Indicators: " + "  ".join(parts))

    hi, lo, eq, zone, pct = premium_discount(rows)
    lines.append(
        f"Dealing range: H={hi:.2f} L={lo:.2f} EQ={eq:.2f}"
        f" | price at {pct:.0f}% -> {zone}"
    )

    fvgs = find_fvg(rows)
    if fvgs:
        lines.append("Unmitigated FVG:")
        for f in fvgs:
            d = datetime.datetime.utcfromtimestamp(f["t"]).strftime("%m-%d %H:%M")
            lines.append(f"  {f['kind']:8s} {f['lo']:.2f} - {f['hi']:.2f}   @{d}")

    obs = order_blocks(rows)
    if obs:
        lines.append("Order blocks:")
        for o in obs:
            d = datetime.datetime.utcfromtimestamp(o["t"]).strftime("%m-%d %H:%M")
            lines.append(f"  {o['kind']:11s} {o['lo']:.2f} - {o['hi']:.2f}   @{d}")

    eqh, eql = liquidity_levels(rows)
    if eqh or eql:
        lines.append(f"Liquidity pools: EQH={eqh or '-'}  EQL={eql or '-'}")

    lines.append(f"Last {show_bars} candles (UTC):")
    for r in rows[-show_bars:]:
        d = datetime.datetime.utcfromtimestamp(r["t"]).strftime("%m-%d %H:%M")
        lines.append(
            f"  {d}  O{r['o']:.2f} H{r['h']:.2f} L{r['l']:.2f} C{r['c']:.2f}"
        )
    return "\n".join(lines)


def main():
    now = datetime.datetime.utcnow()
    wib = now + datetime.timedelta(hours=7)

    print("=" * 70)
    print("XAUUSD MULTI-TIMEFRAME SMC DATA PACKET")
    print(f"Generated: {now:%Y-%m-%d %H:%M} UTC  /  {wib:%H:%M} WIB")
    print("=" * 70)

    quote = fetch_quote()
    desc = quote.get("description", "GOLD (US$/OZ)")

    print("\nINSTRUMENT & LIVE PRICE")
    print(f"  Symbol : {SYMBOL}  —  {desc}  (spot gold CFD, NOT futures)")
    if quote.get("close") is not None:
        print(f"  Price  : {quote['close']:.2f}   (change {quote.get('change', 0):+.2f}%)")
        print(f"  Today  : O={quote.get('open')} H={quote.get('high')} L={quote.get('low')}")
    if quote.get("price_52_week_high"):
        print(f"  52wk   : H={quote['price_52_week_high']}  L={quote.get('price_52_week_low')}")
    print("  NOTE   : all levels below are SPOT prices — usable directly on a")
    print("           prop-firm / CFD chart. No basis conversion needed.")

    # 1H is the backbone series; fail loudly if it's unavailable.
    try:
        h1 = fetch_candles("60", 400)
    except Exception as e:
        print(f"\nFATAL: {e}")
        sys.exit(1)

    for label, res, bars, emas, show in [
        ("1W — WEEKLY", "1W", 120, (20, 50), 6),
        ("1D — DAILY", "1D", 300, (20, 50, 200), 8),
        ("4H", "240", 300, (20, 50), 8),
    ]:
        try:
            rows = fetch_candles(res, bars)
            print(fmt_tf(label, rows, ema_periods=emas, show_bars=show))
        except Exception as e:
            print(f"\n### {label}\n  FETCH FAILED: {e}")

    print(fmt_tf("1H", h1, ema_periods=(20, 50, 200), show_bars=10))

    try:
        m15 = fetch_candles("15", 300)
        print(fmt_tf("15M — EXECUTION TF", m15, ema_periods=(9, 21, 50), show_bars=16))
        sr = session_ranges(m15)
        if sr:
            print("\n### TODAY'S SESSION RANGES (UTC)")
            for name, v in sr.items():
                print(
                    f"  {name:20s} H={v['high']:.2f} L={v['low']:.2f}"
                    f"  range={v['high'] - v['low']:.2f}  bars={v['bars']}"
                )
    except Exception as e:
        print(f"\n### 15M\n  FETCH FAILED: {e}")

    print("\n### ECONOMIC CALENDAR (high/medium impact, WIB)")
    for line in econ_calendar():
        print(line)

    print("\n" + "=" * 70)
    print("END OF DATA PACKET")
    print("=" * 70)


if __name__ == "__main__":
    main()
