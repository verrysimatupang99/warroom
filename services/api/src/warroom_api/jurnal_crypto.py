"""Jurnal trade paper crypto — dibaca dari ledger `crypto_equity.jsonl`.

Dipisah dari `lokal.py` (4 Nov 2026) karena berkas itu menembus batas 1000 baris,
dan karena ledger crypto punya pemilik data sendiri: `paper-scan` di worker yang
menulis lewat aturan gate yang sama dengan yang dipakai eksekutor.

Kenapa BUKAN `momentum_trades.csv`: berkas itu milik strategi momentum lama
(19 baris BUY, berhenti 3 Nov) dan tidak berbagi keadaan dengan paper trader.
Memakainya membuat jurnal crypto menampilkan sumber yang berbeda dari yang
sebenarnya berjalan — temuan 4 Nov 2026.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _jalur_env(nama: str, bawaan: str) -> Path:
    v = os.environ.get(nama)
    return Path(v) if v else Path(bawaan)


# Bisa dioverride (CI/e2e menunjuk berkas sintetis; produksi tetap /home/admin).
EQUITY_CRYPTO = _jalur_env(
    "WARROOM_EQUITY_CRYPTO", "/home/admin/live-trading/state/crypto_equity.jsonl"
)

_HARGA_DI_NOTE = re.compile(r"@\s*([0-9]+(?:\.[0-9]+)?)")


def r_dari(t: dict[str, Any]) -> float:
    """Nilai R sebuah baris trade; 0,0 kalau kosong/tidak terbaca (bukan ditebak)."""
    v = t.get("r")
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def dari_ledger(jalur: Path | None = None) -> list[dict[str, Any]]:
    """Trade tertutup dari ledger paper, dibentuk seperti baris jurnal lain.

    Hasil dilaporkan dalam **R** (kelipatan risiko), bukan persen: `pnl_pct`
    sengaja dikosongkan karena R tidak bisa diterjemahkan ke persen tanpa ukuran
    risiko per trade. Mengisinya dengan R akan menyesatkan pembaca.
    """
    p = jalur or EQUITY_CRYPTO
    if not p.is_file():
        return []
    hasil: list[dict[str, Any]] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        arah = str(r.get("direction") or "").upper()
        # Harga keluar tertulis di `note` ("closed_SL @ 0.26714994"); diambil apa
        # adanya kalau polanya cocok, dikosongkan kalau tidak — jangan ditebak.
        m = _HARGA_DI_NOTE.search(str(r.get("note") or ""))
        hasil.append(
            {
                "iso": str(r.get("closed_at", ""))[:19].replace("T", " "),
                "symbol": r.get("pair", ""),
                "side": "SELL" if arah == "SHORT" else "BUY",
                "direction": arah,
                "volume": "",
                "price_filled": m.group(1) if m else "",
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_pct": "",
                "r": r.get("r"),
                "status": r.get("status", ""),
                "strategi": r.get("strategi", ""),
                "fee_usd": r.get("fee_usd", ""),
                "keterangan": r.get("note", ""),
                "market": "crypto",
                "sumber": r.get("source", "paper-crypto"),
            }
        )
    return hasil


def dari_db(batas: int = 200) -> list[dict[str, Any]]:
    """Trade crypto dari tabel `trades` (diisi `trades-crypto-sync`).

    Bentuk baris sama dengan `dari_ledger` supaya pemaakai tidak tahu bedanya —
    kalau DB kosong/belum terisi, pemanggil boleh jatuh ke ledger.
    """
    from sqlalchemy import text
    from warroom_core.db import session_scope

    hasil: list[dict[str, Any]] = []
    with session_scope() as s:
        rows = s.execute(
            text(
                "select ext_id, side, pnl_r, pnl_usd, price, opened_at, closed_at, "
                "evidence_json from trades where venue='crypto' and mode='paper' "
                "order by closed_at desc nulls last limit :n"
            ),
            {"n": batas},
        ).fetchall()
    for r in rows:
        ev = r.evidence_json if isinstance(r.evidence_json, dict) else json.loads(r.evidence_json or "{}")
        hasil.append(
            {
                "iso": str(r.closed_at or "")[:19].replace("T", " "),
                "symbol": str(ev.get("pair") or ""),
                "side": r.side or "",
                "direction": "SHORT" if (r.side or "").upper() == "SELL" else "LONG",
                "volume": "",
                "price_filled": str(ev.get("exit_price") or ""),
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_pct": "",
                "r": float(r.pnl_r) if r.pnl_r is not None else None,
                "status": str(ev.get("status") or ""),
                "strategi": str(ev.get("strategi") or ""),
                "fee_usd": ev.get("fee_usd"),
                "keterangan": str(ev.get("note") or ""),
                "market": "crypto",
                "sumber": str(ev.get("source") or "paper-crypto"),
            }
        )
    return hasil


def ringkas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Ringkasan menang/kalah/total R dari baris trade crypto."""
    return {
        "trade_paper": len(rows),
        "menang_paper": sum(1 for t in rows if r_dari(t) > 0),
        "kalah_paper": sum(1 for t in rows if r_dari(t) < 0),
        "r_total_paper": round(sum(r_dari(t) for t in rows), 2),
    }
