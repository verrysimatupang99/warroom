"""Regresi: rekonsiliasi ledger — saldo = modal + realized − fee.

Yang dikunci:
1. Fee yang tercatat per baris dipotong dari saldo gross → saldo_net.
2. Baris TANPA fee_usd tidak dianggap fee nol; itu membuat `lengkap=False` (rekonsiliasi
   belum penuh) dan dilaporkan apa adanya.
3. Identitas `saldo_net = modal + realized − fee` terpenuhi; realized dicross-check dari
   Σ R × risiko (flat) sehingga drift (mis. compounding) ketahuan.
4. `close_position` menulis `cost_bps` + `fee_usd` ke baris ledger (integrasi paper).
"""

from __future__ import annotations

import json
from pathlib import Path

from live_trading import dompet as dp
from live_trading.config import get_settings
from live_trading.execution.paper import PaperBroker

KURS = 17000.0


def _ledger(state: Path, baris: list[dict]) -> None:
    (state / "crypto_equity.jsonl").write_text(
        "\n".join(json.dumps(b) for b in baris) + "\n", encoding="utf-8"
    )


def test_rekonsiliasi_penuh_memotong_fee(tmp_path: Path) -> None:
    _ledger(tmp_path, [
        {"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01", "fee_usd": 0.5, "cost_bps": 20.0},
        {"signal_id": "b", "r": -0.5, "closed_at": "2026-10-02", "fee_usd": 0.3, "cost_bps": 20.0},
    ])
    out = dp.cek_rekonsiliasi_saldo(tmp_path, market="crypto", kurs=KURS)
    assert out["tersedia"] is True
    modal = 10_000_000 / KURS
    risiko = modal * 0.01
    realized = (1.0 - 0.5) * risiko
    assert abs(out["modal_usd"] - modal) < 0.01
    assert abs(out["realized_usd"] - realized) < 0.01
    assert out["fee_usd"] == 0.8
    # identitas: saldo_net = modal + realized − fee
    assert abs(out["saldo_net_usd"] - (modal + realized - 0.8)) < 0.01
    assert out["saldo_net_usd"] < out["saldo_gross_usd"]
    assert out["lengkap"] is True and out["konsisten"] is True
    assert out["baris_tanpa_fee"] == 0


def test_baris_tanpa_fee_dilaporkan_bukan_nol(tmp_path: Path) -> None:
    _ledger(tmp_path, [
        {"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01", "fee_usd": 0.5},
        {"signal_id": "b", "r": -0.5, "closed_at": "2026-10-02"},  # fee tidak tercatat
    ])
    out = dp.cek_rekonsiliasi_saldo(tmp_path, market="crypto", kurs=KURS)
    assert out["lengkap"] is False
    assert out["baris_tanpa_fee"] == 1
    assert out["baris_dengan_fee"] == 1
    # fee hanya dari baris yang mencatat — baris kosong tidak dianggap gratis
    assert out["fee_usd"] == 0.5
    assert any("belum mencatat fee_usd" in c for c in out["catatan"])


def test_ledger_tanpa_fee_sama_sekali(tmp_path: Path) -> None:
    _ledger(tmp_path, [
        {"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01"},
        {"signal_id": "b", "r": 2.0, "closed_at": "2026-10-02"},
    ])
    out = dp.cek_rekonsiliasi_saldo(tmp_path, market="crypto", kurs=KURS)
    assert out["fee_usd"] == 0.0
    assert out["lengkap"] is False
    # tanpa fee, saldo_net = saldo gross (fee tidak dikarang)
    assert out["saldo_net_usd"] == out["saldo_gross_usd"]


def test_close_position_menulis_fee_ke_ledger(tmp_path: Path) -> None:
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    b = PaperBroker(s)
    pos = b.open_position(
        pair="BTCUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0,
        size_usd=200.0, cost_bps=20.0,
    )
    rec = b.close_position(pos.signal_id, 110.0, "closed_TP2")
    baris = json.loads(s.ledger_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert baris["cost_bps"] == 20.0
    # fee = size 200 × 20 bps = 200 × 0.002 = 0.4
    assert baris["fee_usd"] == 0.4
    assert rec["fee_usd"] == 0.4


def test_close_tanpa_cost_bps_fee_none(tmp_path: Path) -> None:
    """cost_bps None → fee None (jujur), bukan 0 seolah gratis."""
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    b = PaperBroker(s)
    pos = b.open_position(
        pair="ETHUSDT", direction="LONG", entry=100.0, stop=95.0, tp1=105.0, tp2=110.0,
        size_usd=100.0,
    )
    b.close_position(pos.signal_id, 110.0, "closed_TP2")
    baris = json.loads(s.ledger_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert baris["cost_bps"] is None
    assert baris["fee_usd"] is None
