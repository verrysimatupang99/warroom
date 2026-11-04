"""Tes ingest ledger paper crypto → model Trade (pilihan A, 4 Nov 2026)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from warroom_core.trades_crypto import baca_ledger, ke_trade

UTC = timezone.utc


def _baris(**tambahan):
    dasar = {
        "signal_id": "#SIGTES01",
        "pair": "SOLUSDT",
        "direction": "SHORT",
        "closed_at": "2026-11-04T21:49:55+07:00",
        "status": "closed_SL",
        "r": -1.0,
        "cost_bps": 20.0,
        "fee_usd": 0.0574,
        "note": "closed_SL @ 95.45580386",
        "source": "paper-crypto",
        "strategi": "legacy-smc",
    }
    dasar.update(tambahan)
    return dasar


def _opened(**tambahan):
    dasar = {
        "signal_id": "#SIGTES01",
        "pair": "SOLUSDT",
        "direction": "SHORT",
        "entry": 92.42,
        "stop": 95.45580386,
        "stop_init": 95.45580386,
        "size_usd": 28.7,
        "cost_bps": 20.0,
        "opened_at": "2026-11-04T20:00:00+07:00",
        "source": "paper-crypto",
    }
    dasar.update(tambahan)
    return dasar


def test_ke_trade_pnl_usd_dari_data_nyata():
    t = ke_trade(_baris(), _opened())
    assert t is not None
    assert t.venue == "crypto" and t.mode == "paper"
    assert t.ext_id == "#SIGTES01"
    assert t.side == "SELL"
    # SHORT: entry 92.42, exit 95.45580386 → rugi; risk = stop_init-entry = 3.0358
    assert t.pnl_usd is not None and t.pnl_usd < 0
    assert float(t.pnl_r) == -1.0
    # strategy_id tidak pernah difabrikasi
    assert t.strategy_id is None
    ev = t.evidence_json
    assert ev["strategi"] == "legacy-smc"
    assert ev["entry"] == 92.42


def test_ke_trade_bahan_hilang_pnl_none_bukan_nol():
    t = ke_trade(_baris(), {})  # tanpa event opened
    assert t is not None
    assert t.pnl_usd is None  # jujur: tidak tahu, bukan 0
    assert float(t.pnl_r) == -1.0  # R tetap dari ledger


def test_ke_trade_label_wib_salah_diperbaiki_dari_created_at():
    # closed_at berlabel UTC padahal WIB (7 jam di depan created_at event)
    anchor = datetime(2026, 10, 15, 8, 7, 43, tzinfo=UTC)
    t = ke_trade(_baris(closed_at="2026-10-15T15:07:45+00:00"), _opened(), anchor)
    assert t is not None
    assert t.closed_at is not None
    assert t.closed_at.utcoffset() == timedelta(hours=7)
    # jam tidak bergeser
    assert (t.closed_at.hour, t.closed_at.minute) == (15, 7)


def test_ke_trade_rekonsiliasi_utc_asli_tidak_disentuh():
    anchor = datetime(2026, 11, 1, 4, 0, 5, tzinfo=UTC)
    t = ke_trade(_baris(closed_at="2026-11-01T04:00:00+00:00", source="rekonsiliasi"), {}, anchor)
    assert t is not None
    assert t.closed_at is not None
    assert t.closed_at.utcoffset() == timedelta(0)


def test_ke_trade_tanpa_signal_id_ditolak():
    assert ke_trade(_baris(signal_id=""), {}) is None


def test_baca_ledger_baris_rusak_dilewati(tmp_path: Path):
    p = tmp_path / "ledger.jsonl"
    p.write_text(
        json.dumps(_baris()) + "\n" + "{ini bukan json}\n" + "\n",
        encoding="utf-8",
    )
    rows = baca_ledger(p)
    assert len(rows) == 1
