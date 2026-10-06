"""Gabungan baca-saja: atribusi per-agent + panel radar/LP/poly.

Aturan: panel tidak pernah menulis, gagal = n/a, dashboard tidak boleh mati
karena satu panel. Semua diuji tanpa jaringan (raw JSON / berkas tmp).
"""

from __future__ import annotations

import json

from live_trading import dashboard as dash
from live_trading import measure


def _baris(arah, bias, r):
    return {
        "hasil": "tp1" if r > 0 else "sl",
        "r": r,
        "direction": arah,
        "agents": {"agents": {"orderflow": {"bias": bias}}},
    }


def test_atribusi_pisah_setuju():
    rows = [
        _baris("long", 0.5, 1.0),
        _baris("long", 0.5, -1.0),
        _baris("long", -0.5, 2.0),
        _baris("short", -0.5, 1.5),
        _baris("long", None, 0.5),
    ]
    out = measure.atribusi_agent(rows)
    of = out["orderflow"]
    assert of["n"] == 5
    assert of["n_setuju"] == 3  # long+ / long+ / short-
    assert of["avg_setuju_r"] == round((1.0 - 1.0 + 1.5) / 3, 3)
    assert of["avg_tak_setuju_r"] == 2.0
    assert "kecil" in of["putusan"]


def test_atribusi_tanpa_agents():
    rows = [{"hasil": "tp1", "r": 1.0, "direction": "long"}]
    assert measure.atribusi_agent(rows) == {}


def test_radar_dari_raw():
    raw = json.dumps([
        {"chain": "arc", "window": "PRIME", "hp_count": 6, "avg_vl": 2.36, "age_days": 13},
        {"chain": "base", "window": "CLOSED", "hp_count": 3, "avg_vl": 1.1, "age_days": 1147},
    ])
    p = dash._radar_panel(raw=raw)
    assert p["tersedia"] is True
    assert p["arc_window"] == "PRIME" and p["arc_hp"] == 6 and p["n_chain"] == 2
    assert len(p["chains"]) == 2 and p["chains"][0]["chain"] == "arc"


def test_radar_rusak_jadi_na():
    assert dash._radar_panel(raw="bukan json")["tersedia"] is False


def test_lp_dari_berkas(tmp_path):
    f = tmp_path / "lp.json"
    f.write_text(json.dumps({"capital_usd": 30, "positions": [
        {"symbol": "UBI", "notional_usd": 30, "fee_usd_per_day_est": 1.449, "vl_at_entry": 4.83},
    ]}), encoding="utf-8")
    p = dash._lp_panel(path=str(f))
    assert p["tersedia"] is True and p["posisi"][0]["symbol"] == "UBI"
    assert dash._lp_panel(path=str(tmp_path / "hilang.json"))["tersedia"] is False


def test_poly_dari_berkas(tmp_path):
    f = tmp_path / "shadow.json"
    f.write_text(json.dumps({"balance": 20, "pnl": 0, "entries": 0,
                             "open": 0, "updated": "2026-09-24T05:57:26"}), encoding="utf-8")
    p = dash._poly_panel(path=str(f))
    assert p["tersedia"] is True
    assert p["arms"][0]["balance"] == 20


def test_poly_empat_arm(tmp_path):
    arms = []
    for i, pnl in enumerate([0, 5.0]):
        f = tmp_path / f"arm{i}.json"
        f.write_text(json.dumps({"balance": 100 + pnl, "pnl": pnl, "entries": i,
                                 "wins": i, "losses": 0, "open": 0,
                                 "updated": "2026-09-29T13:00:00"}), encoding="utf-8")
        arms.append(f"arm{i}")
    saved = dash._POLY_ARMS
    dash._POLY_ARMS = {a: str(tmp_path / f"{a}.json") for a in arms}
    try:
        p = dash._poly_panel()
    finally:
        dash._POLY_ARMS = saved
    assert p["tersedia"] is True and len(p["arms"]) == 2
    assert p["total_pnl"] == 5.0


def test_radar_baca_state_lokal(tmp_path):
    """State lokal (hasil `lt radar-update`): dibaca, umur dari diambil_epoch."""
    import time

    (tmp_path / "radar_state.json").write_text(
        json.dumps(
            {
                "diambil_epoch": time.time() - 600,
                "sumber": "lokal",
                "chains": [
                    {"chain": "arc", "window": "OPEN", "hp_count": 1, "avg_vl": 1.5, "age_days": 16}
                ],
            }
        ),
        encoding="utf-8",
    )
    p = dash._radar_panel(state_dir=tmp_path)
    assert p["tersedia"] is True and p["sumber"] == "lokal"
    assert p["arc_window"] == "OPEN" and p["n_chain"] == 1
    assert 9 <= p["umur_mnt"] <= 11


def test_radar_state_basi_umur_jujur(tmp_path):
    """State lama: umurnya dilaporkan apa adanya (bukan n/a, bukan 0)."""
    import time

    (tmp_path / "radar_state.json").write_text(
        json.dumps(
            {
                "diambil_epoch": time.time() - 7200,
                "chains": [
                    {"chain": "arc", "window": "OPEN", "hp_count": 1, "avg_vl": 1.5, "age_days": 16}
                ],
            }
        ),
        encoding="utf-8",
    )
    p = dash._radar_panel(state_dir=tmp_path)
    assert p["tersedia"] is True and p["sumber"] == "lokal"
    assert p["umur_mnt"] >= 119


def test_radar_tanpa_state_jadi_na(tmp_path):
    """Belum pernah `lt radar-update`: n/a + alasan, bukan nilai karangan."""
    p = dash._radar_panel(state_dir=tmp_path)
    assert p["tersedia"] is False
    assert "radar_state.json" in p["error"]
