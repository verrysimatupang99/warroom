#!/usr/bin/env python3
"""Drift alarm + cluster-robust stats + live-trading gate untuk ledger 616.

Output:
1) ~/.hermes/cron/state/idx616_drift.json  — dibaca dashboard (equity/wallet)
2) stdout = pesan Telegram HANYA saat ada alarm (no_agent empty = silent).

Metode:
- Rolling expectancy: mean net_r 20 trade CLOSED terakhir per setup;
  < 0 dengan sample >= 10 = DRIFT ALERT (edge mati pelan, itu yang bikin
  Signal IDX dulu 6 bulan minus tanpa sadar).
- Cluster-robust: bootstrap per HARI created (bukan per trade — satu hari
  BSJP = 5 ticker korelasi; effective N lu = jumlah hari, bukan jumlah trade).
  5000 resample, seed fix → CI 95% mean R.
- Gate live-trading (per setup): >= 20 hari independen, expectancy > 0.6R,
  winrate > 55%, max DD < 4R → semua PASS baru layak uang riil.
- Regime: ^JKSE close vs MA20 per tanggal created (yfinance, gratis).
"""
import datetime as dt
import json
import sqlite3
import sys

try:
    from _paths import DRIFT_JSON as OUT
    from _paths import LEDGER_DB as DB
    from _paths import REGIME_JSON as REGIME_CACHE
except Exception:
    DB = '/home/ubuntu/.hermes/cron/state/idx616_signal_ledger.db'
    OUT = '/home/ubuntu/.hermes/cron/state/idx616_drift.json'
    REGIME_CACHE = '/home/ubuntu/.hermes/cron/state/idx616_regime.json'
import random

random.seed(616)


def closed_rows():
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "select setup,ticker,created_at,closed_at,net_r,result from signals "
        "where status='CLOSED' and net_r is not null order by closed_at")]
    c.close()
    return rows


def regime_map(dates):
    """date -> 'risk-on'/'risk-off' via ^JKSE vs MA20. Cache 1 hari."""
    try:
        cache = json.load(open(REGIME_CACHE))
        if cache.get('day') == str(dt.date.today()):
            m = cache.get('map', {})
        else:
            m = {}
    except Exception:
        m = {}
    missing = [d for d in dates if d not in m]
    if missing:
        try:
            import yfinance as yf
            ihsg = yf.Ticker('^JKSE').history(period='1y')
            ma = ihsg['Close'].rolling(20).mean()
            m = {}
            for d, (cl, ma20) in zip(
                ihsg.index, zip(ihsg['Close'], ma, strict=False), strict=False
            ):
                ds = str(d.date())
                if ma20 == ma20:
                    m[ds] = 'risk-on' if cl >= ma20 else 'risk-off'
            json.dump({'day': str(dt.date.today()), 'map': m},
                      open(REGIME_CACHE, 'w'))
        except Exception as e:
            print(f"[drift] regime fail: {e}", file=sys.stderr)
    return m


def cluster_stats(rows):
    """bootstrap per-hari; return (mean_R, ci_lo, ci_hi, n_days, effective_note)."""
    by_day = {}
    for r in rows:
        d = (r['created_at'] or '')[:10]
        by_day.setdefault(d, []).append(float(r['net_r']))
    day_means = [sum(v) / len(v) for v in by_day.values()]
    if not day_means:
        return None
    mean = sum(day_means) / len(day_means)
    if len(day_means) < 2:
        return {'mean_r': round(mean, 3), 'ci_lo': None, 'ci_hi': None,
                'n_days': len(day_means)}
    boots = []
    n = len(day_means)
    for _ in range(5000):
        s = [day_means[random.randrange(n)] for _ in range(n)]
        boots.append(sum(s) / n)
    boots.sort()
    return {'mean_r': round(mean, 3),
            'ci_lo': round(boots[int(0.025 * 5000)], 3),
            'ci_hi': round(boots[int(0.975 * 5000)], 3),
            'n_days': n,
            'trades': len(rows),
            'note': f'efektif N={n} hari (bukan {len(rows)} trade — 1 hari = 1 event korelasi)'}


def setup_gate(rows):
    """semua PASS = layak live. rows = list per setup."""
    rs = [float(r['net_r']) for r in rows]
    n = len(rs)
    days = {(r['created_at'] or '')[:10] for r in rows}
    exp = sum(rs) / n if n else 0
    wr = sum(1 for x in rs if x > 0) / n * 100 if n else 0
    cum = peak = dd = 0.0
    for x in rs:
        cum += x
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    checks = [
        {'k': 'independen days >= 20', 'v': len(days), 'ok': len(days) >= 20},
        {'k': 'expectancy > 0.6R', 'v': round(exp, 3), 'ok': exp > 0.6},
        {'k': 'winrate > 55%', 'v': round(wr, 1), 'ok': wr > 55},
        {'k': 'max DD < 4R', 'v': round(dd, 2), 'ok': dd < 4},
    ]
    return {'n': n, 'days': len(days), 'checks': checks,
            'all_pass': all(c['ok'] for c in checks), 'max_dd_r': round(dd, 2)}


def main():
    rows = closed_rows()
    by_setup = {}
    for r in rows:
        s = (r['setup'] or '?').split('_')[0]
        s = {'BSJP': 'BSJP', 'ARA': 'ARA', 'INTRADAY': 'SCALP', 'MOMENTUM': 'SCALP',
             'BREAKOUT': 'SCALP', 'REJECTION': 'SCALP'}.get(s.split('_')[0], s)
        by_setup.setdefault(s, []).append(r)

    out = {'generated': str(dt.datetime.now(dt.UTC)),
           'setups': {}, 'alerts': []}
    for s, rs in by_setup.items():
        cl = cluster_stats(rs)
        gate = setup_gate(rs)
        recent = sorted(rs, key=lambda r: r['closed_at'])[-20:]
        roll = (sum(float(x['net_r']) for x in recent) / len(recent)
                if len(recent) >= 10 else None)
        out['setups'][s] = {'closed': len(rs), 'cluster': cl, 'gate': gate,
                            'rolling20_r': round(roll, 3) if roll is not None else None}
        if roll is not None and roll < 0:
            out['alerts'].append(f"{s}: rolling-20 expectancy {roll:+.2f}R (NEGATIF — edge mati?)")
            if cl and cl.get('ci_hi') is not None and cl['ci_hi'] < 0:
                out['alerts'].append(f"{s}: CI95 cluster seluruhnya < 0 ({cl['ci_lo']},{cl['ci_hi']})")

    reg = regime_map({(r['created_at'] or '')[:10] for r in rows})
    out['regime'] = {d: reg.get(d, 'n/a') for d in
                     sorted({(r['created_at'] or '')[:10] for r in rows})}
    json.dump(out, open(OUT, 'w'), indent=1)

    if out['alerts']:
        lines = ['⚠️ *IDX 616 — DRIFT ALERT*', '']
        lines += [f"• {a}" for a in out['alerts']]
        g = out['setups'].get('BSJP', {}).get('gate', {})
        if g.get('n'):
            lines += ['', f"BSJP gate: {sum(1 for c in g['checks'] if c['ok'])}/4 PASS"]
        lines += ['', '— Hermes Grader Watch']
        print('\n'.join(lines))
    # tanpa alert = silent (stdout kosong)
    return 0


if __name__ == '__main__':
    sys.exit(main())
