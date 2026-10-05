"""Regresi: sinyal terbaik per pasar (5 Okt 2026).

Yang dikunci:
1. Selalu mengembalikan SEMUA pasar (yang kosong pun) — UI tidak perlu tahu pasar mana yang
   kebetulan ada; kalau ini berubah, Home akan diam-diam kehilangan kartu.
2. Pasar kosong `ada=False` dan `skor=None` — BUKAN 0. Nol adalah angka; "tidak ada" bukan.
3. Skor crypto dihitung dari aturan yang lolos, dan kandidat PREMIUM dipilih di atas SKIP.
4. Klaim Polymarket yang belum lewat split beku WAJIB `terverifikasi=False` + catatan.
"""

from __future__ import annotations

from datetime import UTC, datetime

from warroom_core.db import Fact, session_scope
from warroom_core.sinyal import PASAR, sinyal_terbaik_per_pasar


def _fakta(s, kind: str, key: str, value) -> None:
    s.add(Fact(kind=kind, key=key, value_json=value, source="uji",
               observed_at=datetime.now(UTC), ttl_s=3600, hash=f"h-{kind}-{key}"))


def test_selalu_semua_pasar(db) -> None:
    """Tanpa fakta apa pun, semua pasar tetap muncul — sebagai 'tidak ada', bukan hilang."""
    with session_scope() as s:
        rows = sinyal_terbaik_per_pasar(s)
    assert len(rows) == len(PASAR)
    assert {r.pasar for r in rows} == {k for k, _l, _s in PASAR}
    assert all(r.ada is False for r in rows)
    assert all(r.skor is None for r in rows), "kosong harus None, bukan 0"


def test_crypto_pilih_premium_dan_skor_dari_aturan(db) -> None:
    with session_scope() as s:
        _fakta(s, "snapshot", "kandidat", [
            {"pair": "SKIPUSDT", "direction": "LONG", "tier": "SKIP", "entry": 1.0, "sl": 0.9,
             "rules": [{"ok": True, "rule": "a"}, {"ok": False, "rule": "b"}]},
            {"pair": "BAGUSUSDT", "direction": "LONG", "tier": "PREMIUM", "entry": 2.0, "sl": 1.9,
             "tp1": 2.2, "rules": [{"ok": True, "rule": "a"}, {"ok": True, "rule": "b"}]},
        ])
    with session_scope() as s:
        rows = {r.pasar: r for r in sinyal_terbaik_per_pasar(s)}
    c = rows["crypto"]
    assert c.ada is True
    assert c.subjek == "BAGUSUSDT", "PREMIUM harus menang atas SKIP"
    assert c.skor == 100
    assert c.terverifikasi is False
    assert "BUKAN edge terbukti" in c.catatan_kejujuran


def test_polymarket_klaim_tanpa_split_tidak_terverifikasi(db) -> None:
    """Klaim EDGE dengan split null = eksplorasi. Harus ditandai, bukan disembunyikan."""
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 78.25, "breakEven_pct": 76.66, "ci95": [76.75, 79.67],
            "nNeeded": 7392, "verdict_alat": "EDGE", "split": None, "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in sinyal_terbaik_per_pasar(s)}
    p = rows["polymarket"]
    assert p.ada is True
    assert p.terverifikasi is False
    assert "BELUM TERVERIFIKASI" in p.catatan_kejujuran
    assert p.skor == 78


def test_polymarket_dengan_split_terverifikasi(db) -> None:
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 80.0, "breakEven_pct": 76.66, "verdict_alat": "EDGE",
            "split": "frozen:poly-paired-abc", "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in sinyal_terbaik_per_pasar(s)}
    p = rows["polymarket"]
    assert p.terverifikasi is True
    assert "frozen:poly-paired-abc" in p.catatan_kejujuran


def test_lp_sorot_yang_harus_keluar(db) -> None:
    """Sinyal LP terpenting adalah yang harus KELUAR — itu keputusan, bukan info."""
    with session_scope() as s:
        _fakta(s, "snapshot", "lp_paper", {"posisi": [
            {"symbol": "AMAN", "verdict": "PANTAU", "alasan": "sehat", "notional": 30.0},
            {"symbol": "BAHAYA", "verdict": "KELUAR", "alasan": "IL -9% terlalu dalam", "notional": 30.0},
        ]})
    with session_scope() as s:
        rows = {r.pasar: r for r in sinyal_terbaik_per_pasar(s)}
    lp = rows["lp"]
    assert lp.subjek == "BAHAYA"
    assert lp.arah == "KELUAR"


def test_idx_dan_forex_kosong_menyebut_alasan(db) -> None:
    with session_scope() as s:
        rows = {r.pasar: r for r in sinyal_terbaik_per_pasar(s)}
    assert "BSJP" in rows["idx"].alasan
    assert rows["forex"].ada is False
