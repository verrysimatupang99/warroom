"""Regresi: jalur keputusan TUNGGAL paper & live (5 Okt 2026).

Ini tes inti dari janji "paper 1:1 dengan live". Yang dikunci bukan "kode jalan", tapi:
satu kandidat + satu konteks → SATU keputusan, dan keputusan itu identik apa pun mode-nya.
Kalau suatu saat ada yang menambahkan `if mode == "live"` di dalam keputusan, tes ini gagal.
"""

from __future__ import annotations

from live_trading.execution.keputusan import Konteks, jalur_untuk, putuskan_masuk

KANDIDAT = {
    "pair": "BTCUSDT", "direction": "LONG", "entry": 86000.0, "sl": 85280.0,
    "tp1": 87440.0, "tp2": 88880.0, "atr": 800.0,
}


def test_keputusan_identik_paper_dan_live() -> None:
    """Inti 1:1: mode hanya mengubah TUJUAN, bukan isi keputusan."""
    k_paper = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, mode="paper"))
    k_live = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, mode="live"))

    assert k_paper.masuk == k_live.masuk
    assert k_paper.size_usd == k_live.size_usd, "ukuran harus identik — bukan dihitung ulang"
    assert k_paper.sl == k_live.sl
    assert k_paper.tp1 == k_live.tp1 and k_paper.tp2 == k_live.tp2
    assert k_paper.risk_usd == k_live.risk_usd
    assert k_paper.jejak == k_live.jejak, "jejak langkah harus identik baris-demi-baris"
    # satu-satunya beda: tujuan
    assert jalur_untuk(k_paper) == "paper" and jalur_untuk(k_live) == "live"


def test_jejak_merekam_urutan_langkah() -> None:
    k = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0))
    assert k.jejak[0] == "kandidat diterima"
    assert any("field lengkap" in j for j in k.jejak)
    assert any("gerbang risiko" in j for j in k.jejak)


def test_kandidat_tidak_lengkap_ditolak() -> None:
    k = putuskan_masuk({"pair": "BTCUSDT"}, Konteks(equity_usd=100.0))
    assert k.masuk is False
    assert "tidak lengkap" in k.alasan


def test_slot_penuh_ditolak() -> None:
    k = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, slot_tersisa=0))
    assert k.masuk is False
    assert "slot" in k.alasan


def test_biaya_terukur_masuk_ke_keputusan() -> None:
    """Biaya terukur (P2) harus dibawa di keputusan, bukan dihitung ulang di eksekutor."""
    murah = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0))
    mahal = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=25.0))
    assert murah.cost_bps == 10.0 and mahal.cost_bps == 25.0


def test_tanpa_biaya_terukur_tetap_jalan_dengan_asumsi() -> None:
    """Buku tak terbaca (fee_bps=None) tidak boleh memblokir; jatuh ke asumsi, bukan gagal."""
    k = putuskan_masuk(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=None))
    assert k.masuk is True
    assert k.cost_bps is None
