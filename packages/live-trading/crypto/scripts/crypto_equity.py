import logging
#!/usr/bin/env python3
"""Crypto equity tracker — ledger R per trade + kurva ekuitas.

Ledger append-only: ~/.hermes/state/crypto_equity.jsonl
Satu baris = satu trade tertutup:
  {"signal_id","pair","closed_at","status","r","note","source"}

Sumber kebenaran R:
  1. angka R eksplisit di notes watchlist (mis. "Net ~+1R", "Blended ~+1.5R")
  2. fallback peta status (closed_TP2=+1.5R, closed_TP1=+0.5R, closed_SL=-1R, expired=0R)

`sync()` idempoten: menambah trade yang belum ada di ledger, tidak pernah menimpa
baris lama. Dipanggil dashboard tiap request (murah) dan bisa dipanggil manual.

Dipakai juga oleh: crypto_dashboard.py (panel equity curve).
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.expanduser("~/.hermes")
WATCHLIST = os.path.join(HERE, "crypto-watchlist.json")
LEDGER = os.path.join(HERE, "state", "crypto_equity.jsonl")
WIB = timezone(timedelta(hours=7))

CLOSED_PREFIX = ("closed", "expired")
FALLBACK_R = {"closed_TP2": 1.5, "closed_TP1": 0.5, "closed_SL": -1.0,
              "closed_timeout": 0.0, "expired": 0.0}
_R_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*R\b")


def _read_ledger():
    rows = []
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def _write_ledger(rows):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, LEDGER)


def _r_from_notes(notes):
    if not notes:
        return None
    # "Net ~+1R", "Blended ~+1.5R", "-0.5R"
    m = _R_RE.search(notes)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _closed_at(item, notes):
    """Ambil tanggal close dari notes kalau ada ('Eval 22/Sep 05:00 WIB')."""
    if notes:
        m = re.search(r"Eval\s+(\d{1,2})/(\w{3})\s+(\d{1,2}):(\d{2})", notes)
        if m:
            try:
                dt = datetime.strptime(f"{m.group(1)}/{m.group(2)} {m.group(3)}:{m.group(4)}",
                                       "%d/%b %H:%M")
                return dt.replace(year=datetime.now(WIB).year, tzinfo=WIB).isoformat()
            except Exception:
                logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
    return item.get("date_added")


def sync():
    """Tambah trade tertutup dari watchlist ke ledger. Return jumlah baris baru."""
    try:
        wl = json.load(open(WATCHLIST, encoding="utf-8"))
    except Exception:
        return 0
    items = wl.get("items") or []
    ledger = _read_ledger()
    seen = {r.get("signal_id") for r in ledger}
    added = 0
    for it in items:
        st = it.get("status") or ""
        sid = it.get("signal_id")
        if not sid or sid in seen or not st.startswith(CLOSED_PREFIX):
            continue
        notes = it.get("notes") or ""
        r = _r_from_notes(notes)
        if r is None:
            r = FALLBACK_R.get(st, 0.0)
        ledger.append({
            "signal_id": sid,
            "pair": it.get("pair"),
            "direction": it.get("direction"),
            "closed_at": _closed_at(it, notes),
            "status": st,
            "r": round(float(r), 3),
            "note": notes[:300],
            "source": "watchlist-sync",
            "logged_at": datetime.now(WIB).isoformat(),
        })
        added += 1
    if added:
        ledger.sort(key=lambda x: (x.get("closed_at") or "", x.get("signal_id") or ""))
        _write_ledger(ledger)
    return added


def curve():
    """Titik kurva ekuitas kumulatif (dalam R) + statistik."""
    sync()
    rows = _read_ledger()
    rows.sort(key=lambda x: (x.get("closed_at") or "", x.get("signal_id") or ""))
    pts = [{"i": 0, "r": 0.0, "cum": 0.0, "label": "start", "signal_id": None}]
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    wins = 0
    losses = 0
    gross_win = 0.0
    gross_loss = 0.0
    for i, t in enumerate(rows, 1):
        r = float(t.get("r") or 0.0)
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        if r > 0:
            wins += 1
            gross_win += r
        elif r < 0:
            losses += 1
            gross_loss += abs(r)
        pts.append({
            "i": i, "r": r, "cum": round(cum, 3),
            "signal_id": t.get("signal_id"), "pair": t.get("pair"),
            "status": t.get("status"), "closed_at": t.get("closed_at"),
        })
    n = len(rows)
    stats = {
        "trades": n,
        "total_r": round(cum, 2),
        "winrate_pct": round(100 * wins / n, 1) if n else None,
        "wins": wins, "losses": losses,
        "avg_r": round(cum / n, 3) if n else None,
        "max_drawdown_r": round(max_dd, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "expectancy_r": round(cum / n, 3) if n else None,
    }
    return {"points": pts, "trades": rows, "stats": stats,
            "since": rows[0].get("closed_at") if rows else None}


def add_trade(signal_id, pair, status, r, note="", closed_at=None, source="manual"):
    """Catat trade manual (dipakai kalau ada trade di luar watchlist)."""
    ledger = _read_ledger()
    if any(x.get("signal_id") == signal_id for x in ledger):
        return False
    ledger.append({
        "signal_id": signal_id, "pair": pair, "status": status,
        "r": round(float(r), 3), "note": note,
        "closed_at": closed_at or datetime.now(WIB).isoformat(),
        "source": source, "logged_at": datetime.now(WIB).isoformat(),
    })
    ledger.sort(key=lambda x: (x.get("closed_at") or "", x.get("signal_id") or ""))
    _write_ledger(ledger)
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        print(f"sync: +{sync()} baris baru -> {LEDGER}")
    c = curve()
    print(json.dumps(c["stats"], indent=2))
    for p in c["points"]:
        print(f"  {p['i']:>2} {str(p.get('pair')):<12} {str(p.get('status')):<12} r={p['r']:+.2f} cum={p['cum']:+.2f}")
