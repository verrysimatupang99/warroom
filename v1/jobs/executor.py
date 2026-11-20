"""Eksekusi aksi yang sudah di-arm + di-confirm.

Ambil event CONFIRM:* yang belum dieksekusi, jalankan aksinya lewat systemctl,
lalu tandai executed=true + tulis jejak hasilnya.

Aksi yang diizinkan (whitelist):
  pause_ea        -> systemctl stop <unit>
  resume_ea       -> systemctl start <unit>
  restart_instance-> systemctl restart <unit>
Unit dipetakan dari nama target, TIDAK dari input bebas.
"""
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone

import psycopg

DSN = os.environ["V1_DSN"]
LOG = "/var/log/wr-executor.log"

# Gerbang aman: live hanya boleh dieksekusi kalau bendera ini "1".
# Tanpa bendera, target live ditolak walau sudah di-arm + di-confirm.
LIVE_ENABLED = os.environ.get("WR_EXEC_LIVE", "0") == "1"

# target (nama strategi) -> unit systemd
UNIT_MAP = {
    "mtrb_pro": "mt5-ex-demo",
    "gold_reaper_hexa": "mt5-ex-live",
    "demo": "mt5-ex-demo",
    "live": "mt5-ex-live",
}
LIVE_TARGETS = {"gold_reaper_hexa", "live"}

ACTION_CMD = {
    "pause_ea": "stop",
    "resume_ea": "start",
    "restart_instance": "restart",
}


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def run_systemctl(verb: str, unit: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["/usr/bin/systemctl", verb, unit],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()[:200]
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]


def main() -> int:
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """select id, actor, action, after_json
                   from v1.event
                   where action like 'CONFIRM:%%'
                     and (after_json->>'executed')::boolean = false
                     and after_json->>'blocked' is null
                     and after_json->>'skipped' is null
                   order by id asc
                   limit 5"""
            )
            pending = cur.fetchall()

        for ev in pending:
            armed_id = ev["after_json"].get("armed_id")
            target = ev["after_json"].get("target")
            # aksi & target sebenarnya ada di event ARM yang dirujuk
            arm_action = None
            if armed_id:
                with conn.cursor() as c:
                    c.execute(
                        """select action, after_json->>'target'
                           from v1.event where id=%s""",
                        (armed_id,),
                    )
                    r = c.fetchone()
                    if r:
                        arm_action = r[0]
                        target = target or r[1]
            verb = ACTION_CMD.get((arm_action or "").replace("ARM:", ""))
            unit = UNIT_MAP.get(target)
            if not unit or not verb:
                log(f"event {ev['id']}: skip permanen target/aksi tidak dikenal ({target})")
                with conn.cursor() as c:
                    c.execute(
                        """update v1.event
                           set after_json = after_json || jsonb_build_object(
                               'executed', false, 'skipped', true,
                               'error', 'target/aksi tidak dikenal')
                           where id=%s""",
                        (ev["id"],),
                    )
                continue

            # gerbang live: tolak kalau target live dan bendera mati
            if target in LIVE_TARGETS and not LIVE_ENABLED:
                log(f"event {ev['id']}: DITOLAK target live ({target}), WR_EXEC_LIVE=0")
                with conn.cursor() as c:
                    c.execute(
                        """update v1.event
                           set after_json = after_json || jsonb_build_object(
                               'executed', false, 'blocked', 'live_locked',
                               'error', 'eksekusi live terkunci (WR_EXEC_LIVE=0)')
                           where id=%s""",
                        (ev["id"],),
                    )
                continue

            log(f"event {ev['id']}: {verb} {unit} (target={target})")
            ok, detail = run_systemctl(verb, unit)
            with conn.cursor() as c:
                c.execute(
                    """update v1.event
                       set after_json = after_json || jsonb_build_object(
                           'executed', %s::boolean, 'unit', %s::text, 'verb', %s::text,
                           'result_ok', %s::boolean, 'result_detail', %s::text,
                           'executed_at', to_char(now(), 'YYYY-MM-DD HH24:MI:SS'))
                       where id=%s::bigint""",
                    (ok, unit, verb, ok, detail, ev["id"]),
                )
                c.execute(
                    """insert into v1.event (actor, action, target_table, target_id, after_json)
                       values (%s::text, 'EXEC:' || %s::text, 'strategy_run', 0,
                               jsonb_build_object('unit', %s::text, 'verb', %s::text,
                                                  'ok', %s::boolean, 'detail', %s::text))""",
                    (ev["actor"], ev["action"].replace("CONFIRM:", ""), unit, verb, ok, detail),
                )
            log(f"event {ev['id']}: hasil ok={ok} {detail}")
        conn.commit()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR " + traceback.format_exc(limit=2).replace("\n", " | ")[:300])
        sys.exit(1)
