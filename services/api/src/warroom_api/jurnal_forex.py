"""Jurnal trade forex — dibaca dari tabel `trades` (venue `forex`, mode `live`).

Dipisah dari `lokal.py` dengan alasan yang sama seperti `jurnal_crypto`: satu
pemilik data, satu bentuk baris. Sumber kebenarannya tetap `deals.csv` (ADR-009),
tetapi DB adalah tempat jurnal membaca supaya halaman tidak bergantung pada
berkas di host setiap kali dibuka.

Bila tabel belum terisi (`trades-forex-sync` belum jalan atau EA belum pernah
melapor), `dari_db` mengembalikan daftar kosong dan pemanggil jatuh ke
pembacaan `deals.csv` langsung — bukan menampilkan "0 trade" seolah EA sehat.
"""

from __future__ import annotations

import json
from typing import Any


def dari_db(batas: int = 200) -> list[dict[str, Any]]:
    """Baris jurnal forex dari tabel `trades`, bentuk sama dengan `_trade_forex`."""
    try:
        from sqlalchemy import text
        from warroom_core.db import session_scope
    except Exception:  # noqa: BLE001 — jurnal tidak boleh menjatuhkan halaman
        return []

    hasil: list[dict[str, Any]] = []
    try:
        with session_scope() as s:
            rows = s.execute(
                text(
                    "select ext_id, side, qty, price, pnl_usd, opened_at, closed_at, "
                    "evidence_json from trades where venue='forex' and mode='live' "
                    "order by closed_at desc nulls last limit :n"
                ),
                {"n": batas},
            ).fetchall()
    except Exception:  # noqa: BLE001 — DB belum siap/belum migrasi
        return []

    for r in rows:
        ev = r.evidence_json if isinstance(r.evidence_json, dict) else {}
        if not ev:
            try:
                ev = json.loads(r.evidence_json or "{}")
            except (TypeError, ValueError):
                ev = {}
        hasil.append(
            {
                "iso": str(r.closed_at or "")[:19].replace("T", " "),
                "symbol": str(ev.get("symbol") or ""),
                "side": r.side or "",
                "volume": "" if r.qty is None else str(r.qty),
                "price_filled": "" if r.price is None else str(r.price),
                "open_price": "" if ev.get("open_price") is None else str(ev.get("open_price")),
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_usd": "" if r.pnl_usd is None else str(r.pnl_usd),
                "pnl_pct": "",
                "ticket": str(r.ext_id or ""),
                "account": str(ev.get("account") or "unknown"),
                "strategy_version": str(ev.get("strategy_version") or "unknown"),
                "market": "forex",
            }
        )
    return hasil
