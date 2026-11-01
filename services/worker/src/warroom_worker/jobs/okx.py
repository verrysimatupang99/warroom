"""Job `okx-sync`: saldo dan posisi OKX read-only menjadi fakta.

Sumber: `/etc/warroom/okx.env` (600 root) berisi API key dengan izin Read dan
whitelist IP host. Job ini tidak pernah mengirim order atau mengubah akun.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as SASession
from warroom_core.db import Job

from .base import _tulis_fakta


def handler_okx_sync(s: SASession, job: Job) -> str:
    from live_trading import okx_account as ox

    ttl = int(job.payload_json.get("ttl_s", 900))
    akun = ox.ringkas_akun()
    posisi = ox.ringkas_posisi()
    _tulis_fakta(
        s,
        kind="okx.account",
        key="ringkas",
        value=akun,
        source="OKX /account/balance (read-only)",
        ttl_s=ttl,
    )
    _tulis_fakta(
        s,
        kind="okx.positions",
        key="ringkas",
        value=posisi,
        source="OKX /account/positions (read-only)",
        ttl_s=ttl,
    )
    return (
        f"equity_usd={akun['total_eq_usd']} mata_uang={akun['mata_uang']} "
        f"posisi={posisi['jumlah']} upl_usd={posisi['upl_total_usd']}"
    )
