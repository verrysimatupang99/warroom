#!/usr/bin/env python3
"""Collector untuk cron LLM: Ara Hunter.

Jalankan scan ARA (tanpa --post = tanpa LLM call di dalam script, tanpa kirim).
Cetak data packet JSON ke STDOUT untuk LLM.
Silent (stdout kosong) kalau tidak ada kandidat.
Archive dashboard tetap ditulis oleh scan.
Ledger 616 ditulis DI SINI (setelah hits valid, sebelum LLM) — sinyal = event,
grader v3 yang resolve outcome-nya. Idempotent via UNIQUE ledger.
"""
import datetime as dt
import json
import subprocess
import sys

sys.path.insert(0, '/home/admin/warroom/packages/live-trading/idx616/scripts')
VPY = "/home/admin/warroom/.venv/bin/python"
SCANNER = "/home/admin/warroom/packages/live-trading/idx616/scripts/ara_hunter.py"
ARA_JOB_ID = 'a059957d2e81'


def record_ledger(hits, ts_wib):
    """Entry = close TV saat sinyal; exit = open T+1 (grade oleh grader v3).
    Levels nominal -2.5/+1/+2% — dicatat sebagai plan, bukan level touch."""
    try:
        from idx616_ledger import record_event
    except Exception as e:
        print(f"[ara-ledger] unavailable: {e}", file=sys.stderr)
        return
    ok = 0
    for h in hits:
        c = float(h['close'])
        try:
            record_event(job_id=ARA_JOB_ID, producer='ara_hunter_ledger.py',
                         created_at=ts_wib, ticker=f"{h['symbol']}.JK",
                         setup='ARA_HUNTER', source='ara_hunter',
                         direction='LONG', entry_low=c, entry_high=c,
                         sl=round(c * 0.975, 1), tp1=round(c * 1.01, 1),
                         tp2=round(c * 1.02, 1),
                         data_source='tradingview_scanner', source_timestamp=ts_wib,
                         note=f"ara chg {h.get('change_pct')}% rvol {h.get('rel_vol')}x adx {h.get('adx')}")
            ok += 1
        except Exception as e:
            if 'UNIQUE' not in str(e):
                print(f"[ara-ledger] {h.get('symbol')}: {e}", file=sys.stderr)
    print(f"[ara-ledger] {ok}/{len(hits)} recorded", file=sys.stderr)


def main():
    r = subprocess.run([VPY, SCANNER], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"[collector FAIL rc={r.returncode}] {r.stderr.strip()[:200]}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(r.stdout.strip()[:20000])
    except Exception as e:
        print(f"[collector FAIL parse JSON: {e}]", file=sys.stderr)
        return 1
    hits = payload.get("hits") or []
    if not hits:
        return 0  # SILENT
    # WIB ISO dari waktu scan (ara_hunter pakai now_wib → 'YYYY-MM-DD HH:MM:SS')
    try:
        ts_wib = dt.datetime.strptime(
            payload['time'], '%Y-%m-%d %H:%M:%S').replace(
                tzinfo=dt.timezone(dt.timedelta(hours=7))).isoformat()
    except Exception:
        from idx_clock import now_wib
        ts_wib = now_wib().isoformat()
    record_ledger(hits, ts_wib)
    packet = {
        "time": payload.get("time"),
        "scanned": payload.get("scanned"),
        "recipe": "chg>=5% · rel_vol>=3x · ADX>15 · value>=Rp1B",
        "backtest": "walk-forward 11 Sep: +1.00% net/trade, exit open T+1",
        "hits": [
            {
                "symbol": h["symbol"],
                "close": h["close"],
                "change_pct": round(h["change_pct"] or 0, 1),
                "rel_vol": round(h["rel_vol"] or 0, 1),
                "adx": round(h["adx"] or 0, 0),
            }
            for h in hits
        ],
    }
    print("=== ARA HUNTER DATA PACKET ===")
    print(json.dumps(packet, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    raise SystemExit(main())
