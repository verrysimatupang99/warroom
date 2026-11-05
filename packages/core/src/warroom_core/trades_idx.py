"""Baris tertutup dari ledger IDX (`idx616_signal_ledger.db`, SQLite) → `trades`.

Ledger IDX mencatat SINYAL, bukan eksekusi: sebagian besar baris berstatus
`CREATED` dan belum pernah ditutup. Mengingest baris terbuka sebagai "trade"
akan mengarang posisi yang tidak pernah ada — jadi modul ini hanya menerima
baris yang benar-benar punya `closed_at` dan `result`.

Konsekuensi yang disengaja: `trades` IDX boleh kosong untuk waktu lama. Itu
bukan kegagalan ingest, dan pemanggil harus bisa membedakannya lewat
`ringkas_sumber()`.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from warroom_core.db import Trade

VENUE = "idx"
MODE = "paper"
LEDGER_DEFAULT = Path("/home/admin/live-trading/state/idx616_signal_ledger.db")


def _koneksi(jalur: Path) -> sqlite3.Connection | None:
    """Koneksi baca-saja. None bila berkas tidak ada / bukan SQLite."""
    if not jalur.is_file():
        return None
    try:
        return sqlite3.connect(f"file:{jalur}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def ringkas_sumber(jalur: Path = LEDGER_DEFAULT) -> dict[str, int]:
    """Jumlah baris per keadaan — untuk membedakan \"belum ada\" dari \"nol tertutup\"."""
    con = _koneksi(jalur)
    if con is None:
        return {"ada": 0, "terbuka": 0, "tertutup": 0, "berkas": 0}
    try:
        total = con.execute("select count(*) from signals").fetchone()[0]
        tutup = con.execute("select count(*) from signals where closed_at is not null").fetchone()[0]
    except sqlite3.Error:
        return {"ada": 0, "terbuka": 0, "tertutup": 0, "berkas": 0}
    finally:
        con.close()
    return {"ada": total, "terbuka": total - tutup, "tertutup": tutup, "berkas": 1}


def baca_tertutup(jalur: Path = LEDGER_DEFAULT) -> list[dict[str, Any]]:
    """Baris dengan `closed_at` terisi. Baris terbuka tidak pernah dimasukkan."""
    con = _koneksi(jalur)
    if con is None:
        return []
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select * from signals where closed_at is not null and closed_at <> '' order by closed_at"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [dict(r) for r in rows]


def _waktu(teks: Any) -> datetime | None:
    if not teks:
        return None
    try:
        t = datetime.fromisoformat(str(teks).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _angka(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ke_trade(baris: dict[str, Any]) -> Trade | None:
    """Satu sinyal tertutup → Trade. None bila kuncinya tidak bisa dipertanggungjawabkan."""
    eid = str(baris.get("event_id") or "").strip()
    if not eid:
        return None
    arah = str(baris.get("direction") or "").strip().upper()
    side = "BUY" if arah.startswith("LONG") else "SELL" if arah.startswith("SHORT") else None
    if side is None:
        return None
    closed_at = _waktu(baris.get("closed_at"))
    if closed_at is None:
        # Tanpa waktu tutup, baris ini tidak bisa diletakkan di garis waktu jurnal.
        return None

    net_r = _angka(baris.get("net_r"))
    evidence = {
        "ticker": str(baris.get("ticker") or ""),
        "setup": str(baris.get("setup") or ""),
        "status": str(baris.get("status") or ""),
        "result": str(baris.get("result") or ""),
        "entry_low": _angka(baris.get("entry_low")),
        "entry_high": _angka(baris.get("entry_high")),
        "sl": _angka(baris.get("sl")),
        "tp1": _angka(baris.get("tp1")),
        "costs_r": _angka(baris.get("costs_r")),
        "note": str(baris.get("note") or ""),
        "producer": str(baris.get("producer") or ""),
        "data_source": str(baris.get("data_source") or ""),
        "filled_at": str(baris.get("filled_at") or ""),
    }
    return Trade(
        venue=VENUE,
        mode=MODE,
        ext_id=eid,
        strategy_id=None,  # `setup` adalah nama, bukan id baris strategies
        side=side,
        qty=None,  # ledger tidak mencatat ukuran posisi
        price=None,  # ledger tidak mencatat harga eksekusi
        pnl_usd=None,  # hanya R yang ada; USD butuh ukuran posisi
        pnl_r=net_r,
        opened_at=_waktu(baris.get("filled_at")) or _waktu(baris.get("created_at")),
        closed_at=closed_at,
        evidence_json=evidence,
    )
