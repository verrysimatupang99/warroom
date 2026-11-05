"""Tes ingest ledger IDX (SQLite) → model Trade, 5 Nov 2026.

Ledger IDX mencatat sinyal, bukan eksekusi. Kontrak yang dikunci di sini:
hanya baris yang benar-benar tertutup yang boleh menjadi `Trade`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from warroom_core.trades_idx import baca_tertutup, ke_trade, ringkas_sumber

SKEMA = """
CREATE TABLE signals(
 event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, producer TEXT NOT NULL, created_at TEXT NOT NULL,
 ticker TEXT NOT NULL, setup TEXT NOT NULL, source TEXT NOT NULL, direction TEXT NOT NULL,
 entry_low REAL NOT NULL, entry_high REAL NOT NULL, sl REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL,
 status TEXT NOT NULL DEFAULT 'CREATED', filled_at TEXT, closed_at TEXT, result TEXT, net_r REAL,
 costs_r REAL DEFAULT 0, data_source TEXT NOT NULL, source_timestamp TEXT, freshness_s REAL,
 duplicate_of TEXT, note TEXT, graded_at TEXT, grader_version TEXT,
 UNIQUE(job_id,created_at,ticker,setup))
"""

TERBUKA = {
    "event_id": "e-buka",
    "job_id": "j1",
    "producer": "ara_hunter_ledger.py",
    "created_at": "2026-11-04T09:00:00+07:00",
    "ticker": "BBCA.JK",
    "setup": "ARA_HUNTER",
    "source": "idx",
    "direction": "LONG",
    "entry_low": 9000.0,
    "entry_high": 9010.0,
    "sl": 8800.0,
    "tp1": 9200.0,
    "status": "CREATED",
    "data_source": "tradingview_scanner",
}

TERTUTUP = {
    **TERBUKA,
    "event_id": "e-tutup",
    "ticker": "TLKM.JK",
    "status": "CLOSED",
    "filled_at": "2026-11-04T09:05:00+07:00",
    "closed_at": "2026-11-04T14:30:00+07:00",
    "result": "TP1",
    "net_r": 1.8,
}


def _db(tmp_path: Path, baris: list[dict]) -> Path:
    p = tmp_path / "idx_ledger.db"
    con = sqlite3.connect(p)
    con.execute(SKEMA)
    for r in baris:
        kolom = ", ".join(r)
        tanya = ", ".join("?" for _ in r)
        con.execute(f"insert into signals ({kolom}) values ({tanya})", list(r.values()))
    con.commit()
    con.close()
    return p


def test_hanya_baris_tertutup_yang_dibaca(tmp_path: Path):
    p = _db(tmp_path, [TERBUKA, TERTUTUP])
    rows = baca_tertutup(p)
    assert [r["event_id"] for r in rows] == ["e-tutup"]


def test_ringkas_sumber_membedakan_terbuka_dan_tertutup(tmp_path: Path):
    p = _db(tmp_path, [TERBUKA, TERTUTUP])
    assert ringkas_sumber(p) == {"ada": 2, "terbuka": 1, "tertutup": 1, "berkas": 1}


def test_berkas_hilang_bukan_galat(tmp_path: Path):
    assert baca_tertutup(tmp_path / "tidak-ada.db") == []
    assert ringkas_sumber(tmp_path / "tidak-ada.db")["berkas"] == 0


def test_trade_dari_baris_tertutup(tmp_path: Path):
    t = ke_trade(baca_tertutup(_db(tmp_path, [TERTUTUP]))[0])
    assert t is not None
    assert t.venue == "idx" and t.mode == "paper"
    assert t.ext_id == "e-tutup"
    assert t.side == "BUY"
    assert t.pnl_r == 1.8
    # Tidak ada ukuran posisi/harga eksekusi di ledger → tidak dikarang
    assert t.qty is None and t.price is None and t.pnl_usd is None
    assert t.strategy_id is None
    assert t.closed_at is not None


def test_arah_tidak_dikenal_dilewati():
    assert ke_trade({**TERTUTUP, "direction": "HEDGE"}) is None


def test_tanpa_closed_at_dilewati():
    assert ke_trade({**TERTUTUP, "closed_at": ""}) is None
