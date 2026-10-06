"""Uji mark LP — rumus IL, fee taksiran berlabel, skor pool, pakem berbasis hari."""

from __future__ import annotations

import json
import math
from pathlib import Path

from live_trading import lp_mark as M


def test_il_5050_nilai_kenal():
    assert M.il_5050(1.0) == 0.0
    # Harga x4 → IL terkenal ≈ -20%
    assert abs(M.il_5050(4.0) - (-0.2)) < 1e-9
    # Harga x1/4 → IL sama (simetris)
    assert abs(M.il_5050(0.25) - (-0.2)) < 1e-9
    assert M.il_5050(0) == -1.0


def test_fee_terkumpul_proporsional():
    f1 = M.fee_terkumpul(notional_usd=100, vl=3.0, fee_tier=0.01, hari=1)
    f2 = M.fee_terkumpul(notional_usd=100, vl=3.0, fee_tier=0.01, hari=2)
    assert abs(f2 - 2 * f1) < 1e-9
    assert abs(f1 - 3.0) < 1e-9
    # input tidak masuk akal → 0, bukan angka karangan
    assert M.fee_terkumpul(notional_usd=0, vl=3, fee_tier=0.01, hari=1) == 0.0
    assert M.fee_terkumpul(notional_usd=100, vl=0, fee_tier=0.01, hari=1) == 0.0


def test_mark_posisi_menghitung_pnl_dan_hold():
    kini = 1_000_000_000.0
    pos = {
        "symbol": "UBI",
        "address": "0xabc",
        "entry_price": 1.0,
        "entry_ts": kini - 2 * 86400,  # 2 hari
        "notional_usd": 30.0,
        "vl_at_entry": 4.83,
    }
    m = M.mark_posisi(pos, harga_sekarang=1.21, vl_sekarang=3.0, fee_tier=0.01, kini=kini)
    assert m["status"] == "dinilai"
    assert abs(m["umur_hari"] - 2.0) < 1e-9
    # fee = 30 * 3.0 * 0.01 * 2 = 1.8
    assert abs(m["fee_usd"] - 1.8) < 1e-6
    # IL pada rasio 1.21 = 2*sqrt(1.21)/2.21 - 1
    il = 2 * math.sqrt(1.21) / (1 + 1.21) - 1
    assert abs(m["il_pct"] - il * 100) < 1e-3
    assert abs(m["hold_usd"] - 30 * il) < 1e-6
    assert abs(m["lp_vs_hold_usd"] - m["fee_usd"]) < 1e-6, "vs hold murni = fee"
    assert m["fee_apakah_taksiran"] is True


def test_mark_tanpa_harga_jujur():
    m = M.mark_posisi({"symbol": "X", "entry_price": 0}, harga_sekarang=1.0, vl_sekarang=3.0, fee_tier=0.01)
    assert m["status"] == "tidak-ada-harga"
    assert "jangan dikarang" in m["alasan"]


def test_skor_pool_gate_sama_dengan_lp_paper():
    bagus = {"fee_ratio": 4.0, "liq": 200_000, "holders": 5000, "price_5m": 1.0,
             "rug": 0.05, "bundler": 0.05, "insider": 0.02, "top10": 0.10}
    s = M.skor_pool(bagus)
    assert s["lolos"] is True and s["skor"] > 50
    jelek = dict(bagus, fee_ratio=0.5, liq=10_000, holders=100, price_5m=-20.0)
    s2 = M.skor_pool(jelek)
    assert s2["lolos"] is False
    assert any("V/L" in g for g in s2["gagal"])
    assert any("liq" in g for g in s2["gagal"])
    assert any("holders" in g for g in s2["gagal"])
    assert any("5m" in g for g in s2["gagal"])


def test_catat_mark_append(tmp_path: Path):
    p = tmp_path / "lp_ledger.jsonl"
    M.catat_mark(p, {"symbol": "A", "ts": 1.0, "status": "dinilai", "pnl_pct": 1.0})
    M.catat_mark(p, {"symbol": "A", "ts": 2.0, "status": "dinilai", "pnl_pct": 2.0})
    baris = [json.loads(ln) for ln in p.read_text().splitlines()]
    assert len(baris) == 2 and baris[0]["pnl_pct"] == 1.0


def test_nilai_pakem_lp_menghitung_hari():
    """n = hari unik: 3 mark di hari yang sama tetap terhitung 1 hari."""
    hari0 = 1_790_000_000.0  # detik apa pun
    baris = []
    for i, offset in enumerate([0, 3600, 7200]):  # 3 mark, hari sama
        baris.append({"symbol": "A", "ts": hari0 + offset, "status": "dinilai", "pnl_pct": 1.0 + i})
    for d in range(1, 15):  # 14 hari berikutnya
        baris.append({"symbol": "A", "ts": hari0 + d * 86400, "status": "dinilai", "pnl_pct": 0.5})
    for d in range(15, 40):  # total 40 hari
        baris.append({"symbol": "A", "ts": hari0 + d * 86400, "status": "dinilai", "pnl_pct": -0.2})
    hasil = M.nilai_pakem_lp(baris)
    # 40 hari unik → PRELIMINARY (30–99), meskipun barisnya 43
    assert hasil.n_hari == 40
    assert hasil.tingkat == "PRELIMINARY"
