"""Uji runner mark LP — tanpa jaringan (harga dipalsukan)."""

from __future__ import annotations

import json
from pathlib import Path

from live_trading import lp_mark_run as R


def _state_lp(tmp_path: Path, **pos) -> Path:
    p = tmp_path / "lp_paper_state.json"
    p.write_text(
        json.dumps({"paper": True, "capital_usd": 30.0, "positions": [pos]}),
        encoding="utf-8",
    )
    return p


def test_hitung_menulis_ledger_dan_pakem(tmp_path: Path, monkeypatch) -> None:
    state = _state_lp(
        tmp_path,
        symbol="UBI",
        address="0xabc",
        entry_price=1.0,
        entry_ts=1_000_000.0,
        notional_usd=30.0,
        vl_at_entry=4.83,
    )
    monkeypatch.setattr(
        R, "_harga_pool", lambda alamat, rantai=None: {"harga_usd": 1.21, "vl": 3.0, "liq_usd": 80_000}
    )
    laporan = R.hitung_semua(state_path=state, state_dir=tmp_path, kini=1_000_000.0 + 2 * 86400)
    assert laporan["status"] == "ok"
    m = laporan["mark"][0]
    assert m["status"] == "dinilai" and m["symbol"] == "UBI"
    assert abs(m["fee_usd"] - 1.8) < 1e-6  # 30 × 3.0 × 0.01 × 2 hari
    assert laporan["total_pnl_usd"] == m["pnl_usd"]
    # ledger tertulis
    led = (tmp_path / "lp_ledger.jsonl").read_text().strip().splitlines()
    assert len(led) == 1 and json.loads(led[0])["symbol"] == "UBI"
    # pakem ikut dilaporkan (n=1 hari → INSUFFICIENT)
    assert laporan["pakem"]["tingkat"] == "INSUFFICIENT"
    # mark terakhir tersimpan untuk panel
    assert (tmp_path / "lp_mark_terakhir.json").is_file()


def test_pool_tak_terbaca_tidak_dikarang(tmp_path: Path, monkeypatch) -> None:
    state = _state_lp(tmp_path, symbol="X", address="0xdead", entry_price=1.0, entry_ts=1.0, notional_usd=10)
    monkeypatch.setattr(R, "_harga_pool", lambda alamat, rantai=None: None)
    laporan = R.hitung_semua(state_path=state, state_dir=tmp_path)
    assert laporan["mark"][0]["status"] == "pasar-tak-terbaca"
    assert not (tmp_path / "lp_ledger.jsonl").exists(), "gagal baca ≠ boleh menulis baris kosong"


def test_tanpa_posisi_jujur(tmp_path: Path) -> None:
    p = tmp_path / "kosong.json"
    p.write_text(json.dumps({"positions": []}), encoding="utf-8")
    laporan = R.hitung_semua(state_path=p, state_dir=tmp_path)
    assert laporan["status"] == "tidak-ada-posisi"
    assert "lp_paper" in laporan["alasan"]


def test_laporan_panel_belum_ada(tmp_path: Path) -> None:
    laporan = R.laporan_lp_mark(tmp_path)
    assert laporan["status"] == "belum-ada" and laporan["mark"] == []
