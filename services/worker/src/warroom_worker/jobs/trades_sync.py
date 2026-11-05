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
            "select type, created_at, payload_json from events where type in ('trade.opened','trade.closed')"
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


def handler_trades_forex_sync(s: SASession, job: Job) -> str:
    """Job `trades-forex-sync`: deals.csv (deal tertutup EA) → tabel `trades`.

    Beda dari jalur crypto: tidak ada ledger alternatif. Bila berkas belum ada,
    hasilnya dilaporkan sebagai `sumber=belum-ada` — bukan `masuk=0` yang terbaca
    seperti "EA jalan tapi tidak ada trade".
    """
    from warroom_core.trades_forex import DEALS_DEFAULT, baca_deals, jalur_hilang, ke_trade

    if jalur_hilang(DEALS_DEFAULT):
        return "sumber=belum-ada (deals.csv tidak ada — EA belum melapor)"

    rows = baca_deals()
    trades = [t for t in (ke_trade(r) for r in rows) if t is not None]
    skip = len(rows) - len(trades)

    kunci_ada = {ext for (ext,) in s.query(Trade.ext_id).filter(Trade.venue == "forex", Trade.mode == "live")}
    baru = [t for t in trades if t.ext_id not in kunci_ada]
    if baru:
        s.add_all(baru)
        s.add(
            Event(
                type="trade.ingest",
                actor="trades-forex-sync",
                payload_json={"masuk": len(baru), "total_db": len(kunci_ada) + len(baru)},
            )
        )
    return f"deals={len(rows)} db={len(kunci_ada) + len(baru)} masuk={len(baru)} skip={skip or 'nihil'}"


def handler_trades_idx_sync(s: SASession, job: Job) -> str:
    """Job `trades-idx-sync`: sinyal IDX TERTUTUP → tabel `trades`.

    Ledger IDX mencatat sinyal, bukan eksekusi. Hanya baris dengan `closed_at`
    yang masuk; sisanya dilaporkan sebagai hitungan, bukan dianggap trade.
    """
    from warroom_core.trades_idx import LEDGER_DEFAULT, baca_tertutup, ke_trade, ringkas_sumber

    r = ringkas_sumber(LEDGER_DEFAULT)
    if r["berkas"] == 0:
        return "sumber=belum-ada (idx616_signal_ledger.db tidak ada)"
    if r["tertutup"] == 0:
        return f"sumber=ada terbuka={r['terbuka']} tertutup=0 (belum ada trade tertutup)"

    trades = [t for t in (ke_trade(x) for x in baca_tertutup()) if t is not None]
    skip = r["tertutup"] - len(trades)

    kunci_ada = {ext for (ext,) in s.query(Trade.ext_id).filter(Trade.venue == "idx", Trade.mode == "paper")}
    baru = [t for t in trades if t.ext_id not in kunci_ada]
    if baru:
        s.add_all(baru)
        s.add(
            Event(
                type="trade.ingest",
                actor="trades-idx-sync",
                payload_json={"masuk": len(baru), "total_db": len(kunci_ada) + len(baru)},
            )
        )
    return (
        f"tertutup={r['tertutup']} db={len(kunci_ada) + len(baru)} masuk={len(baru)} skip={skip or 'nihil'}"
    )
