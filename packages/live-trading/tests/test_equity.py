"""Equity — kurva kumulatif R dan statistik harus aritmetika yang benar.

Ledger adalah sumber kebenaran profitabilitas. Kalau penjumlahan,
drawdown, atau idempotensi di sini salah, semua angka di dashboard ikut
salah — jadi modul kecil ini diuji paling ketat.
"""

from __future__ import annotations

import json

from live_trading import equity
from live_trading.config import get_settings


def _isi(s, baris):
    s.state_dir.mkdir(parents=True, exist_ok=True)
    with s.ledger_path.open("w", encoding="utf-8") as fh:
        for b in baris:
            fh.write(b + "\n")


def test_kosong(tmp_path):
    s = get_settings(home=tmp_path)
    c = equity.curve(s)
    assert c["stats"]["trades"] == 0
    assert c["stats"]["total_r"] == 0
    assert c["stats"]["winrate_pct"] is None
    assert c["points"] == [{"i": 0, "r": 0.0, "cum": 0.0, "label": "start"}]


def _baris(*rows):
    return [json.dumps(r) for r in rows]


def test_kumulatif_dd_pf(tmp_path):
    s = get_settings(home=tmp_path)
    _isi(
        s,
        _baris(
            {"signal_id": "#A", "pair": "BTCUSDT", "closed_at": "2026-09-01T10:00:00",
             "status": "closed_TP1", "r": 1.0},
            {"signal_id": "#B", "pair": "ETHUSDT", "closed_at": "2026-09-02T10:00:00",
             "status": "closed_SL", "r": -1.0},
            {"signal_id": "#C", "pair": "SOLUSDT", "closed_at": "2026-09-03T10:00:00",
             "status": "closed_TP2", "r": 2.0},
        ),
    )
    c = equity.curve(s)
    st = c["stats"]
    assert st["trades"] == 3
    assert st["total_r"] == 2.0
    assert st["wins"] == 2 and st["losses"] == 1
    assert st["winrate_pct"] == round(100 * 2 / 3, 1)
    assert st["max_drawdown_r"] == 1.0  # puncak +1 lalu turun ke 0
    assert st["profit_factor"] == 3.0  # (1+2)/1
    assert [p["cum"] for p in c["points"]] == [0.0, 1.0, 0.0, 2.0]


def test_baris_rusak_dilewati(tmp_path):
    s = get_settings(home=tmp_path)
    _isi(s, ['bukan json', '{"tanpa_signal_id": 1}', '{"signal_id": "#D", "r": 0.5}'])
    c = equity.curve(s)
    assert c["stats"]["trades"] == 1
    assert c["stats"]["total_r"] == 0.5


def test_add_trade_idempoten(tmp_path):
    s = get_settings(home=tmp_path)
    assert equity.add_trade(s, signal_id="#E", pair="BTCUSDT", status="closed_TP1", r=1.0) is True
    assert equity.add_trade(s, signal_id="#E", pair="BTCUSDT", status="closed_TP1", r=1.0) is False
    assert equity.curve(s)["stats"]["trades"] == 1
