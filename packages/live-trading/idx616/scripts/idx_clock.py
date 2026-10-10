"""Shared WIB clock and IDX session calendar for topic-616 jobs."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

WIB = ZoneInfo('Asia/Jakarta')
CALENDAR = Path(__file__).with_name('idx_holidays_2026.json')


def now_wib():
    return dt.datetime.now(WIB)


def holidays(path=CALENDAR):
    data = json.loads(Path(path).read_text())
    dates = {dt.date.fromisoformat(r['date']) for r in data['holidays']}
    if not dates:
        raise ValueError('IDX holiday calendar is empty')
    return dates


def trading_day(day, closed=None):
    closed = holidays() if closed is None else closed
    if day.year not in {d.year for d in closed}:
        raise ValueError(f'IDX holiday calendar unavailable for {day.year}')
    return day.weekday() < 5 and day not in closed


def next_trading_day(day, closed=None):
    closed = holidays() if closed is None else closed
    day += dt.timedelta(days=1)
    while not trading_day(day, closed):
        day += dt.timedelta(days=1)
    return day


def expected_eod(now=None):
    now = now or now_wib()
    closed = holidays()
    day = now.date()
    if trading_day(day, closed) and now.time().replace(tzinfo=None) >= dt.time(16, 15):
        return day
    day -= dt.timedelta(days=1)
    while not trading_day(day, closed):
        day -= dt.timedelta(days=1)
    return day


def market_status(now):
    if not trading_day(now.date()):
        return 'CLOSED'
    t = now.time().replace(tzinfo=None)
    lunch = dt.time(11, 30) if now.weekday() == 4 else dt.time(12)
    reopen = dt.time(14) if now.weekday() == 4 else dt.time(13, 30)
    if t < dt.time(9):
        return 'PRE'
    if dt.time(9) <= t < lunch or reopen <= t < dt.time(15, 50):
        return 'INTRADAY'
    if t < dt.time(15, 50):
        return 'BREAK'
    return 'POST'
