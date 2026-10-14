#!/usr/bin/env python3
"""Forward-grade ledger events 616.

Aturan per setup (mengikuti disiplin ledger di skill idx-indonesia-market-data):

- BSJP_*: entry = close T, exit = OPEN sesi T+1 (bukan sentuh TP/SL intraday).
  net_r = (ret_pct - COST) / risk_pct, dengan risk_pct dari (entry - sl)/entry.
  Bar hari-T sendiri TIDAK boleh dipakai (created_at 15:41 < bar T 23:59).
  Sesi dibandingkan per-TANGGAL, bukan per-timestamp.
- ARA_*: sesuai resep walk-forward 11 Sep — entry = close T (TV snapshot),
  exit = open T+1, metrik = % net langsung (+1.00% net/trade di backtest),
  bukan R-multiple (ngetem overnight, bukan level-based). Dedupe: satu
  ticker hanya dihitung sekali per hari (run 10:15/14:15/16:15 overlap).
- INTRADAY (scalp): butuh bar intraday. Sumber = WS tick DB arjum_trades
  (tick-by-tick WIB, coverage 14 Sep+). Agregasi 1m dari signal ts sampai
  15:49, chronological walk TP/SL/timeout; same-bar collision -> AMBIGUOUS.
  Kalau DB tidak punya tick ticker-hari itu -> TETAP pending (jujur).
  data_freshness di-note; fill = level touch (asumsi limit-order disiplin,
  dicatat apa adanya di note).

Tidak pernah mengarang fill. Idempotent: event CLOSED dilewati.
"""
import datetime as dt
import json
import os
import sqlite3
import sys

# Versi lokal War Room: path skrip = folder modul ini (dulu hardcoded /home/ubuntu)
sys.path.insert(0, '/home/admin/warroom/packages/live-trading/idx616/scripts')
from idx616_ledger import DB, con

try:
    from arjum_pool import pool_history
except Exception:  # tanpa kunci arjum: grader jatuh ke fallback bila ada
    pool_history = None

BSJP_COST_PCT = 0.40   # round-trip fee+levy, konsisten dgn idx_bsjp_watch.py
ARA_COST_PCT = 0.40
try:
    from _paths import ARJUM_TRADES_DB as WS_DB  # versi lokal
except Exception:
    WS_DB = '/home/ubuntu/.hermes/cron/state/arjum_trades.db'
GRADER_VERSION = "v3-ara-intraday"

# Batas waktu scalping intraday (jam, WIB). Docstring modul & _minute_bars menyebut
# "sampai 15:49"; kode memakai f"{SCALP_TIMEOUT}:59" sehingga nilai yang benar adalah
# "15:48" (menit terakhir sebelum 15:49). Sebelumnya konstanta ini TIDAK PERNAH
# didefinisikan -> NameError laten, hanya muncul saat ada bar intraday untuk digrade.
# Nilai ditarik dari docstring, bukan dikarang; koreksi bila owner punya definisi lain.
SCALP_TIMEOUT = "15:48"


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


def grade_ara(row):
    """ARA: entry close T (sudah di entry_low oleh ara_ledger.py), exit open T+1.
    net_r = (ret% - cost) / 2.5 (SL nominal -2.5% = konvensi Ara). Return None
    kalau T+1 belum ada."""
    sig_date = (row['created_at'] or '')[:10]
    entry = row['entry_low'] or row['entry_high']
    if not sig_date or not entry:
        return None
    future = [b for b in _bars(row['ticker']) if b['date'] > sig_date and b['open']]
    if not future:
        return None
    exit_price = future[0]['open']
    exit_date = future[0]['date']
    ret_pct = (exit_price / entry - 1) * 100
    net_pct = ret_pct - ARA_COST_PCT
    risk_pct = 2.5  # SL nominal -2.5% (konvensi Ara, bukan level real)
    net_r = round(net_pct / risk_pct, 4)
    result = 'WIN' if net_pct > 0 else 'LOSS'
    return {
        'status': 'CLOSED', 'filled_at': row['created_at'],
        'closed_at': f"{exit_date}T09:00:00+07:00", 'result': result,
        'net_r': net_r,
        'note': (f"ARA exit open {exit_date}: {exit_price:g} vs close-T {entry:g} "
                 f"= {ret_pct:+.2f}% net {net_pct:+.2f}% ({net_r:+.2f}R@2.5%)"),
    }


def _minute_bars(ticker, sig_date, sig_time):
    """Agregasi tick WS -> bars 1m chronological dari signal sampai 15:49."""
    if not os.path.exists(WS_DB):
        return None
    t = ticker.upper().removesuffix('.JK')
    try:
        c = sqlite3.connect(f'file:{WS_DB}?mode=ro', uri=True, timeout=10)
    except sqlite3.Error:
        return None
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "select ts, price from trades where ticker=? and ts>=? and ts<=? "
        "and price>0 order by ts", (t, f"{sig_date} {sig_time}",
                                    f"{sig_date} {SCALP_TIMEOUT}:59")).fetchall()
    c.close()
    bars = {}
    for r in rows:
        minute = str(r['ts'])[:16]  # 'YYYY-MM-DD HH:MM'
        p = float(r['price'])
        b = bars.setdefault(minute, {'ts': minute, 'high': p, 'low': p, 'open': p, 'close': p})
        b['high'] = max(b['high'], p)
        b['low'] = min(b['low'], p)
        b['close'] = p
    return sorted(bars.values(), key=lambda b: b['ts'])


def grade_intraday(row, bars):
    """Walk TP/SL/timeout chronological. Fill = level touch (asumsi limit).
    Same-bar collision -> AMBIGUOUS (favorit-kanan rule lama ledger)."""
    entry = row['entry_low'] or row['entry_high']
    if not entry or not row['sl'] or not row['tp1']:
        return None
    sl, tp1, tp2 = float(row['sl']), float(row['tp1']), float(row['tp2'] or row['tp1'])
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    for b in bars:
        hit_sl = b['low'] <= sl
        hit_tp = b['high'] >= tp1
        if hit_sl and hit_tp:
            return {'status': 'CLOSED', 'filled_at': row['created_at'],
                    'closed_at': b['ts'].replace(' ', 'T') + '+07:00',
                    'result': 'AMBIGUOUS', 'net_r': 0.0,
                    'note': f"intraday: SL&TP1 di bar 1m sama ({b['ts']}) -> ambiguous 0R"}
        if hit_sl:
            net_r = -1.0
            return {'status': 'CLOSED', 'filled_at': row['created_at'],
                    'closed_at': b['ts'].replace(' ', 'T') + '+07:00',
                    'result': 'SL', 'net_r': round(net_r, 4),
                    'note': f"intraday SL touch {b['ts']} @ {sl:g}"}
        if hit_tp:
            # TP2 touch?
            extra = ''
            if tp2 and b['high'] >= tp2:
                return {'status': 'CLOSED', 'filled_at': row['created_at'],
                        'closed_at': b['ts'].replace(' ', 'T') + '+07:00',
                        'result': 'TP2', 'net_r': round((tp2 - entry) / risk, 4),
                        'note': f"intraday TP2 touch {b['ts']} @ {tp2:g}"}
            return {'status': 'CLOSED', 'filled_at': row['created_at'],
                    'closed_at': b['ts'].replace(' ', 'T') + '+07:00',
                    'result': 'TP1', 'net_r': round((tp1 - entry) / risk, 4),
                    'note': f"intraday TP1 touch {b['ts']} @ {tp1:g}{extra}"}
    # timeout: exit di close bar terakhir
    if bars:
        last = bars[-1]['close']
        net_r = round((last - entry) / risk, 4)
        return {'status': 'CLOSED', 'filled_at': row['created_at'],
                'closed_at': bars[-1]['ts'].replace(' ', 'T') + '+07:00',
                'result': 'TIMEOUT', 'net_r': net_r,
                'note': f"intraday timeout {SCALP_TIMEOUT} @ {last:g} = {net_r:+.2f}R"}
    return None


def main():
    c = con(DB)
    rows = c.execute(
        "select * from signals where status!='CLOSED'").fetchall()
    c.close()

    graded = {'bsjp': 0, 'ara': 0, 'intraday': 0}
    pending = errors = skipped = 0
    dup_skips = 0
    ara_done_today = set()
    # urutan grading: BSJP/ARA chronological
    rows = sorted(rows, key=lambda r: (r['created_at'] or ''))
    for r in rows:
        setup = (r['setup'] or '').upper()
        try:
            if setup.startswith('BSJP'):
                upd = grade_bsjp(r)
                if not upd:
                    pending += 1
                    continue
                kind = 'bsjp'
            elif setup.startswith('ARA'):
                key = ((r['created_at'] or '')[:10], r['ticker'])
                if key in ara_done_today:
                    dup_skips += 1
                    continue
                upd = grade_ara(r)
                if not upd:
                    pending += 1
                    continue
                ara_done_today.add(key)
                kind = 'ara'
            elif setup in ('INTRADAY', 'MOMENTUM', 'BREAKOUT', 'REJECTION'):
                sig_dt = (r['created_at'] or '').replace('T', ' ')[:19]
                if len(sig_dt) < 16 or not os.path.exists(WS_DB):
                    pending += 1
                    continue
                bars = _minute_bars(r['ticker'], sig_dt[:10], sig_dt[11:16])
                if not bars:
                    skipped += 1  # jujur: tidak ada tick untuk ticker-hari ini
                    continue
                upd = grade_intraday(r, bars)
                if not upd:
                    pending += 1
                    continue
                upd['note'] = f"[ws1m {len(bars)}b] " + upd['note']
                kind = 'intraday'
            else:
                skipped += 1
                continue
            cc = con(DB)
            cc.execute(
                "UPDATE signals SET status=?,filled_at=?,closed_at=?,result=?,"
                "net_r=?,note=?,graded_at=?,grader_version=? WHERE event_id=?",
                (upd['status'], upd['filled_at'], upd['closed_at'], upd['result'],
                 upd['net_r'], upd['note'][:300],
                 dt.datetime.now(dt.UTC).isoformat(),
                 GRADER_VERSION, r['event_id']))
            cc.commit()
            cc.close()
            graded[kind] += 1
        except Exception as e:
            errors += 1
            print(f"[grader-warn] {r['event_id']} {e}", file=sys.stderr)

    print(json.dumps({
        'events': len(rows), 'graded': graded,
        'pending_wait_session': pending,
        'skipped_no_intraday_data': skipped,
        'ara_dup_suppressed': dup_skips,
        'errors': errors, 'grader': GRADER_VERSION,
    }))


if __name__ == '__main__':
    main()
