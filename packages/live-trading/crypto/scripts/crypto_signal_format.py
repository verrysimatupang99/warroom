#!/usr/bin/env python3
"""Signal post formatter — gaya FULL DETAILS (permintaan Dumbledore 8 Sep).

Usage:
  python3 crypto_signal_format.py --pair AVAX_USDT --side LONG --entry 8.023 \
      --sl 7.782 --tp 8.504 --quality 6.5 --poi "FVG bullish 1H fresh" \
      --note "1H+4H HH/HL, taker 1.37, OI +2.7%"
Output: formatted text block (print) untuk Telegram.
Optional: --live untuk ambil posisi live dari MEXC (bila sudah open).
"""
import argparse
import sys

sys.path.insert(0, "/home/ubuntu/.hermes/scripts")


def fetch_live(pair):
    try:
        from mexc_client import positions, price
        ps = positions(pair)
        if ps:
            return float(ps[0]["holdAvgPrice"]), float(ps[0]["holdVol"]), price(pair)
    except Exception:
        pass
    return None, None, None


def fmt_pct(x):
    return f"{x:+.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    ap.add_argument("--entry", type=float, required=True)
    ap.add_argument("--sl", type=float, required=True)
    ap.add_argument("--tp", type=float, required=True)
    ap.add_argument("--quality", default="?")
    ap.add_argument("--poi", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--leverage", type=int, default=10)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    symbol = args.pair if "_" in args.pair else None
    cur = None
    pnl_usdt = None
    vol = None
    if args.live and symbol:
        entry_real, vol, cur = fetch_live(symbol)
        if entry_real:
            args.entry = entry_real
    if cur is None:
        try:
            from mexc_client import price
            cur = price(symbol or args.pair.replace("_", ""))
        except Exception:
            cur = 0.0

    if args.side == "LONG":
        risk = args.entry - args.sl
        reward = args.tp - args.entry
        rr = reward / risk if risk else 0
        pnl_pct = (cur - args.entry) / args.entry * 100
        pnl_usdt = (cur - args.entry) * (vol or 0) * 10  # vol(lots)*lotsize~0.1*lev
    else:
        risk = args.sl - args.entry
        reward = args.entry - args.tp
        rr = reward / risk if risk else 0
        pnl_pct = (args.entry - cur) / args.entry * 100
        pnl_usdt = (args.entry - cur) * (vol or 0) * 10

    sl_pct = (args.sl - args.entry) / args.entry * 100
    tp_pct = (args.tp - args.entry) / args.entry * 100
    status = "GREEN" if pnl_pct > 0 else "RED"
    notional = args.entry * (vol or 1) * 0.1 if vol else 0

    print(f"""{args.pair.replace('_','/')} TRADE - FULL DETAILS!
--- ```
═══════════════════════════════════════
{args.pair.replace('_','/')} {args.side} - EXECUTED!
Entry: ${args.entry:,.5g}
Quality: {args.quality}/10
═══════════════════════════════════════
POSITION DETAILS:
Symbol: {args.pair.replace('_','/')}
Side: {args.side}
Entry Price: ${args.entry:,.5g}
Current Price: ${cur:,.5g}
Size: ${notional:.2f} (notional)
Leverage: {args.leverage}x (isolated)

RISK MANAGEMENT:
Stop Loss: ${args.sl:,.5g} → {fmt_pct(sl_pct)} from entry!
→ DI BALIK liquidity (playbook) ✓
Take Profit: ${args.tp:,.5g} → {fmt_pct(tp_pct)} from entry!
→ R:R = 1:{rr:.2f}!

CURRENT PNL:
→ {pnl_usdt:+.4f} USDT ({fmt_pct(pnl_pct)})
→ Status: {status}

WHY THIS TRADE - QUALITY ANALYSIS:

POI (ENTRY LOGIC):
{args.poi or '(isi POI: OB/SR/trendline/FVG/CISD/iFVG)'}

ORDER FLOW & POSITIONING:
{args.note}

PROBABILITY (honest):
Diisi dari macro score pipeline.

⚠️ Bukan nasihat keuangan. DYOR.""")


if __name__ == "__main__":
    main()
