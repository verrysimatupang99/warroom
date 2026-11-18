"""Ingest MT5 -> War Room v1.

Sumber:
  1. Live  : MQL5/Files/wr_telemetry.json  (ditulis EA tiap ~5 s) + wr_deals.jsonl
  2. Demo  : Common/Files/MTRB_Pro_status.json (ditulis MTRB_Fix tiap ~2 s)

Yang ditulis: account_snapshot, position, fill, ledger_entry, feed, strategy_run, event.
Idempoten: snapshot per detik, posisi per (account, ext_id), deal per (account, ticket).
"""
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import psycopg

DSN = os.environ["V1_DSN"]
LIVE_DIR = Path("/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Live/MQL5/Files")
DEMO_STATUS = Path(
    "/home/admin/.wine-exness/drive_c/users/admin/AppData/Roaming/"
    "MetaQuotes/Terminal/Common/Files/MTRB_Pro_status.json"
)
LOG = Path("/var/log/wr-ingest.log")


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        with LOG.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def ts(val):
    """Normalisasi waktu MT5 ('2026.11.17 20:07:15') ke datetime/None."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    txt = str(val).strip().replace(".", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def get_account(cur, login_tail: str, mode: str):
    cur.execute(
        """select id, currency from v1.account
           where right(coalesce(login_ext,''),3)=%s and mode=%s and active
           order by id limit 1""",
        (login_tail[-3:], mode),
    )
    return cur.fetchone()


def snapshot(cur, acct_id: int, currency: str, bal, eq, margin, free, floating):
    cur.execute(
        """insert into v1.account_snapshot
             (account_id, ts, balance, equity, margin, free_margin, floating_pnl, currency)
           values (%s, date_trunc('second', now()), %s,%s,%s,%s,%s,%s)
           on conflict (account_id, ts) do update set
             balance=excluded.balance, equity=excluded.equity,
             margin=excluded.margin, free_margin=excluded.free_margin,
             floating_pnl=excluded.floating_pnl""",
        (acct_id, bal, eq, margin, free, floating, currency),
    )


def upsert_position(cur, acct_id: int, inst_id, ext_id, side, qty, entry, sl, tp,
                    opened_at, pnl=None, closed_at=None):
    if inst_id is None or not ext_id:
        return
    cur.execute(
        """insert into v1.position
             (account_id, instrument_id, ext_id, side, qty_open, entry_price,
              sl, tp1, opened_at, realized_pnl, closed_at)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (account_id, ext_id) do update set
             qty_open=excluded.qty_open, entry_price=excluded.entry_price,
             sl=excluded.sl, tp1=excluded.tp1,
             realized_pnl=coalesce(excluded.realized_pnl, v1.position.realized_pnl),
             closed_at=coalesce(excluded.closed_at, v1.position.closed_at)""",
        (acct_id, inst_id, str(ext_id), side, qty, entry, sl, tp, opened_at, pnl, closed_at),
    )


def instrument_id(cur, symbol: str, price: float | None):
    cur.execute(
        """select id from v1.instrument
           where symbol=%s and active
           order by (digits is not null) desc, id limit 1""",
        (symbol,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # simbol tak dikenal: daftarkan otomatis supaya data tidak hilang
    cur.execute("select id from v1.venue where code='exness'")
    v = cur.fetchone()
    if not v:
        return None
    digits = 3 if price and price > 100 else 5
    cur.execute(
        """insert into v1.instrument (venue_id, market, symbol, kind, quote_ccy, digits)
           values (%s,'forex',%s,'spot','USD',%s)
           on conflict (venue_id, symbol, kind) do update set active=true
           returning id""",
        (v[0], symbol, digits),
    )
    return cur.fetchone()[0]


def touch_feed(cur, code: str, ok: bool, detail: str = "", sla: int = 15):
    if ok:
        cur.execute(
            """update v1.feed set last_ok_at=now(), status='ok', last_error=null,
                      sla_seconds=%s
               where code=%s""",
            (sla, code),
        )
        cur.execute(
            "insert into v1.feed_check (feed_id, latency_ms, ok, detail) "
            "select id, null, true, %s from v1.feed where code=%s",
            (detail[:200], code),
        )
    else:
        cur.execute(
            """update v1.feed set status='error', last_error=%s, last_error_at=now()
               where code=%s""",
            (detail[:200], code),
        )


def touch_run(cur, magic: int, stale_after: int = 120):
    cur.execute(
        "update v1.strategy_run set last_heartbeat_at=now(), status='running' "
        "where magic=%s and stopped_at is null",
        (magic,),
    )


def ingest_live(cur) -> bool:
    tel = read_json(LIVE_DIR / "wr_telemetry.json")
    if not tel:
        touch_feed(cur, "mt5_live", False, "wr_telemetry.json tidak terbaca")
        return False
    age = time.time() - (LIVE_DIR / "wr_telemetry.json").stat().st_mtime
    acct = get_account(cur, str(tel.get("account", "")), "live")
    if not acct:
        touch_feed(cur, "mt5_live", False, f"akun {tel.get('account')} tidak ada di v1.account")
        return False
    acct_id, cur_ccy = acct
    snapshot(
        cur, acct_id, tel.get("currency") or cur_ccy,
        tel.get("balance"), tel.get("equity"), tel.get("margin"),
        tel.get("free_margin"), tel.get("floating_pnl"),
    )
    for p in tel.get("positions") or []:
        inst = instrument_id(cur, p.get("symbol", ""), p.get("open_price") or p.get("price"))
        upsert_position(
            cur, acct_id, inst, p.get("ticket") or p.get("id"),
            "buy" if str(p.get("side", "")).upper().startswith("B") else "sell",
            p.get("volume") or p.get("qty"), p.get("open_price") or p.get("price"),
            p.get("sl"), p.get("tp"), ts(p.get("open_time")) or datetime.now(timezone.utc),
            p.get("profit"),
        )
    touch_feed(cur, "mt5_live", age <= 30, f"umur {int(age)}s", sla=45)
    touch_run(cur, 20261104)
    return age <= 30


def ingest_live_deals(cur) -> int:
    path = LIVE_DIR / "wr_deals.jsonl"
    if not path.exists() or path.stat().st_size == 0:
        return 0
    acct = get_account(cur, "452009427", "live")
    if not acct:
        return 0
    acct_id = acct[0]
    n = 0
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        ticket = d.get("ticket")
        if not ticket:
            continue
        profit = float(d.get("profit") or 0) + float(d.get("swap") or 0) + float(d.get("commission") or 0)
        inst = instrument_id(cur, d.get("symbol", ""), d.get("close_price"))
        cur.execute(
            """insert into v1.ledger_entry
                 (account_id, ts, kind, amount, currency, ref_table, ref_id, note)
               values (%s, coalesce(%s::timestamptz, now()), 'trade', %s, %s, 'deal', %s, %s)
               on conflict do nothing""",
            (acct_id, ts(d.get("close_time")), profit, acct[1] if len(acct) > 1 else "USC",
             int(ticket), f"{d.get('symbol')} {d.get('side')} {d.get('volume')}"),
        )
        if inst:
            cur.execute(
                """insert into v1.position
                     (account_id, instrument_id, ext_id, side, qty_open, qty_closed,
                      entry_price, exit_price, opened_at, closed_at, realized_pnl)
                   values (%s,%s,%s,%s,%s,%s,%s,%s, coalesce(%s::timestamptz, now()),
                           coalesce(%s::timestamptz, now()), %s)
                   on conflict (account_id, ext_id) do update set
                     exit_price=excluded.exit_price, closed_at=excluded.closed_at,
                     realized_pnl=excluded.realized_pnl""",
                (acct_id, inst, str(d.get("position") or ticket),
                 "buy" if str(d.get("side", "")).upper().startswith("B") else "sell",
                 d.get("volume") or 0, d.get("volume") or 0,
                 d.get("close_price"), d.get("close_price"),
                 ts(d.get("open_time")) or ts(d.get("close_time")), ts(d.get("close_time")), profit),
            )
        n += 1
    return n


def ingest_demo(cur) -> bool:
    st = read_json(DEMO_STATUS)
    if not st:
        touch_feed(cur, "mt5_demo", False, "MTRB_Pro_status.json tidak terbaca")
        return False
    age = time.time() - DEMO_STATUS.stat().st_mtime
    acc = st.get("account") or {}
    acct = get_account(cur, str(acc.get("login_tail", "")), "demo")
    if not acct:
        touch_feed(cur, "mt5_demo", False, "akun demo tidak ada di v1.account")
        return False
    acct_id, cur_ccy = acct
    snapshot(cur, acct_id, acc.get("currency") or cur_ccy, acc.get("balance"),
             acc.get("equity"), acc.get("margin"), acc.get("free_margin"), None)
    for p in st.get("positions") or []:
        inst = instrument_id(cur, p.get("symbol", ""), p.get("open_price") or p.get("price"))
        upsert_position(cur, acct_id, inst, p.get("ticket") or p.get("id"),
                        "buy" if str(p.get("side", "")).upper().startswith("B") else "sell",
                        p.get("volume") or p.get("qty"), p.get("open_price") or p.get("price"),
                        p.get("sl"), p.get("tp"),
                        ts(p.get("open_time")) or datetime.now(timezone.utc))
    touch_feed(cur, "mt5_demo", age <= 60, f"umur {int(age)}s", sla=45)
    touch_run(cur, 772001)
    return age <= 60


def main() -> int:
    try:
        with psycopg.connect(DSN, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                live_ok = ingest_live(cur)
                deals = ingest_live_deals(cur)
                demo_ok = ingest_demo(cur)
            conn.commit()
        log(f"ok live={live_ok} demo={demo_ok} deals={deals}")
        return 0
    except Exception as e:  # noqa: BLE001
        log(f"ERROR {type(e).__name__}: {str(e)[:300]}")
        log("TRACE " + traceback.format_exc(limit=2).replace("\n", " | ")[:300])
        return 1


if __name__ == "__main__":
    sys.exit(main())
