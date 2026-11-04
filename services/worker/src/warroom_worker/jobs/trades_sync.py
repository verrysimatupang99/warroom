"""Job `trades-crypto-sync`: ledger paper crypto → tabel `trades` (idempoten).

Ledger adalah kebenaran yang ditulis eksekutor; DB adalah tempat jurnal API
membaca. Job ini menjembatani keduanya tiap beberapa menit. Baris yang sudah
ada tidak disentuh; yang baru masuk ditambahkan; baris rusak dilaporkan di
hasil job, bukan didiam-diamkan.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Job, Trade


def handler_trades_crypto_sync(s: SASession, job: Job) -> str:
    from live_trading.config import get_settings
    from sqlalchemy import text
    from warroom_core.trades_crypto import baca_ledger, ke_trade

    stg = get_settings()
    ledger = stg.state_dir / "crypto_equity.jsonl"
    rows = baca_ledger(ledger)
    rusak = 0
    # baca_ledger tidak membedakan kosong vs rusak; hitung ulang di sini agar
    # job-health melihat ledger yang mulai rusak sebelum angkanya dipercaya.
    try:
        total_ln = len([ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()])
    except OSError:
        total_ln = len(rows)
    rusak = total_ln - len(rows)
    if total_ln and rusak:
        raise RuntimeError(f"ledger crypto punya {rusak}/{total_ln} baris rusak — ingest ditahan")

    opened: dict[str, dict] = {}
    closed: dict[str, Any] = {}
    for tipe, created, payload in s.execute(
        text(
            "select type, created_at, payload_json from events "
            "where type in ('trade.opened','trade.closed')"
        )
    ):
        d = payload if isinstance(payload, dict) else json.loads(payload)
        sid = str(d.get("signal_id") or "")
        if not sid:
            continue
        if tipe == "trade.opened":
            opened.setdefault(sid, d)
        elif tipe == "trade.closed":
            closed.setdefault(sid, created)

    trades = []
    skip: list[str] = []
    for r in rows:
        t = ke_trade(r, opened.get(str(r.get("signal_id"))), closed.get(str(r.get("signal_id"))))
        (trades.append(t) if t else skip.append(str(r.get("signal_id"))))

    kunci_ada = {
        (v, m, e)
        for v, m, e in s.query(Trade.venue, Trade.mode, Trade.ext_id).filter(
            Trade.venue == "crypto", Trade.mode == "paper"
        )
    }
    baru = [t for t in trades if (t.venue, t.mode, t.ext_id) not in kunci_ada]
    if baru:
        s.add_all(baru)
        s.add(
            Event(
                type="trade.ingest",
                actor="trades-crypto-sync",
                payload_json={"masuk": len(baru), "total_db": len(kunci_ada) + len(baru)},
            )
        )
    return f"ledger={len(rows)} db={len(kunci_ada) + len(baru)} masuk={len(baru)} skip={skip or 'nihil'}"
