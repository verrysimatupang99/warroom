"""Collector market non-forex (monitor/paper, TIDAK trading).

Tiap feed: ambil harga/odds dari sumber publik, tulis ke v1.quote + v1.feed_check.
Gagal satu feed tidak menggagalkan yang lain.
"""
import json
import os
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone

import psycopg

DSN = os.environ["V1_DSN"]

FEEDS = {
    # code: (market, provider, url, parser)
    "okx": ("crypto", "okx-rest",
            "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
            "okx"),
    "polymarket": ("prediction", "gamma-rest",
                   "https://gamma-api.polymarket.com/markets?closed=false&limit=25",
                   "polymarket"),
    "idx": ("equity", "idx-yahoo",
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE?range=5d&interval=1d",
            "idx"),
}


def fetch(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": "warroom-v1/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def parse_okx(data):
    out = []
    for t in (data.get("data") or [])[:40]:
        sym = t.get("instId", "")
        last = t.get("last")
        if last is None:
            continue
        out.append((sym, float(last)))
    return out


def parse_polymarket(data):
    out = []
    for m in (data if isinstance(data, list) else [])[:25]:
        q = m.get("question", "")[:60]
        price = m.get("outcomePrices")
        if price:
            try:
                p = json.loads(price)
                out.append((q, float(p[0])))
            except Exception:
                continue
    return out


def parse_idx(data):
    res = (data.get("chart") or {}).get("result") or []
    if not res:
        return []
    m = (res[0] or {}).get("meta") or {}
    px = m.get("regularMarketPrice")
    sym = m.get("symbol", "")
    if px is None or not sym:
        return []
    return [(sym, float(px))]


PARSERS = {"okx": parse_okx, "polymarket": parse_polymarket, "idx": parse_idx}


def get_instrument(cur, venue_id, market, symbol, kind, quote):
    cur.execute(
        """select id from v1.instrument
           where venue_id=%s and symbol=%s and kind=%s""",
        (venue_id, symbol[:120], kind),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """insert into v1.instrument (venue_id, market, symbol, kind, quote_ccy)
           values (%s,%s,%s,%s,%s) returning id""",
        (venue_id, market, symbol[:120], kind, quote),
    )
    return cur.fetchone()[0]


def run_feed(cur, code: str, market: str, provider: str, url: str, parser_name: str):
    t0 = time.time()
    try:
        data = fetch(url)
        points = PARSERS[parser_name](data)
        lat = int((time.time() - t0) * 1000)
        cur.execute(
            """update v1.feed set status='ok', last_ok_at=now(), last_error=null
               where code=%s""",
            (code,),
        )
        cur.execute(
            "insert into v1.feed_check (feed_id, latency_ms, ok, detail) "
            "select id, %s, true, %s from v1.feed where code=%s",
            (lat, f"{len(points)} titik", code),
        )
        return points
    except Exception as e:  # noqa: BLE001
        cur.execute(
            """update v1.feed set status='error', last_error=%s, last_error_at=now()
               where code=%s""",
            (str(e)[:200], code),
        )
        cur.execute(
            "insert into v1.feed_check (feed_id, latency_ms, ok, detail) "
            "select id, null, false, %s from v1.feed where code=%s",
            (str(e)[:200], code),
        )
        return []


SLA_MIN = {"okx": 90}  # collector 60s -> SLA < 60s bikin warn palsu di /v1/status


def main() -> int:
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("set search_path to v1, public")
            for code, sla in SLA_MIN.items():
                cur.execute(
                    "update v1.feed set sla_seconds=%s where code=%s and (sla_seconds is null or sla_seconds < %s)",
                    (sla, code, sla),
                )
            for code, (market, provider, url, parser) in FEEDS.items():
                cur.execute("select id from v1.venue where code=%s", (code,))
                v = cur.fetchone()
                if not v:
                    cur.execute(
                        """insert into v1.venue (code, kind, name)
                           values (%s,
                             case %s when 'crypto' then 'exchange'
                                     when 'prediction' then 'prediction'
                                     when 'onchain' then 'chain'
                                     else 'exchange' end::venue_kind, %s)
                           returning id""",
                        (code, market, provider),
                    )
                    v = cur.fetchone()
                venue_id = v[0]

                kind = {"crypto": "perp", "equity": "stock"}.get(market, "binary")
                qccy = "IDR" if market == "equity" else "USD"
                points = run_feed(cur, code, market, provider, url, parser)
                for sym, price in points[:30]:
                    iid = get_instrument(cur, venue_id, market, sym, kind, qccy)
                    cur.execute(
                        """insert into v1.quote (instrument_id, ts, last, feed_id)
                           values (%s, date_trunc('second', now()), %s,
                                   (select id from v1.feed where code=%s))
                           on conflict (instrument_id, ts) do update set last=excluded.last""",
                        (iid, price, code),
                    )
        conn.commit()
    print("collector ok")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(traceback.format_exc(limit=2)[:300])
        sys.exit(1)
