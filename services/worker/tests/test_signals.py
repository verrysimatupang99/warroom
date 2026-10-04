"""Tes adapter sinyal (Aksi 2) — ledger sintetis, tanpa jaringan, tanpa menyentuh state nyata.

Prinsip yang diuji: hanya sinyal yang LOLOS yang dikabarkan; ledger yang tidak terbaca
menghasilkan **status + alasan** (bukan daftar kosong yang menyamar jadi "tidak ada sinyal");
setiap hasil membawa label jujur.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from warroom_worker.adapters import signals as sig

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _baris(
    pair: str,
    arah: str,
    menit_lalu: float,
    *,
    allowed: bool = True,
    tier: str = "PREMIUM",
    rules: list[dict] | None = None,
) -> dict:
    return {
        "ts": (NOW - timedelta(minutes=menit_lalu)).isoformat(timespec="seconds"),
        "pair": pair,
        "direction": arah,
        "allowed": allowed,
        "tier": tier,
        "entry": 100.0,
        "sl": 98.5,
        "tp1": 101.5,
        "risk_pct": 1.5,
        "rules": rules
        if rules is not None
        else [{"rule": "mtf_alignment", "ok": True, "hard": True, "reason": "searah"}],
    }


def _tulis(tmp_path: Path, baris: list[dict]) -> Path:
    p = tmp_path / "state"
    p.mkdir(parents=True, exist_ok=True)
    (p / "verdicts.jsonl").write_text(
        "\n".join(json.dumps(b) for b in baris) + "\n", encoding="utf-8"
    )
    return p


def test_hanya_yang_lolos_dan_dalam_jendela(tmp_path) -> None:
    d = _tulis(
        tmp_path,
        [
            _baris("BTCUSDT", "LONG", 30),
            _baris("ETHUSDT", "SHORT", 60, allowed=False),  # ditolak gate
            _baris("SOLUSDT", "LONG", 60 * 20),  # di luar jendela 6 jam
        ],
    )
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW)
    assert h["status"] == "ok"
    assert [s["pair"] for s in h["sinyal"]] == ["BTCUSDT"]


def test_unik_per_pair_dan_arah_terbaru_menang(tmp_path) -> None:
    d = _tulis(
        tmp_path,
        [
            _baris("BTCUSDT", "LONG", 120, tier="STANDAR"),
            _baris("BTCUSDT", "LONG", 20, tier="PREMIUM"),  # lebih baru
            _baris("BTCUSDT", "SHORT", 60),  # arah lain = entri terpisah
        ],
    )
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW)
    pasangan = sorted((s["pair"], s["arah"], s["tier"]) for s in h["sinyal"])
    assert pasangan == [("BTCUSDT", "LONG", "PREMIUM"), ("BTCUSDT", "SHORT", "PREMIUM")]


def test_terbaru_di_depan(tmp_path) -> None:
    d = _tulis(tmp_path, [_baris("AAAUSDT", "LONG", 200), _baris("BBBUSDT", "LONG", 10)])
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW)
    assert [s["pair"] for s in h["sinyal"]] == ["BBBUSDT", "AAAUSDT"]


def test_selalu_membawa_label_jujur(tmp_path) -> None:
    d = _tulis(tmp_path, [_baris("BTCUSDT", "LONG", 5)])
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW)
    assert "belum-terbukti" in h["label"]
    assert "belum-terbukti" in sig.LABEL_JUJUR


def test_aturan_yang_gagal_dikumpulkan(tmp_path) -> None:
    rules = [
        {"rule": "mtf_alignment", "ok": True, "hard": True, "reason": "searah"},
        {"rule": "atr_min", "ok": False, "hard": False, "reason": "ATR tipis"},
    ]
    d = _tulis(tmp_path, [_baris("BTCUSDT", "LONG", 5, rules=rules)])
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW)
    assert h["sinyal"][0]["aturan_gagal"] == ["atr_min"]


def test_ledger_tidak_ada_menghasilkan_status_bukan_kosong(tmp_path) -> None:
    """Penting: 'tidak bisa dibaca' TIDAK boleh menyamar sebagai 'tidak ada sinyal'."""
    kosong = tmp_path / "tanpa-state"
    kosong.mkdir()
    h = sig.sinyal_terakhir(kosong, jam_terakhir=6, sekarang=NOW)
    assert h["status"] != "ok"
    assert h["sinyal"] == []
    assert h["detail"]


def test_baris_rusak_dilewati_dan_dihitung(tmp_path) -> None:
    p = tmp_path / "state"
    p.mkdir(parents=True)
    (p / "verdicts.jsonl").write_text(
        json.dumps(_baris("BTCUSDT", "LONG", 5)) + "\n{bukan json}\n", encoding="utf-8"
    )
    h = sig.sinyal_terakhir(p, jam_terakhir=6, sekarang=NOW)
    assert h["status"] == "ok"
    assert h["rusak"] == 1
    assert len(h["sinyal"]) == 1


def test_batas_max_n(tmp_path) -> None:
    d = _tulis(tmp_path, [_baris(f"X{i}USDT", "LONG", i + 1) for i in range(20)])
    h = sig.sinyal_terakhir(d, jam_terakhir=6, sekarang=NOW, max_n=5)
    assert len(h["sinyal"]) == 5
