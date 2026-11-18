"""War Room v1 API — status ringkas (feed freshness, strategy heartbeat, akun).

Endpoint ini yang membuat /sistem bisa jujur: setiap angka membawa umur data.
Sebagian besar hanya baca (SELECT). Dua endpoint tulis (arm/confirm) hanya mencatat
niat + jejak ke v1.event dan TIDAK mengeksekusi apa pun di akun trading.
"""
import os
import time
from datetime import datetime, timezone

import psycopg
from fastapi import FastAPI

DSN = os.environ.get("V1_DSN", "")
app = FastAPI(title="War Room v1 API", version="1.0.0")


def q(sql: str, params=None):
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params or ())
            try:
                return cur.fetchall()
            except psycopg.ProgrammingError:
                return []


@app.get("/v1/health")
def health():
    try:
        q("select 1")
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


@app.get("/v1/status")
def status():
    t0 = time.time()
    feeds = q(
        """
        select code, provider, market, owner_host, sla_seconds, status, last_ok_at,
               last_error,
               case when last_ok_at is null then null
                    else extract(epoch from (now() - last_ok_at))::int end as age_s
        from v1.feed
        where active
        order by code
        """
    )
    for f in feeds:
        age, sla = f["age_s"], f["sla_seconds"]
        if age is None:
            f["level"], f["fresh"] = "unknown", False
        elif age <= sla:
            f["level"], f["fresh"] = "ok", True
        elif age <= sla * 3:
            f["level"], f["fresh"] = "warn", False
        else:
            f["level"], f["fresh"] = "stale", False

    runs = q(
        """
        select s.code as strategy, s.version, s.market, s.status as strategy_status,
               a.label as account, a.mode, a.currency, r.magic, r.status, r.unit,
               extract(epoch from (now() - r.last_heartbeat_at))::int as heartbeat_age_s
        from v1.strategy_run r
        join v1.strategy s on s.id = r.strategy_id
        left join v1.account a on a.id = r.account_id
        where r.stopped_at is null
        order by s.code
        """
    )
    for r in runs:
        age = r["heartbeat_age_s"]
        r["stale"] = age is None or age > 120

    accounts = q(
        """
        select label, right(coalesce(login_ext, ''), 3) as login_tail, mode, currency,
               kind, status, status_at
        from v1.account
        where active
        order by mode desc, label
        """
    )

    summary = {
        "feeds_ok": sum(1 for f in feeds if f["level"] == "ok"),
        "feeds_stale": sum(1 for f in feeds if f["level"] in ("warn", "stale")),
        "runs_stale": sum(1 for r in runs if r["stale"]),
    }
    return {
        "ok": True,
        "now": datetime.now(timezone.utc),
        "db": {"ok": True, "latency_ms": int((time.time() - t0) * 1000)},
        "summary": summary,
        "feeds": feeds,
        "runs": runs,
        "accounts": accounts,
    }

@app.get("/v1/recon")
def recon():
    """Status rekonsiliasi terakhir per akun: broker vs ledger."""
    rows = q(
        """
        select distinct on (r.account_id)
               a.label, a.mode, a.currency, r.ts, r.broker_balance, r.ledger_sum,
               r.baseline, r.expected, r.drift, r.ok
        from v1.recon_check r
        join v1.account a on a.id = r.account_id
        order by r.account_id, r.ts desc
        """
    )
    return {
        "ok": True,
        "all_ok": all(r["ok"] for r in rows) if rows else None,
        "accounts": rows,
    }

@app.get("/v1/ledger")
def ledger(limit: int = 100):
    """Mutasi uang terbaru + total per akun."""
    rows = q(
        """
        select l.id, l.ts, a.label as account, a.mode, l.kind, l.amount, l.currency,
               l.ref_table, l.ref_id, l.note
        from v1.ledger_entry l
        join v1.account a on a.id = l.account_id
        order by l.ts desc, l.id desc
        limit %s
        """,
        (min(max(limit, 1), 500),),
    )
    totals = q(
        """
        select a.label as account, a.currency, count(*) as n,
               coalesce(sum(l.amount), 0) as total
        from v1.ledger_entry l
        join v1.account a on a.id = l.account_id
        group by a.label, a.currency
        order by a.label
        """
    )
    return {"ok": True, "totals": totals, "entries": rows}


@app.get("/v1/jejak")
def jejak(limit: int = 100):
    """Jejak audit: siapa mengubah apa (trigger DB, tidak bisa dilewati aplikasi)."""
    rows = q(
        """
        select id, ts, actor, action, target_table, target_id, before_json, after_json
        from v1.event
        order by id desc
        limit %s
        """,
        (min(max(limit, 1), 500),),
    )
    return {"ok": True, "events": rows}

@app.get("/v1/forex")
def forex():
    """Ringkasan forex: akun (live & demo), posisi terbuka, strategi, PnL hari ini."""
    accounts = q(
        """
        select a.id, a.label, a.mode, a.currency, a.status as account_status,
               s.ts as snapshot_ts, s.balance, s.equity, s.free_margin, s.floating_pnl,
               extract(epoch from (now() - s.ts))::int as age_s
        from v1.account a
        left join lateral (
            select * from v1.account_snapshot x
            where x.account_id = a.id order by x.ts desc limit 1
        ) s on true
        where a.active and a.venue_id = (select id from v1.venue where code='exness')
        order by a.mode desc
        """
    )
    for a in accounts:
        cur = q(
            """select coalesce(sum(amount),0) as pnl, count(*) as n
               from v1.ledger_entry
               where account_id=%s and kind='trade' and ts >= date_trunc('day', now())""",
            (a["id"],),
        )[0]
        a["pnl_today"] = cur["pnl"]
        a["trades_today"] = cur["n"]

    positions = q(
        """
        select p.id, a.label as account, a.mode, i.symbol, p.side, p.qty_open,
               p.entry_price, p.sl, p.tp1, p.be_active, p.opened_at,
               extract(epoch from (now() - p.opened_at))::int as age_s,
               r.magic
        from v1.position p
        join v1.account a on a.id = p.account_id
        join v1.instrument i on i.id = p.instrument_id
        left join v1.strategy_run r on r.id = p.strategy_run_id
        where p.closed_at is null
        order by p.opened_at desc
        """
    )

    runs = q(
        """
        select s.code as strategy, s.version, a.label as account, a.mode, r.magic, r.unit,
               r.status, extract(epoch from (now() - r.last_heartbeat_at))::int as heartbeat_age_s
        from v1.strategy_run r
        join v1.strategy s on s.id = r.strategy_id
        left join v1.account a on a.id = r.account_id
        where r.stopped_at is null
        order by s.code
        """
    )
    for r in runs:
        r["stale"] = r["heartbeat_age_s"] is None or r["heartbeat_age_s"] > 120

    return {"ok": True, "accounts": accounts, "positions": positions, "runs": runs}

@app.get("/v1/signals")
def signals(limit: int = 60):
    """Keputusan terbaru per engine + alasan (approved & rejected)."""
    rows = q(
        """
        select s.id, s.ts, s.engine, s.side, s.decision, s.reason_code, s.gate_json,
               i.symbol, a.label as account, a.mode, st.code as strategy
        from v1.signal s
        join v1.strategy_run r on r.id = s.strategy_run_id
        join v1.strategy st on st.id = r.strategy_id
        left join v1.account a on a.id = r.account_id
        left join v1.instrument i on i.id = s.instrument_id
        order by s.ts desc, s.id desc
        limit %s
        """,
        (min(max(limit, 1), 300),),
    )
    return {"ok": True, "signals": rows}


@app.get("/v1/journal")
def journal(limit: int = 100):
    """Riwayat deal (posisi tertutup) per akun, dari ledger trade."""
    rows = q(
        """
        select l.id, l.ts, a.label as account, a.mode, l.amount as pnl, l.currency,
               l.ref_id as ticket, l.note
        from v1.ledger_entry l
        join v1.account a on a.id = l.account_id
        where l.kind = 'trade'
        order by l.ts desc, l.id desc
        limit %s
        """,
        (min(max(limit, 1), 300),),
    )
    return {"ok": True, "deals": rows}


@app.post("/v1/arm")
def arm(body: dict):
    """Arm sebuah aksi (mis. pause EA). Belum mengeksekusi apa pun — hanya mencatat niat
    dan mengembalikan token konfirmasi. Eksekusi butuh POST /v1/confirm dengan token itu.
    """
    action = str(body.get("action") or "").strip()
    target = str(body.get("target") or "").strip()
    if not action or not target:
        return {"ok": False, "error": "action dan target wajib"}
    allowed = {"pause_ea", "resume_ea", "restart_instance"}
    if action not in allowed:
        return {"ok": False, "error": f"aksi tidak diizinkan; pilih salah satu: {sorted(allowed)}"}
    token = os.urandom(16).hex()
    cur = q(
        """insert into v1.event (actor, action, target_table, target_id, after_json)
           values (%s, 'ARM:' || %s::text, 'strategy_run', 0,
                   jsonb_build_object('target', %s::text, 'confirm_token', %s::text,
                                      'state', 'armed'))
           returning id""",
        (str(body.get("actor") or "operator"), action, target, token),
    )
    return {"ok": True, "armed_id": cur[0]["id"], "confirm_token": token,
            "note": "belum dieksekusi; kirim token ke /v1/confirm"}


@app.post("/v1/confirm")
def confirm(body: dict):
    """Konfirmasi aksi yang sudah di-arm. Baru di sini aksi dieksekusi (dan diaudit)."""
    token = str(body.get("confirm_token") or "").strip()
    if not token:
        return {"ok": False, "error": "confirm_token wajib"}
    ev = q(
        """select id, after_json from v1.event
           where action like 'ARM:%%' and after_json->>'confirm_token' = %s
           order by id desc limit 1""",
        (token,),
    )
    if not ev:
        return {"ok": False, "error": "token tidak dikenal atau sudah dipakai"}
    action = ev[0]["after_json"].get("target")
    q(
        """insert into v1.event (actor, action, target_table, target_id, after_json)
           values (%s, 'CONFIRM:' || %s::text, 'strategy_run', 0,
                   jsonb_build_object('armed_id', %s::bigint, 'state', 'confirmed',
                                      'executed', false,
                                      'note', 'eksekusi nyata belum tersambung (read-only v1)'))""",
        (str(body.get("actor") or "operator"), action, ev[0]["id"]),
    )
    return {"ok": True, "action": action, "executed": False,
            "note": "aksi dicatat sebagai confirmed; eksekusi nyata belum tersambung di v1"}

@app.get("/v1/markets")
def markets():
    """Harga terakhir per market non-forex + status feed-nya (monitor saja)."""
    feeds = {r["code"]: r for r in q(
        """select code, status, last_ok_at,
                  extract(epoch from (now() - last_ok_at))::int as age_s
           from v1.feed where code in ('okx','polymarket','gmgn','idx')"""
    )}
    def latest(market):
        return q(
            """
            select i.symbol, q.last, q.ts,
                   extract(epoch from (now() - q.ts))::int as age_s
            from v1.quote q
            join v1.instrument i on i.id = q.instrument_id
            where i.market = %s
              and q.ts = (select max(q2.ts) from v1.quote q2
                          where q2.instrument_id = i.id)
            order by i.symbol
            limit 40
            """,
            (market,),
        )
    return {
        "ok": True,
        "feeds": feeds,
        "crypto": latest("crypto"),
        "prediction": latest("prediction"),
        "equity": latest("equity"),
        "onchain": latest("onchain"),
    }
