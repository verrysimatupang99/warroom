#!/usr/bin/env python3
"""multipair_journal.py — journal ringan utk signal NAS100 & EURUSD.

Dipanggil oleh multi_pair_signal.py saat signal TERKIRIM:
  journal_signal(pair, sig, zone, score)

Format: satu JSON array di ~/.hermes/trading-journal/multipair_journal.json
Status lifecycle sederhana (manual confirm workflow):
  PENDING -> (manual) ACTIVE -> CLOSED {outcome: TP2|TP1|SL|BE|NO FILL|EXPIRED}
Update status manual via CLI:
  python3 multipair_journal.py list
  python3 multipair_journal.py set <idx> <status> [outcome]
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
JOURNAL = os.path.expanduser("~/.hermes/trading-journal/multipair_journal.json")


def load():
    if os.path.exists(JOURNAL):
        try:
            return json.load(open(JOURNAL))
        except Exception:
            return []
    return []


def save(entries):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "w") as f:
        json.dump(entries, f, indent=2)


def journal_signal(pair, sig, zone, score):
    entries = load()
    dp = 5 if pair == "EURUSD" else (1 if pair == "NAS100" else 2)
    entries.append({
        "pair": pair,
        "date_wib": datetime.now(WIB).isoformat(timespec="seconds"),
        "side": sig["side"],
        "entry": round(sig["entry"], dp),
        "sl": round(sig["sl"], dp),
        "tp1": round(sig["tp1"], dp),
        "tp2": round(sig["tp2"], dp),
        "risk_points": round(sig["risk"], dp),
        "zone_kind": zone.get("kind"),
        "zone_tf": zone.get("tf"),
        "zone_low": zone.get("low"),
        "zone_high": zone.get("high"),
        "confluence": score,
        "order_type": sig.get("order_type", "LIMIT"),
        "status": "PENDING",
        "outcome": None,
    })
    save(entries)
    return len(entries) - 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    entries = load()
    if cmd == "list":
        for i, e in enumerate(entries):
            print(f"[{i}] {e['date_wib'][:16]} {e['pair']:6s} {e['side']:4s} "
                  f"entry {e['entry']} {e['status']}/{e['outcome']} conf {e['confluence']}/6")
        return 0
    if cmd == "set" and len(sys.argv) >= 4:
        idx = int(sys.argv[2])
        entries[idx]["status"] = sys.argv[3]
        if len(sys.argv) >= 5:
            entries[idx]["outcome"] = sys.argv[4]
        save(entries)
        print(f"updated [{idx}] -> {entries[idx]['status']}/{entries[idx].get('outcome')}")
        return 0
    print("unknown cmd", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
