#!/usr/bin/env python3
"""Trade journal + outcome tracker for the XAUUSD SMC daily signal.

Records every signal issued, then resolves its real outcome against TVC:GOLD
price history so the signal quality can be evaluated instead of guessed at.

Commands
--------
  add     Record a new signal (called by the signal cron job)
  track   Resolve open trades against price history (called by the tracker cron)
  report  Print performance statistics
  list    Print recent journal entries

Outcome model
-------------
A signal starts PENDING (limit order not yet filled). Once price trades into the
entry it becomes ACTIVE. From there the resolution is deliberately CONSERVATIVE:

  * If a single candle's range contains both SL and a TP, SL is assumed to have
    hit first. Real 15m candles hide their internal path, and assuming the good
    outcome would inflate the win rate.
  * BE (break-even) is honoured at BE_TRIGGER_R (1.2R): once max favorable
    excursion reaches 1.2R the stop is treated as moved to entry, so a later
    reversal resolves as BE (0R) rather than a full loss. TP1 acts as a 50%
    partial close (+0.5R locked), remainder runs to TP2 (rule v2, 21 Sep 2026).
  * PENDING trades expire after PENDING_TTL_HOURS without a fill (CANCELLED).
  * ACTIVE trades that hit neither level within ACTIVE_TTL_HOURS are closed at
    the last price as EXPIRED, with the R multiple actually achieved.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TV_FEED = os.path.join(HERE, "tv_feed.py")
JOURNAL = os.path.expanduser("~/.hermes/trading-journal/xauusd_journal.json")

PENDING_TTL_HOURS = 24
ACTIVE_TTL_HOURS = 48

# ---- Rule v2 (reset 21 Sep 2026) ----------------------------------------
# BE baru di-arm saat posisi sudah mencapai 1.2R (bukan saat TP1 hit).
# Alasan: 2 dari 9 signal lama peak +1R+ lalu berbalik jadi BE 0R.
BE_TRIGGER_R = 1.2


# ------------------------------------------------------------------ storage

def load():
    if not os.path.exists(JOURNAL):
        return {"trades": []}
    try:
        with open(JOURNAL) as fh:
            return json.load(fh)
    except Exception:
        # never lose the file to a parse error
        os.rename(JOURNAL, JOURNAL + ".corrupt")
        return {"trades": []}


def save(data):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    tmp = JOURNAL + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, JOURNAL)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def wib(dt):
    return dt + datetime.timedelta(hours=7)


# ------------------------------------------------------------------- feed

def fetch(resolution="15", bars=400):
    proc = subprocess.run(
        [sys.executable, TV_FEED, "TVC:GOLD", resolution, str(bars)],
        capture_output=True, text=True, timeout=90,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"feed failed: {(proc.stderr or '')[-200:]}")
    return json.loads(proc.stdout)


# -------------------------------------------------------------------- add

def cmd_add(args):
    data = load()
    ts = now_utc()

    risk = abs(args.entry - args.sl)
    if risk <= 0:
        print("ERROR: entry and SL are identical")
        return 1

    # Record the market price at signal time so the tracker can tell a LIMIT
    # order (entry beyond price) from a STOP order (entry through price).
    price_at_signal = args.price
    if price_at_signal is None:
        try:
            price_at_signal = fetch("15", 3)[-1]["c"]
        except Exception:
            price_at_signal = None

    trade = {
        "id": ts.strftime("%Y%m%d-%H%M%S"),
        "created_utc": ts.isoformat(timespec="seconds"),
        "date_wib": wib(ts).strftime("%Y-%m-%d %H:%M"),
        "side": args.side.upper(),
        "entry": args.entry,
        "sl": args.sl,
        "tp1": args.tp1,
        "tp2": args.tp2,
        "be": args.be,
        "price_at_signal": price_at_signal,
        "risk_points": round(risk, 2),
        "rr_tp1": round(abs(args.tp1 - args.entry) / risk, 2),
        "rr_tp2": round(abs(args.tp2 - args.entry) / risk, 2) if args.tp2 else None,
        "bias": args.bias or "",
        "poi": args.poi or "",
        "session": args.session or "",
        "style": args.style or "",
        "status": "PENDING",
        "filled_utc": None,
        "resolved_utc": None,
        "outcome": None,
        "r_multiple": None,
        "max_favorable_r": 0.0,
        "be_armed": False,
        "notes": [],
    }

    # guard against a duplicate signal on the same calendar day
    today = wib(ts).strftime("%Y-%m-%d")
    same_day = [t for t in data["trades"]
                if str(t.get("date_wib", "")).startswith(today)]
    if same_day and not args.force:
        print(f"SKIP: a trade already exists for {today} "
              f"({same_day[-1]['id']}, status {same_day[-1]['status']}). "
              f"Use --force to override.")
        return 2

    data["trades"].append(trade)
    save(data)
    print(f"RECORDED {trade['id']}  {trade['side']} @ {trade['entry']} "
          f"SL {trade['sl']} TP1 {trade['tp1']} "
          f"(risk {trade['risk_points']} pts, RR {trade['rr_tp1']})")
    return 0


# ------------------------------------------------------------------ track

def _resolve(trade, candles):
    """Walk candles chronologically and update the trade in place.

    Returns True when the trade's state changed.
    """
    changed = False
    long = trade["side"] == "BUY"
    entry, sl = trade["entry"], trade["sl"]
    tp1, tp2, be = trade["tp1"], trade["tp2"], trade["be"]
    risk = abs(entry - sl)

    created = datetime.datetime.fromisoformat(trade["created_utc"])
    bars = [c for c in candles
            if datetime.datetime.fromtimestamp(c["t"], datetime.timezone.utc) >= created]

    # Order semantics depend on where price sat when the signal was issued.
    # A BUY below market is a LIMIT (fills on a dip); above market it is a STOP
    # (fills on a breakout). Without this the fill test `low <= entry` marks a
    # breakout order filled instantly, because price is by definition below it.
    ref = trade.get("price_at_signal")
    if ref is None and bars:
        ref = bars[0]["o"]
    if ref is None:
        return False
    if long:
        is_limit = entry <= ref
    else:
        is_limit = entry >= ref

    for c in bars:
        ct = datetime.datetime.fromtimestamp(c["t"], datetime.timezone.utc)
        hi, lo = c["h"], c["l"]

        if trade["status"] == "PENDING":
            if long:
                touched = (lo <= entry) if is_limit else (hi >= entry)
            else:
                touched = (hi >= entry) if is_limit else (lo <= entry)
            if touched:
                trade["status"] = "ACTIVE"
                trade["filled_utc"] = ct.isoformat(timespec="seconds")
                trade["notes"].append(f"filled {wib(ct):%m-%d %H:%M} WIB")
                changed = True
            else:
                age = (ct - created).total_seconds() / 3600
                if age > PENDING_TTL_HOURS:
                    trade["status"] = "CANCELLED"
                    trade["outcome"] = "NO FILL"
                    trade["r_multiple"] = 0.0
                    trade["resolved_utc"] = ct.isoformat(timespec="seconds")
                    trade["notes"].append("expired without fill")
                    return True
                continue

        if trade["status"] != "ACTIVE":
            break

        hit_sl = (lo <= sl) if long else (hi >= sl)
        hit_tp1 = (hi >= tp1) if long else (lo <= tp1)
        hit_tp2 = (tp2 is not None) and ((hi >= tp2) if long else (lo <= tp2))
        hit_be = (be is not None) and ((hi >= be) if long else (lo <= be))

        # Only credit a favourable excursion when this candle did NOT stop us
        # out. Otherwise a single wide candle reports a peak the trade never
        # actually banked, which flatters the "sempat +1R" diagnostics.
        if not hit_sl:
            fav = (hi - entry) if long else (entry - lo)
            r_fav = fav / risk if risk else 0
            if r_fav > trade["max_favorable_r"]:
                trade["max_favorable_r"] = round(r_fav, 2)
                changed = True

        # CONSERVATIVE: when SL shares a candle with a TP, assume SL first.
        if hit_sl:
            if trade["be_armed"]:
                trade["status"] = "CLOSED"
                trade["outcome"] = "BE"
                trade["r_multiple"] = 0.0
                trade["notes"].append(
                    f"stopped at breakeven {wib(ct):%m-%d %H:%M} WIB "
                    f"(peak {trade['max_favorable_r']}R)")
            else:
                trade["status"] = "CLOSED"
                trade["outcome"] = "SL"
                trade["r_multiple"] = -1.0
                trade["notes"].append(f"stop loss {wib(ct):%m-%d %H:%M} WIB")
            trade["resolved_utc"] = ct.isoformat(timespec="seconds")
            return True

        if hit_tp2:
            trade["status"] = "CLOSED"
            trade["outcome"] = "TP2"
            trade["r_multiple"] = trade["rr_tp2"]
            trade["resolved_utc"] = ct.isoformat(timespec="seconds")
            trade["notes"].append(f"TP2 hit {wib(ct):%m-%d %H:%M} WIB")
            return True

        # TP1 hit → SEPARUH posisi close di TP1 (partial 50%), sisanya jalan
        # ke TP2. BE baru di-arm saat harga sudah lewat BE_TRIGGER_R (1.2R,
        # rule baru 21 Sep 2026 — bukan lagi saat TP1). Alasan: data 9 signal
        # lama (WR 20%) menunjukkan 2 kali profit +1R+ hangus jadi BE 0R
        # (peak 1.37R & 0.71R berbalik) karena BE di-arm terlalu cepat.
        if hit_tp1 and not trade.get("tp1_hit"):
            trade["tp1_hit"] = True
            trade["notes"].append(
                f"TP1 hit {wib(ct):%m-%d %H:%M} WIB — partial 50% close "
                f"(+{trade['rr_tp1'] / 2:+.2f}R), sisa jalan ke TP2")
            # efektif TP1 partial: +0.5R terkunci, TP2 sisa memberi +1R lagi
            trade["be_armed"] = False
            changed = True
            if tp2 is None:
                trade["status"] = "CLOSED"
                trade["outcome"] = "TP1"
                trade["r_multiple"] = trade["rr_tp1"]
                trade["resolved_utc"] = ct.isoformat(timespec="seconds")
                return True

        # BE arms at BE_TRIGGER_R (1.2R) — bukan di TP1 (rule baru v2)
        if not trade.get("be_armed") and trade.get("tp1_hit") and \
                trade["max_favorable_r"] >= BE_TRIGGER_R:
            trade["be_armed"] = True
            trade["notes"].append(
                f"BE armed {wib(ct):%m-%d %H:%M} WIB "
                f"(peak {trade['max_favorable_r']}R >= {BE_TRIGGER_R}R)")
            changed = True

    # timeout for a still-open position
    if trade["status"] == "ACTIVE" and bars:
        # filled_utc bisa NULL kalau trade di-mark ACTIVE manual (user konfirmasi
        # entry di luar pipeline) — fallback ke created_utc, jangan crash.
        # Bug 25 Sep 2026: fromisoformat(None) → TypeError, seluruh tracker mati.
        fraw = trade.get("filled_utc") or trade.get("created_utc")
        if not fraw:
            return changed
        if isinstance(fraw, (int, float)):
            filled = datetime.datetime.fromtimestamp(fraw, datetime.timezone.utc)
        else:
            filled = datetime.datetime.fromisoformat(str(fraw))
        if filled.tzinfo is None:
            filled = filled.replace(tzinfo=datetime.timezone.utc)
        last = bars[-1]
        lt = datetime.datetime.fromtimestamp(last["t"], datetime.timezone.utc)
        if (lt - filled).total_seconds() / 3600 > ACTIVE_TTL_HOURS:
            move = (last["c"] - entry) if long else (entry - last["c"])
            trade["status"] = "CLOSED"
            trade["outcome"] = "TP1 PARTIAL" if trade.get("tp1_hit") else "EXPIRED"
            trade["r_multiple"] = round(
                trade["rr_tp1"] if trade.get("tp1_hit") else move / risk, 2)
            trade["resolved_utc"] = lt.isoformat(timespec="seconds")
            trade["notes"].append(f"closed on timeout at {last['c']:.2f}")
            changed = True

    return changed


def cmd_track(args):
    data = load()
    open_trades = [t for t in data["trades"]
                   if t["status"] in ("PENDING", "ACTIVE")]
    if not open_trades:
        if not args.quiet:
            print("No open trades.")
        return 0

    try:
        candles = fetch("15", 400)
    except Exception as e:
        print(f"TRACK FAILED: {e}")
        return 1

    events = []
    for t in open_trades:
        before = (t["status"], t["outcome"], t.get("max_favorable_r", 0) or 0)
        if _resolve(t, candles):
            after = (t["status"], t["outcome"], t.get("max_favorable_r", 0) or 0)
            if before[:2] != after[:2]:
                events.append(t)

    save(data)

    if not events:
        if not args.quiet:
            print(f"{len(open_trades)} open trade(s), no state change.")
        return 0

    for t in events:
        icon = {"TP2": "🎯", "TP1": "✅", "SL": "🛑", "BE": "⚖️",
                "NO FILL": "⬜", "EXPIRED": "⏹"}.get(t["outcome"], "▶️")
        if t["status"] in ("PENDING", "ACTIVE"):
            print(f"▶️ {t['id']} {t['side']} — now {t['status']} "
                  f"(entry {t['entry']}, peak {t.get('max_favorable_r', 0) or 0}R)")
        else:
            print(f"{icon} {t['id']} {t['side']} @ {t['entry']} — "
                  f"{t['outcome']}  {t.get('r_multiple'):+.2f}R")
            if t["notes"]:
                print(f"    {t['notes'][-1]}")
    return 0


# ----------------------------------------------------------------- report

def cmd_report(args):
    data = load()
    # SKIP records are no-trade decisions, not trades — exclude from stats
    trades = [t for t in data["trades"] if t.get("status") != "SKIP"]
    if not trades:
        print("Journal kosong — belum ada signal tercatat.")
        return 0

    closed = [t for t in trades if t["status"] == "CLOSED"]
    cancelled = [t for t in trades if t["status"] == "CANCELLED"]
    open_t = [t for t in trades if t["status"] in ("PENDING", "ACTIVE")]

    wins = [t for t in closed if t.get("r_multiple") and t.get("r_multiple") > 0]
    losses = [t for t in closed if t.get("r_multiple") is not None and t.get("r_multiple") < 0]
    bes = [t for t in closed if t.get("r_multiple") == 0]

    total_r = sum(t.get("r_multiple") for t in closed if t.get("r_multiple") is not None)
    wr = 100 * len(wins) / len(closed) if closed else 0

    print("📒 JURNAL SIGNAL XAUUSD — EVALUASI")
    print(f"\nTotal signal   : {len(trades)}")
    print(f"  Selesai      : {len(closed)}")
    print(f"  Masih jalan  : {len(open_t)}")
    print(f"  Tidak kena   : {len(cancelled)} (limit tidak tersentuh)")

    if closed:
        print(f"\nWin rate       : {wr:.0f}%  ({len(wins)}W / {len(losses)}L / {len(bes)}BE)")
        print(f"Total R        : {total_r:+.2f}R")
        print(f"Rata-rata R    : {total_r / len(closed):+.2f}R per trade")
        if wins:
            print(f"Avg win        : {sum(t.get('r_multiple') for t in wins) / len(wins):+.2f}R")
        if losses:
            print(f"Avg loss       : {sum(t.get('r_multiple') for t in losses) / len(losses):+.2f}R")

        # expectancy in points using each trade's own risk
        pts = sum((t.get("r_multiple") or 0) * t["risk_points"] for t in closed)
        print(f"Total poin     : {pts:+.1f} poin")

        by_side = {}
        for t in closed:
            by_side.setdefault(t["side"], []).append(t.get("r_multiple") or 0)
        print("\nPer arah:")
        for side, rs in by_side.items():
            w = len([r for r in rs if r > 0])
            print(f"  {side:4s} {len(rs)} trade, {w} menang, {sum(rs):+.2f}R")

        near = [t for t in closed
                if t["outcome"] in ("SL", "BE") and (t.get("max_favorable_r", 0) or 0) >= 1.0]
        if near:
            print(f"\n⚠️ {len(near)} trade sempat +1R atau lebih sebelum berbalik:")
            for t in near:
                print(f"  {t.get('date_wib', '')} {t['side']} peak {t.get('max_favorable_r', 0) or 0}R "
                      f"-> {t['outcome']}")

    if open_t:
        print("\nMasih terbuka:")
        for t in open_t:
            print(f"  {t['id']} {t['side']} @ {t['entry']} — {t['status']}"
                  + (f", peak {t.get('max_favorable_r', 0) or 0}R" if t.get("max_favorable_r", 0) or 0 else ""))

    print("\nRiwayat:")
    for t in trades[-args.limit:]:
        r = f"{t.get('r_multiple'):+.2f}R" if t.get("r_multiple") is not None else "—"
        icon = {"TP2": "🎯", "TP1": "✅", "SL": "🛑", "BE": "⚖️",
                "NO FILL": "⬜", "EXPIRED": "⏹"}.get(t["outcome"] or "", "⏳")
        print(f"  {icon} {t.get('date_wib', '')}  {t['side']:4s} @{t['entry']:<9.2f} "
              f"{(t['outcome'] or t['status']):11s} {r:>8s}"
              + (f"  peak {t.get('max_favorable_r', 0) or 0}R" if t.get("max_favorable_r", 0) or 0 else ""))
    return 0


def cmd_list(args):
    data = load()
    print(json.dumps(data["trades"][-args.limit:], indent=2))
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"])
    a.add_argument("--entry", type=float, required=True)
    a.add_argument("--sl", type=float, required=True)
    a.add_argument("--tp1", type=float, required=True)
    a.add_argument("--tp2", type=float, default=None)
    a.add_argument("--be", type=float, default=None)
    a.add_argument("--price", type=float, default=None,
                   help="market price at signal time (auto-fetched when omitted)")
    a.add_argument("--bias", default="")
    a.add_argument("--poi", default="")
    a.add_argument("--session", default="")
    a.add_argument("--style", default="")
    a.add_argument("--force", action="store_true")
    a.set_defaults(func=cmd_add)

    t = sub.add_parser("track")
    t.add_argument("--quiet", action="store_true")
    t.set_defaults(func=cmd_track)

    r = sub.add_parser("report")
    r.add_argument("--limit", type=int, default=20)
    r.set_defaults(func=cmd_report)

    l = sub.add_parser("list")
    l.add_argument("--limit", type=int, default=10)
    l.set_defaults(func=cmd_list)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
