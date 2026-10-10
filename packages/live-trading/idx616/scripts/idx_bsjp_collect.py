#!/usr/bin/env python3
"""Collector untuk cron LLM: BSJP Watcher.

Jalankan scan BSJP (edge_filter + window guard + journal/ledger — semua tetap),
tapi JANGAN kirim via send_confirmed. Cetak data packet JSON ke STDOUT untuk LLM.
Silent (stdout kosong) kalau di luar window / tidak ada kandidat.
"""
import argparse
import datetime
import json
import sys

sys.path.insert(0, "/home/admin/warroom/packages/live-trading/idx616/scripts")
import idx_bsjp_watch as B
from idx_clock import now_wib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    now = now_wib()
    if now.weekday() >= 4:
        return 0  # SILENT: Jumat/weekend off
    from idx_clock import trading_day
    if not trading_day(now.date()) or not (
        datetime.time(15, 40) <= now.time() <= datetime.time(16, 0)
    ):
        return 0  # SILENT: di luar window

    try:
        cands = B.scan()
    except Exception as e:
        print(f"[collector FAIL: {e}]", file=sys.stderr)
        return 1
    hits = B.edge_filter(cands, args.top)
    if not hits:
        return 0  # SILENT

    # journal + ledger tetap dicatat di sini (sekali, bukan oleh LLM)
    for s in hits:
        B.journal_log(s)

    packet = {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "strategy": "BSJP: beli di close hari ini, jual di open besok 08:55-09:05",
        "backtest": "6 bln walk-forward: +0.9% net/trade, WR ~48%",
        "hits": [
            {
                "symbol": s["symbol"],
                "close": s["close"],
                "chg_pct": round(s["chg"], 1),
                "rel_vol": s["rel_vol"],
                "sma10": s.get("sma10"),
                "tier": s.get("tier", "ARA"),
                "net_est": s.get("net_est"),
                "entry": round(s["close"], 0),
                "sl": round(s["close"] * 0.975, 0),
                "tp": round(s["close"] * 1.01, 0),
            }
            for s in hits
        ],
    }
    print("=== BSJP DATA PACKET ===")
    print(json.dumps(packet, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    raise SystemExit(main())
