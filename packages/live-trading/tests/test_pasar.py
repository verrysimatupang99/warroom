"""Tes mesin per-market (``pasar.py``).

Prinsip yang ditegakkan di sini:
1. Semua angka berasal dari berkas; tidak ada yang dikarang (n=0 → tersedia False).
2. Market yang serinya BUKAN R (LP, Polymarket) tidak dipaksa punya mean_r.
3. NO FILL forex tidak dihitung sebagai trade; trade tanpa hasil juga tidak.
4. Strategi berstatus "rencana" TIDAK boleh tampak seperti aktif.
"""

from __future__ import annotations

import json
from pathlib import Path

from live_trading import pasar


def _tulis(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _tulis_jsonl(p: Path, baris: list[dict]) -> None:
    p.write_text("\n".join(json.dumps(b, ensure_ascii=False) for b in baris) + "\n", encoding="utf-8")


def test_tanpa_berkas_tidak_mengarang(tmp_path: Path):
    """Berkas tidak ada → tersedia False + alasan; jangan ada angka nol palsu."""
    c = pasar.ringkas_crypto_sinyal(tmp_path)
    assert c["tersedia"] is False and c["entries"] == []
    f = pasar.ringkas_forex_sinyal(tmp_path)
    assert f["tersedia"] is False and f["entries"] == []
    i = pasar.ringkas_idx_sinyal(tmp_path)
    assert i["tersedia"] is False and i["entries"] == []


def test_crypto_skor_dari_aturan(tmp_path: Path):
    _tulis_jsonl(
        tmp_path / "verdicts.jsonl",
        [
            {
                "ts": "2026-10-06T08:00:00+00:00",
                "pair": "AAAUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "STANDAR",
                "entry": 100.0,
                "sl": 98.0,
                "tp1": 104.0,
                "atr_pct": 1.2,
                "poi_low": 99.0,
                "poi_high": 101.0,
                "rules": [
                    {"rule": "poi_valid", "ok": True, "hard": True, "reason": "ok"},
                    {"rule": "atr_min", "ok": False, "hard": False, "reason": "ATR rendah"},
                ],
            }
        ],
    )
    c = pasar.ringkas_crypto_sinyal(tmp_path)
    assert c["tersedia"] is True
    e = c["entries"][0]
    assert e["skor"] == 50  # 1 dari 2 aturan lolos — terukur, bukan selera
    assert e["r_r"] == 2.0  # (104-100)/(100-98)
    assert e["aturan_gagal"] == ["atr_min"]
    assert "Rencana" not in [s["status"] for s in c["strategi"]]
    assert "rencana" in [s["status"] for s in c["strategi"]]


def test_forex_no_fill_tidak_dihitung(tmp_path: Path):
    """NO FILL = order tak pernah terisi → tetap tampil sebagai baris, tapi tidak masuk seri R."""
    j = {
        "xauusd": {
            "trades": [
                {"date_wib": "2026-09-23 04:26", "side": "BUY", "entry": 4000, "sl": 3980, "tp1": 4040,
                 "status": "CLOSED", "outcome": "SL", "r_multiple": -1.0},
                {"date_wib": "2026-09-29 13:34", "side": "BUY", "entry": 4115, "sl": 4102, "tp1": 4128,
                 "status": "CLOSED", "outcome": "NO FILL", "r_multiple": 0.0},
            ]
        },
        "multipair": [
            {"pair": "NAS100", "date_wib": "2026-09-28T15:00:31+07:00", "side": "BUY", "entry": 30000,
             "sl": 29900, "tp1": 30200, "status": "CLOSED", "outcome": "SL", "market_result": {"r": -1.0}},
        ],
        "impor": {"sha256": "x" * 64, "diimpor": "2026-10-06T00:00:00+00:00"},
    }
    _tulis(tmp_path / "forex_journal.json", j)
    f = pasar.ringkas_forex_sinyal(tmp_path)
    assert f["tersedia"] is True
    # Baris NO FILL tetap terlihat di tabel (transparan) …
    assert any(e["hasil"] == "NO FILL" for e in f["entries"])
    # … tapi seri pakem hanya 2 trade (XAUUSD SL + NAS100 SL), bukan 3.
    assert f["seri_pakem"]["n"] == 2
    assert f["seri_pakem"]["total_r"] == -2.0


def test_gmgn_bukan_r(tmp_path: Path):
    """LP diukur P&L USD — mean_r harus None (tidak dipaksa jadi R)."""
    _tulis_jsonl(
        tmp_path / "lp_ledger.jsonl",
        [
            {"symbol": "A", "status": "dinilai", "pnl_usd": -0.5},
            {"symbol": "B", "status": "dinilai", "pnl_usd": 0.2},
        ],
    )
    g = pasar.ringkas_akurasi_pasar(tmp_path)["pasar"]["gmgn"]
    baris = g["per_setup"]["LP Terukur (mark lokal)"]
    assert baris["n"] == 2
    assert baris["mean_r"] is None
    assert baris["total_pnl_usd"] == -0.3
    assert baris["winrate_pct"] == 50.0
    assert baris["tingkat"] == "INSUFFICIENT"  # 2 < 10 — jujur


def test_pakem_bukan_r_hitung_entri(tmp_path: Path):
    """Seri non-R memakai ambang jumlah entri + catatan bahwa hari tidak tersedia."""
    h = pasar._pakem_hitung(30, 20)
    assert h["tingkat"] == "PRELIMINARY"
    assert h["n_hari"] is None
    assert any("hari" in c for c in h["catatan"])


def test_idx_strategi_merugi_tidak_aktif() -> None:
    """Bukti 14 Okt: ARA_HUNTER (-139R) & INTRADAY (-0,38R) TIDAK boleh "aktif"."""
    from live_trading.pasar import STRATEGI_PASAR
    idx = {s["nama"]: s["status"] for s in STRATEGI_PASAR["idx"]}
    assert idx["ARA Hunter"] != "aktif", "ARA_HUNTER merugi -139R, jangan tampak aktif"
    assert idx["Scalping INTRADAY"] != "aktif", "INTRADAY -0,38R, jangan tampak aktif"
    assert "BSJP (Beli Sore Jual Pagi)" in idx and idx["BSJP (Beli Sore Jual Pagi)"] == "aktif"
