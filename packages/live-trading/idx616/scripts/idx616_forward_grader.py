#!/usr/bin/env python3
"""Forward-grade ledger events 616.

Aturan per setup (mengikuti disiplin ledger di skill idx-indonesia-market-data):

- BSJP_*: entry = close T, exit = OPEN sesi T+1 (bukan sentuh TP/SL intraday).
  net_r = (ret_pct - COST) / risk_pct, dengan risk_pct dari (entry - sl)/entry.
  Bar hari-T sendiri TIDAK boleh dipakai (created_at 15:41 < bar T 23:59).
  Sesi dibandingkan per-TANGGAL, bukan per-timestamp.
- INTRADAY/scalp: butuh bar intraday (WS 5m) yang tidak tersedia retrospektif →
  DIBIARKAN pending. Jangan grade pakai bar harian (fabrikasi fill).

Tidak pernah mengarang fill. Idempotent: event CLOSED dilewati.
"""
import datetime as dt
import json
import sys

sys.path.insert(0, '/home/ubuntu/.hermes/scripts')
from idx616_ledger import DB, con
from arjum_pool import pool_history

BSJP_COST_PCT = 0.40   # round-trip fee+levy, konsisten dgn idx_bsjp_watch.py
GRADER_VERSION = "v2-bsjp-open-exit"


def _bars(ticker):
    code = ticker.upper().removesuffix('.JK')
    data = pool_history(code, frame='daily')
    rows = data.get('rows', []) if isinstance(data, dict) else []
    out = []
    for x in rows:
        ts = x.get('date') or x.get('timestamp') or x.get('time')
        if not ts:
            continue
        d = str(ts)[:10]
        try:
            o = float(x.get('open', x.get('Open')))
        except (TypeError, ValueError):
            o = None
        out.append({'date': d, 'open': o,
                    'high': x.get('high', x.get('High')),
                    'low': x.get('low', x.get('Low')),
                    'close': x.get('close', x.get('Close'))})
    out.sort(key=lambda b: b['date'])
    return out


def grade_bsjp(row):
    """Exit di open sesi T+1. Return dict update atau None kalau belum ada sesi."""
    sig_date = (row['created_at'] or '')[:10]
    if not sig_date:
        return None
    future = [b for b in _bars(row['ticker']) if b['date'] > sig_date and b['open']]
    if not future:
        return None
    exit_price = future[0]['open']
    exit_date = future[0]['date']
    entry = row['entry_low'] or row['entry_high']
    if not entry or not row['sl']:
        return None
    ret_pct = (exit_price / entry - 1) * 100
    risk_pct = (entry - row['sl']) / entry * 100
    if risk_pct <= 0:
        return None
    net_r = round((ret_pct - BSJP_COST_PCT) / risk_pct, 4)
    result = 'TP1' if net_r > 0 else 'SL'
    return {
        'status': 'CLOSED', 'filled_at': f"{sig_date}T15:41:00+07:00",
        'closed_at': f"{exit_date}T09:00:00+07:00", 'result': result,
        'net_r': net_r,
        'note': (f"BSJP exit open {exit_date}: {exit_price:g} vs entry {entry:g} "
                 f"= {ret_pct:+.2f}% net {net_r:+.2f}R"),
    }


def main():
    c = con(DB)
    rows = c.execute(
        "select * from signals where status!='CLOSED'").fetchall()
    c.close()

    graded = pending = errors = skipped = 0
    for r in rows:
        setup = (r['setup'] or '').upper()
        try:
            if setup.startswith('BSJP'):
                upd = grade_bsjp(r)
                if not upd:
                    pending += 1
                    continue
                cc = con(DB)
                cc.execute(
                    "UPDATE signals SET status=?,filled_at=?,closed_at=?,result=?,"
                    "net_r=?,note=?,graded_at=?,grader_version=? WHERE event_id=?",
                    (upd['status'], upd['filled_at'], upd['closed_at'], upd['result'],
                     upd['net_r'], upd['note'],
                     dt.datetime.now(dt.timezone.utc).isoformat(),
                     GRADER_VERSION, r['event_id']))
                cc.commit()
                cc.close()
                graded += 1
            else:
                # INTRADAY/scalp: butuh bar intraday → tetap pending (jujur).
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"[grader-warn] {r['event_id']} {e}", file=sys.stderr)

    print(json.dumps({
        'events': len(rows), 'graded_bsjp': graded,
        'pending_no_next_session': pending,
        'skipped_intraday_needs_intraday_bars': skipped,
        'errors': errors, 'grader': GRADER_VERSION,
    }))


if __name__ == '__main__':
    main()
