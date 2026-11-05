"""Tes ingest `deals.csv` (forex) → model Trade, 5 Nov 2026."""

from __future__ import annotations

from pathlib import Path

from warroom_core.trades_forex import baca_deals, jalur_hilang, ke_trade

DEAL = {
    "ticket": "416510164-77",
    "symbol": "XAUUSDm",
    "side": "BUY",
    "volume": "0.10",
    "open_price": "3980.55",
    "close_price": "3991.20",
    "net": "10.65",
    "iso": "2026-11-05T08:30:00+00:00",
    "open_time": "2026-11-05T07:10:00+00:00",
    "account": "416510164",
    "strategy_version": "v3-break-retest",
}


def _csv(tmp_path: Path, baris: list[dict[str, str]]) -> Path:
    p = tmp_path / "deals.csv"
    kolom = list(baris[0])
    isi = ",".join(kolom) + "\n"
    for r in baris:
        isi += ",".join(str(r.get(k, "")) for k in kolom) + "\n"
    p.write_text(isi, encoding="utf-8")
    return p


def test_deal_lengkap_jadi_trade():
    t = ke_trade(DEAL)
    assert t is not None
    assert t.venue == "forex"
    assert t.ext_id == "416510164-77"
    assert t.side == "BUY"
    assert t.qty == 0.10
    assert t.price == 3991.20
    assert t.pnl_usd == 10.65
    assert t.opened_at is not None and t.closed_at is not None
    # strategy_id tidak difabrikasi; versi strategi disimpan di evidence
    assert t.strategy_id is None
    assert t.evidence_json["strategy_version"] == "v3-break-retest"


def test_tanpa_ticket_dilewati():
    tanpa = dict(DEAL)
    tanpa["ticket"] = ""
    assert ke_trade(tanpa) is None


def test_arah_tidak_dikenal_dilewati_bukan_ditebak():
    aneh = dict(DEAL)
    aneh["side"] = "HEDGE"
    assert ke_trade(aneh) is None


def test_pnl_tidak_ada_tetap_none_bukan_nol():
    tanpa = dict(DEAL)
    tanpa["net"] = ""
    t = ke_trade(tanpa)
    assert t is not None
    assert t.pnl_usd is None


def test_berkas_hilang_dibedakan_dari_nol_trade(tmp_path: Path):
    jalur = tmp_path / "tidak-ada.csv"
    assert jalur_hilang(jalur) is True
    assert baca_deals(jalur, tmp_path / "koreksi.csv") == []


def test_koreksi_diterapkan_dan_jejaknya_disimpan(tmp_path: Path):
    jalur = _csv(tmp_path, [DEAL])
    koreksi = tmp_path / "koreksi.csv"
    koreksi.write_text(
        "ts,ticket,field,old,new,reason,source\n"
        "2026-11-05T09:00:00Z,416510164-77,net,10.65,9.40,salah baca fee,audit\n",
        encoding="utf-8",
    )
    baris = baca_deals(jalur, koreksi)
    assert len(baris) == 1
    t = ke_trade(baris[0])
    assert t is not None
    assert t.pnl_usd == 9.40
    assert t.evidence_json["koreksi"][0]["field"] == "net"
