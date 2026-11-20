"""Rekonsiliasi: saldo broker vs ledger.

Aturan:
  expected = baseline + sum(ledger_entry.amount)
  drift    = broker_balance - expected
  ok       = |drift| <= toleransi (0.01 untuk USD/USC)

Baseline diset sekali per akun saat pertama kali direkonsiliasi
(= saldo broker saat itu - isi ledger saat itu), lalu dibekukan.
Kalau drift != 0, itu berarti ada mutasi uang yang tidak tercatat.
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import psycopg

DSN = os.environ["V1_DSN"]
LOG = "/var/log/wr-recon.log"
TOL = Decimal("0.01")


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select a.id, a.label, a.mode, a.currency,
                          (select balance from v1.account_snapshot s
                             where s.account_id=a.id order by ts desc limit 1) as bal,
                          (select coalesce(sum(amount),0) from v1.ledger_entry l
                             where l.account_id=a.id) as led
                   from v1.account a where a.active order by a.id"""
            )
            rows = cur.fetchall()

            for acct_id, label, mode, ccy, bal, led in rows:
                if bal is None:
                    log(f"skip {label}: belum ada snapshot")
                    continue
                bal = Decimal(str(bal)); led = Decimal(str(led))
                cur.execute("select amount from v1.account_baseline where account_id=%s", (acct_id,))
                b = cur.fetchone()
                if b is None:
                    base = bal - led
                    cur.execute(
                        """insert into v1.account_baseline (account_id, amount, currency, note)
                           values (%s,%s,%s,'baseline otomatis saat recon pertama')""",
                        (acct_id, base, ccy),
                    )
                    log(f"baseline {label}: {base} {ccy}")
                else:
                    base = Decimal(str(b[0]))

                expected = base + led
                drift = bal - expected
                ok = abs(drift) <= TOL
                cur.execute(
                    """insert into v1.recon_check
                         (account_id, broker_balance, ledger_sum, baseline, expected, drift, ok, source)
                       values (%s,%s,%s,%s,%s,%s,%s,'recon.py')""",
                    (acct_id, bal, led, base, expected, drift, ok),
                )
                if not ok:
                    cur.execute(
                        """insert into v1.event (actor, action, target_table, target_id, after_json)
                           values ('recon.py','recon_drift','account',%s,
                                   jsonb_build_object('broker',%s::text,'expected',%s::text,'drift',%s::text,'currency',%s::text))""",
                        (acct_id, str(bal), str(expected), str(drift), ccy),
                    )
                log(f"{label}: broker={bal} expected={expected} drift={drift} ok={ok}")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
