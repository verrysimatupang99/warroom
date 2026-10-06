"""Tes rekonsiliasi posisi menggantung — kejujuran di atas angka yang enak dilihat.

Kasus nyata 6 Okt: OP_USDT & LIT_USDT "still_open" sejak 27 Sep padahal sudah SL dua
hari kemudian. Ledger melaporkan +3,844R; seharusnya +1,844R.
"""

from __future__ import annotations

import json
from pathlib import Path

from live_trading import rekonsiliasi as rk


def _pos(**kw):
    dasar = {
        "signal_id": "#SIG-TEST",
        "pair": "OP_USDT",
        "direction": "LONG",
        "date_added": "2026-09-26T23:06:00+07:00",
        "entry_zone": "0.1469-0.1476",
        "sl": 0.14027,
        "tp1": 0.15419,
        "tp2": 0.16115,
        "status": "still_open",
    }
    dasar.update(kw)
    return dasar


def _k(times, highs, lows):
    return {"t": times, "h": highs, "l": lows}


HARI = 1758902400  # 2026-09-26T20:00:00Z


def test_fill_lalu_sl_konservatif():
    """Candle menyentuh SL dan TP1 sekaligus → dihitung SL (tidak menyenangkan diri)."""
    k = _k([HARI, HARI + 3600], [0.150, 0.158], [0.1460, 0.139])
    out = rk.rekonstruksi_posisi(_pos(), ambil_klines=lambda *a, **kw: k)
    assert out is not None
    assert out["status"] == "closed_SL" and out["r"] == -1.0
    assert out["source"] == "rekonsiliasi"
    assert "SL dicek lebih dulu" in out["note"]


def test_tidak_pernah_fill_expired_r0():
    k = _k([HARI, HARI + 3600], [0.170, 0.171], [0.160, 0.161])
    out = rk.rekonstruksi_posisi(_pos(), ambil_klines=lambda *a, **kw: k)
    assert out is not None
    assert out["status"] == "expired" and out["r"] == 0.0
    assert out["note"].startswith("REKONSILIASI")


def test_masih_jalan_tidak_dipaksa():
    """Sudah terisi tapi belum kena level → None (jangan tutup paksa)."""
    k = _k([HARI, HARI + 3600], [0.150, 0.152], [0.1460, 0.145])
    assert rk.rekonstruksi_posisi(_pos(), ambil_klines=lambda *a, **kw: k) is None


def test_tp2_diakui():
    k = _k([HARI, HARI + 3600], [0.150, 0.162], [0.1460, 0.149])
    out = rk.rekonstruksi_posisi(_pos(), ambil_klines=lambda *a, **kw: k)
    assert out is not None and out["status"] == "closed_TP2" and out["r"] == 2.0


def test_sudah_ada_baris_ledger_tidak_disentuh(tmp_path: Path):
    """Satu posisi = satu baris hasil. Jangan menulis ulang yang sudah ada."""
    (tmp_path / "crypto-watchlist.json").write_text(
        json.dumps({"items": [_pos()]}), encoding="utf-8"
    )
    (tmp_path / "crypto_equity.jsonl").write_text(
        json.dumps({"signal_id": "#SIG-TEST", "pair": "OP_USDT", "r": -1.0}) + "\n",
        encoding="utf-8",
    )
    rep = rk.rekonsiliasi_watchlist(
        tmp_path, ambil_klines=lambda *a, **kw: _k([], [], [])
    )
    assert rep["diperiksa"] == 0
    assert rep["baru"] == []


def test_gagal_ambil_candle_tidak_menulis(tmp_path: Path):
    (tmp_path / "crypto-watchlist.json").write_text(
        json.dumps({"items": [_pos()]}), encoding="utf-8"
    )

    def _boom(*a, **kw):
        raise OSError("jaringan putus")

    rep = rk.rekonsiliasi_watchlist(tmp_path, ambil_klines=_boom)
    assert rep["baru"] == []
    assert rep["gagal"] and "jaringan" in rep["gagal"][0]["alasan"]
    assert not (tmp_path / "crypto_equity.jsonl").exists()


def test_menulis_baris_hasil_ke_ledger(tmp_path: Path):
    (tmp_path / "crypto-watchlist.json").write_text(
        json.dumps({"items": [_pos()]}), encoding="utf-8"
    )
    k = _k([HARI, HARI + 3600], [0.150, 0.145], [0.1460, 0.139])
    rep = rk.rekonsiliasi_watchlist(tmp_path, ambil_klines=lambda *a, **kw: k)
    assert len(rep["baru"]) == 1
    baris = json.loads((tmp_path / "crypto_equity.jsonl").read_text().strip())
    assert baris["status"] == "closed_SL" and baris["source"] == "rekonsiliasi"
