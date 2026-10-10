#!/usr/bin/env python3
"""Grade BSJP against the dated T+1 opening bar; never infer a date."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import yfinance as yf
from openpyxl import load_workbook
from idx_clock import WIB, now_wib, holidays, next_trading_day, trading_day

JOURNAL = Path('/home/ubuntu/.hermes/idx-journal/idx_journal.xlsx')
LOGGER = Path(__file__).with_name('idx_signal_journal.py')
COST_PCT = 0.40


def signal_id(row_number, row):
    identity = [row_number, *[str(row[i]) for i in (0, 1, 4, 6, 17)]]
    return 'bsjp-open-' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]


def candidates(rows, now, closed):
    terminal = {str(r[16]).split('[event:', 1)[1].split(']', 1)[0]
                for r in rows if len(r) >= 18 and r[3] == 'EVAL' and '[event:' in str(r[16])}
    out = []
    for number, row in enumerate(rows, 2):
        if len(row) < 18 or row[3] != 'SIGNAL' or str(row[17]).upper() != 'BSJP' or row[13]:
            continue
        key = signal_id(number, row)
        if key in terminal:
            continue
        try:
            day = dt.date.fromisoformat(str(row[0])[:10])
            opening_day = next_trading_day(day, closed)
            entry = float(row[6])
            if not math.isfinite(entry) or entry <= 0:
                continue
        except (ValueError, TypeError):
            continue
        if opening_day > now.date():
            continue
        if opening_day == now.date() and now.time().replace(tzinfo=None) < dt.time(9, 5):
            continue
        # Old unkeyed evaluations are not re-graded or overwritten automatically.
        legacy = any(len(r) >= 18 and r[3] == 'EVAL' and str(r[17]).upper() == 'BSJP'
                     and r[4] == row[4] and str(r[0])[:10] >= str(row[0])[:10]
                     and '[event:' not in str(r[16]) for r in rows)
        if legacy:
            print(f'SKIP legacy BSJP evaluation requires review: {row[4]} {day}', file=sys.stderr)
            continue
        out.append({'id': key, 'symbol': str(row[4]), 'entry': entry,
                    'signal_date': day, 'opening_date': opening_day})
    return out


def opening_price(history, day):
    if history is None or history.empty:
        return None
    for stamp, row in history.iterrows():
        actual = stamp.tz_convert(WIB).date() if stamp.tzinfo else stamp.date()
        if actual != day:
            continue
        price = float(row['Open'])
        volume = float(row.get('Volume', 0))
        if math.isfinite(price) and price > 0 and math.isfinite(volume) and volume > 0:
            return price
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--journal', type=Path, default=JOURNAL)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    now = now_wib()
    closed = holidays()
    if not trading_day(now.date(), closed) or now.time().replace(tzinfo=None) < dt.time(9, 5):
        return 0
    wb = load_workbook(args.journal, read_only=True, data_only=True)
    rows = list(wb['Jurnal IDX'].iter_rows(min_row=2, values_only=True))
    wb.close()
    graded = []
    for signal in candidates(rows, now, closed):
        day = signal['opening_date']
        try:
            history = yf.Ticker(signal['symbol']).history(
                start=day.isoformat(), end=(day + dt.timedelta(days=1)).isoformat(),
                interval='1d', auto_adjust=False,
            )
            price = opening_price(history, day)
            if price is None:
                print(f'PENDING {signal["symbol"]}: no traded opening bar dated {day}', file=sys.stderr)
                continue
            gross = (price / signal['entry'] - 1) * 100
            net = gross - COST_PCT
            if not args.dry_run:
                proc = subprocess.run([
                    sys.executable, str(LOGGER), '--journal', str(args.journal),
                    '--status', 'EVAL', '--event-id', signal['id'],
                    '--emiten', signal['symbol'], '--entry', str(signal['entry']),
                    '--result', 'EXIT', '--pnl', f'{net:.4f}', '--mode', 'BSJP',
                    '--alasan', f'BSJP open {day} price={price}; gross={gross:.4f}%; cost={COST_PCT}%',
                ], capture_output=True, text=True, timeout=30, check=True)
                if proc.stdout.startswith('ALREADY'):
                    continue
            graded.append(f"• {signal['symbol'].removesuffix('.JK')}: entry {signal['entry']:,.0f} → open {day} {price:,.0f}; gross {gross:+.2f}%, net {net:+.2f}%")
        except Exception as exc:
            print(f'BSJP PENDING {signal["symbol"]}: {type(exc).__name__}', file=sys.stderr)
    if graded:
        print(f'BSJP EXIT — {now:%d %b %H:%M} WIB\n' + '\n'.join(graded)
              + f'\nEvaluasi opening T+1, bukan bukti fill; asumsi biaya round-trip {COST_PCT:.2f}%.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
