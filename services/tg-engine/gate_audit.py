"""Audit trail keputusan gate. Append-only, hanya mencatat saat keputusan BERUBAH."""

from __future__ import annotations

import datetime
import json
import sqlite3
import sys

sys.path.insert(0, "/home/admin/tg-trading-engine")
from db import DB_PATH


def record(signal_id, signal, verdict, balance):
    """Catat keputusan bila berbeda dari catatan terakhir untuk signal_id.

    Mengembalikan True bila baris baru ditulis. Idempoten: polling queue
    berulang tidak membanjiri tabel.
    """
    reasons = json.dumps(verdict.get("reasons") or [], ensure_ascii=False)
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        try:
            row = conn.execute(
                "select decision, reasons_json from gate_decisions "
                "where signal_id = ? order by id desc limit 1",
                (signal_id,),
            ).fetchone()
            if row and row[0] == verdict.get("decision") and row[1] == reasons:
                return False
            conn.execute(
                "insert into gate_decisions (signal_id, channel_name, symbol, action,"
                " entry_low, entry_high, sl, tp1, rr, age_hours, decision,"
                " reasons_json, lot, balance, min_rr, max_age_hours, created_at)"
                " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    signal_id,
                    signal.get("channel"),
                    signal.get("symbol"),
                    signal.get("action"),
                    signal.get("entry_low"),
                    signal.get("entry_high"),
                    signal.get("sl"),
                    signal.get("tp1"),
                    verdict.get("rr"),
                    verdict.get("age_h"),
                    verdict.get("decision"),
                    reasons,
                    verdict.get("lot"),
                    balance,
                    (verdict.get("policy") or {}).get("min_rr"),
                    (verdict.get("policy") or {}).get("max_age_hours"),
                    datetime.datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        print("[gate_audit] gagal catat signal", signal_id, ":", e, flush=True)
        return False


def recent(limit=20):
    """Ambil keputusan terbaru untuk dashboard/forensik."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        cur = conn.execute(
            "select id, signal_id, channel_name, symbol, action, rr, decision,"
            " reasons_json, lot, created_at from gate_decisions order by id desc limit ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]
    finally:
        conn.close()
