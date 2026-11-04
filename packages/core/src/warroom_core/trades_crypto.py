"""Baris ledger paper crypto → record untuk tabel `trades`.

Ledger `crypto_equity.jsonl` adalah kebenaran (ditulis `paper-scan`/eksekutor).
Event `trade.opened` memperkaya: `entry`, `stop_init`, `size_usd`, `strategi`.
`pnl_usd` dihitung dari data nyata — kalau salah satu bahan hilang, hasilnya
None, bukan nol yang pura-pura gratis.

Zona waktu: 3 baris lama berlabel `+00:00` padahal WIB (terbukti dari
`created_at` event, temuan 4 Nov 2026). Penanda: waktu berlabel UTC yang
terletak SETELAH `created_at` event penutupnya tidak mungkin benar — dibaca
ulang sebagai WIB (geser offset, bukan geser jam).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from warroom_core.db import Trade

WIB = timezone(timedelta(hours=7))
VENUE = "crypto"
MODE = "paper"

_HARGA_DI_NOTE = re.compile(r"@\s*([0-9]+(?:\.[0-9]+)?)")
_SUMBER_WIB_SALAH = {"paper-crypto", "paper", "paper-idx", "paper-forex", "paper-gmgn"}


def baca_ledger(jalur: Path) -> list[dict[str, Any]]:
    """Baris JSONL valid; baris rusak dilewati tapi tidak diam-diam dihitung hilang."""
    if not jalur.is_file():
        return []
    hasil: list[dict[str, Any]] = []
    for ln in jalur.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            hasil.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return hasil


def _waktu_jujur(teks: str, anchor: datetime | None) -> datetime | None:
    """Parse waktu; label `+00:00` dari penulis lama diperbaiki jadi WIB.

    Waktu berlabel UTC yang berada >1 jam SETELAH `created_at` event (yang
    benar-benar UTC) mustahil — jamnya WIB yang salah label.
    """
    if not teks:
        return None
    try:
        t = datetime.fromisoformat(teks)
    except ValueError:
        return None
    if (
        anchor is not None
        and teks.endswith("+00:00")
        and t > anchor + timedelta(hours=1)
    ):
        return t.replace(tzinfo=WIB)
    return t


def ke_trade(
    baris: dict[str, Any],
    opened: dict[str, Any] | None = None,
    closed_created_at: datetime | None = None,
) -> Trade | None:
    """Satu baris ledger (+ event pengaya) → model Trade. None bila tak layak."""
    sid = str(baris.get("signal_id") or "").strip()
    if not sid:
        return None
    opened = opened or {}
    closed_at = _waktu_jujur(str(baris.get("closed_at") or ""), closed_created_at)
    opened_at = _waktu_jujur(str(opened.get("opened_at") or ""), None)
    # WIB-salah-label juga bisa menular ke opened_at event: anchor closed tak tersedia
    # di sini, jadi hanya label yang SAMA bohongnya dengan ledger yang dibetulkan.
    if (
        opened_at is not None
        and closed_at is not None
        and str(opened.get("opened_at") or "").endswith("+00:00")
        and opened_at > closed_at
    ):
        opened_at = opened_at.replace(tzinfo=WIB)

    direction = str(baris.get("direction") or "").upper()
    entry = _angka(opened.get("entry"))
    stop_init = _angka(opened.get("stop_init"))
    size_usd = _angka(opened.get("size_usd"))
    cocok = _HARGA_DI_NOTE.search(str(baris.get("note") or ""))
    exit_price = _angka(cocok.group(1)) if cocok else None
    r = _angka(baris.get("r"))

    pnl_usd: float | None = None
    bahan_lengkap = not any(v is None for v in (entry, stop_init, size_usd, exit_price))
    if bahan_lengkap and direction in ("LONG", "SHORT"):
        assert entry is not None and stop_init is not None
        assert size_usd is not None and exit_price is not None
        risk = (entry - stop_init) if direction == "LONG" else (stop_init - entry)
        if risk > 0:
            move = (exit_price - entry) if direction == "LONG" else (entry - exit_price)
            qty = size_usd / entry
            pnl_usd = round(move * qty, 6)

    evidence = {
        "signal_id": sid,
        "source": str(baris.get("source") or "paper-crypto"),
        "strategi": str(baris.get("strategi") or opened.get("strategi") or ""),
        "status": str(baris.get("status") or ""),
        "note": str(baris.get("note") or ""),
        "size_usd": size_usd,
        "entry": entry,
        "stop_init": stop_init,
        "exit_price": exit_price,
        "cost_bps": _angka(baris.get("cost_bps") or opened.get("cost_bps")),
        "fee_usd": _angka(baris.get("fee_usd")),
    }
    return Trade(
        venue=VENUE,
        mode=MODE,
        ext_id=sid,
        strategy_id=None,  # tidak ada baris strategies crypto nyata — jangan fabrikasi
        side="SELL" if direction == "SHORT" else "BUY",
        qty=None,
        price=exit_price,
        pnl_usd=pnl_usd,
        pnl_r=r,
        opened_at=opened_at,
        closed_at=closed_at,
        evidence_json=evidence,
    )


def _angka(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
