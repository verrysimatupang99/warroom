#!/usr/bin/env python3
"""Backfill tabel `trades` dari ledger paper crypto (pilihan A, 4 Nov 2026).

Sumber kebenaran: `crypto_equity.jsonl` (ditulis eksekutor paper). Event
`trade.opened` memperkaya (entry, stop_init, size_usd); `trade.closed`
created_at memperbaiki label zona waktu baris lama yang salah label.

Idempoten: kunci unik (venue, mode, ext_id) = ('crypto','paper',signal_id).
Baris yang sudah ada TIDAK ditulis ulang (bukan upsert buta) — kalau ada
selisih, itu temuan, bukan sesuatu yang didiam-diamkan.

Pakai:
    python ops/backfill-trades-crypto.py --dry-run   # tampilkan rencana
    python ops/backfill-trades-crypto.py             # jalankan
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.db import Trade, dispose_engine, session_scope  # noqa: E402
from warroom_core.trades_crypto import baca_ledger, ke_trade  # noqa: E402


def _events() -> tuple[dict[str, dict], dict[str, datetime]]:
    """Index trade.opened + created_at trade.closed langsung dari DB (baca-saja)."""
    from sqlalchemy import text

    opened: dict[str, dict] = {}
    closed: dict[str, datetime] = {}
    with session_scope() as s:
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
                if not isinstance(created, datetime):
                    created = datetime.fromisoformat(str(created))
                closed.setdefault(sid, created)
    return opened, closed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ledger", type=Path, default=None)
    args = ap.parse_args()

    ledger = args.ledger
    if ledger is None:
        from live_trading.config import get_settings

        ledger = get_settings().state_dir / "crypto_equity.jsonl"

    rows = baca_ledger(ledger)
    opened, closed = _events()
    trades = []
    skip: list[str] = []
    for r in rows:
        t = ke_trade(r, opened.get(str(r.get("signal_id"))), closed.get(str(r.get("signal_id"))))
        (trades.append(t) if t else skip.append(str(r.get("signal_id"))))

    baru: list = []
    sudah: list[str] = []
    with session_scope() as s:
        kunci_ada = {
            (v, m, e)
            for v, m, e in s.query(Trade.venue, Trade.mode, Trade.ext_id).filter(
                Trade.venue == "crypto", Trade.mode == "paper"
            )
        }
        for t in trades:
            (sudah if (t.venue, t.mode, t.ext_id) in kunci_ada else baru).append(t)

    print(f"ledger   : {len(rows)} baris ({ledger})")
    print(f"layak    : {len(trades)} | skip: {skip or 'nihil'}")
    print(f"sudah ada: {len(sudah)} | akan masuk: {len(baru)}")
    tot_r = sum(float(t.pnl_r) for t in trades if t.pnl_r is not None)
    print(f"total R  : {tot_r:+.2f}")

    if args.dry_run:
        print("(dry-run: tidak ada yang ditulis)")
        return 0
    if not baru:
        print("tidak ada baris baru — selesai.")
        return 0

    with session_scope() as s:
        s.add_all(baru)
    print(f"masuk: {len(baru)} baris.")
    dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
