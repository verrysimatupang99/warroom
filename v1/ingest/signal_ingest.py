"""Ingest sinyal (keputusan engine) -> v1.signal.

Sumber:
  1. Demo (MTRB_Pro_status.json): tiap engine punya 'status' (alasan tunggu/entry)
     dan 'enabled'. Satu baris per engine per bar M5.
  2. Live (wr_telemetry.json): eval_alasan + gate (atr, rsi, ema, sesi).

Idempoten: unique (strategy_run_id, engine, bar_ts). Bar M5 = floor(now/300).
Decision: 'rejected' bila alasan bukan entry; 'approved' bila ada entry nyata.
"""
import json
import os
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import psycopg

DSN = os.environ["V1_DSN"]
DEMO_STATUS = Path(
    "/home/admin/.wine-exness/drive_c/users/admin/AppData/Roaming/"
    "MetaQuotes/Terminal/Common/Files/MTRB_Pro_status.json"
)
LIVE_TEL = Path(
    "/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Live/MQL5/Files/wr_telemetry.json"
)


def bar_ts():
    """Awal bar M5 saat ini (UTC)."""
    now = int(time.time())
    return datetime.fromtimestamp(now - (now % 300), UTC)


def norm_reason(txt: str) -> str:
    """Ambil kode singkat dari teks alasan."""
    t = (txt or "").strip()
    if not t or t == "-":
        return "NO_REASON"
    low = t.lower()
    if "di luar sesi" in low or "luar sesi" in low:
        return "DI_LUAR_SESI"
    if "tren turun" in low or "turun" in low:
        return "TREN_TURUN"
    if "tren naik" in low or "naik" in low:
        return "TREN_NAIK"
    if "menunggu" in low or "tunggu" in low:
        return "MENUNGGU_KONFIRMASI"
    if "nonaktif" in low:
        return "ENGINE_NONAKTIF"
    return "MENUNGGU_KONFIRMASI"


def write_signal(cur, run_id, inst_id, engine, reason, gate, side=None, entry=None):
    ts = bar_ts()
    decision = "approved" if reason in ("ENTRY", "ENTRY_BUY", "ENTRY_SELL") else "rejected"
    cur.execute(
        """insert into v1.signal
             (strategy_run_id, instrument_id, ts, engine, side, decision,
              reason_code, gate_json, entry)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (strategy_run_id, engine, ts) do nothing""",
        (run_id, inst_id, ts, engine, side, decision, reason,
         json.dumps(gate, ensure_ascii=False), entry),
    )


def get_run(cur, magic):
    cur.execute(
        """select r.id, r.instrument_id from v1.strategy_run r
           where r.magic=%s and r.stopped_at is null order by r.id desc limit 1""",
        (magic,),
    )
    return cur.fetchone()


def main() -> int:
    ts = bar_ts()
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            # ---------- DEMO: MTRB engines ----------
            try:
                st = json.loads(DEMO_STATUS.read_text())
                run = get_run(cur, 772001)
                if run and st.get("engines"):
                    for e in st["engines"]:
                        enabled = bool(e.get("enabled"))
                        status = (e.get("status") or "").strip()
                        if not enabled:
                            reason = "ENGINE_NONAKTIF"
                        elif not status or status == "-":
                            reason = "NO_REASON"
                        else:
                            reason = norm_reason(status)
                        gate = {
                            "atr": e.get("atr"), "rsi": e.get("rsi"),
                            "spread": e.get("spread"), "sesi": st.get("sessions", {}).get("now"),
                            "enabled": enabled, "positions": e.get("positions"),
                            "today_pl": e.get("today_pl"),
                        }
                        write_signal(cur, run[0], run[1], e.get("id") or e.get("name"),
                                     reason, gate)
            except Exception:
                print("demo error:", traceback.format_exc(limit=1)[:200])

            # ---------- LIVE: Gold Reaper evaluasi ----------
            try:
                tel = json.loads(LIVE_TEL.read_text())
                run = get_run(cur, 20261104)
                if run:
                    reason = norm_reason(tel.get("eval_alasan"))
                    gate = {
                        "atr_m5": tel.get("atr_m5"), "rsi": tel.get("eval_rsi"),
                        "spread": tel.get("eval_spread"), "sesi": tel.get("eval_sesi"),
                        "ema_fast": tel.get("eval_ema_fast"), "ema_slow": tel.get("eval_ema_slow"),
                        "tren": tel.get("eval_tren"), "eval_alasan": tel.get("eval_alasan"),
                    }
                    write_signal(cur, run[0], run[1], "GOLD", reason, gate)
            except Exception:
                print("live error:", traceback.format_exc(limit=1)[:200])
        conn.commit()
    print(f"signal ingest ok bar={ts.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
