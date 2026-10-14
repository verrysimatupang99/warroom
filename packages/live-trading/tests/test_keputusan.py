"""Regresi: jalur keputusan TUNGGAL paper & live (5 Okt 2026).

Ini tes inti dari janji "paper 1:1 dengan live". Yang dikunci bukan "kode jalan", tapi:
satu kandidat + satu konteks → SATU keputusan, dan keputusan itu identik apa pun mode-nya.
Kalau suatu saat ada yang menambahkan `if mode == "live"` di dalam keputusan, tes ini gagal.

CATATAN HERMETISITAS (7 Okt 2026): `slot_tersisa` sekarang SELALU diberikan eksplisit di
tes. Sebelumnya ia dibiarkan default, dan fungsi membaca jumlah posisi paper NYATA — saat
paper-scan membuka 3 posisi (WIF/INJ/AAVE), tes gagal karena slot penuh, bukan karena
regresi. Tes yang bergantung berkas state runtime bukan tes: itu cermin.
"""

from __future__ import annotations

import pytest

from live_trading.execution.keputusan import Konteks, decide_entry, jalur_untuk


@pytest.fixture(autouse=True)
def _state_kosong(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """RiskGate membaca posisi paper NYATA; arahkan LT_HOME ke direktori kosong.

    Tanpa ini, tes bergantung pada isi state runtime: begitu paper-scan membuka 3 posisi
    (nyata: WIF/INJ/AAVE, 7 Okt), semua tes di berkas ini gagal karena slot penuh —
    bukan karena regresi. Tes harus menguji kode, bukan mencerminkan berkas state.
    """
    monkeypatch.setenv("LT_HOME", str(tmp_path))
    yield

KANDIDAT = {
    "pair": "BTCUSDT", "direction": "LONG", "entry": 86000.0, "sl": 85280.0,
    "tp1": 87440.0, "tp2": 88880.0, "atr": 800.0,
}


def test_keputusan_identik_paper_dan_live() -> None:
    """Inti 1:1: mode hanya mengubah TUJUAN, bukan isi keputusan."""
    k_paper = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, mode="paper", slot_tersisa=3))
    k_live = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, mode="live", slot_tersisa=3))

    assert k_paper.masuk == k_live.masuk
    assert k_paper.size_usd == k_live.size_usd, "ukuran harus identik — bukan dihitung ulang"
    assert k_paper.sl == k_live.sl
    assert k_paper.tp1 == k_live.tp1 and k_paper.tp2 == k_live.tp2
    assert k_paper.risk_usd == k_live.risk_usd
    assert k_paper.jejak == k_live.jejak, "jejak langkah harus identik baris-demi-baris"
    # satu-satunya beda: tujuan
    assert jalur_untuk(k_paper) == "paper" and jalur_untuk(k_live) == "live"


def test_jejak_merekam_urutan_langkah() -> None:
    k = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, slot_tersisa=3))
    assert k.jejak[0] == "kandidat diterima"
    assert any("field lengkap" in j for j in k.jejak)
    assert any("gerbang risiko" in j for j in k.jejak)


def test_kandidat_tidak_lengkap_ditolak() -> None:
    k = decide_entry({"pair": "BTCUSDT"}, Konteks(equity_usd=100.0))
    assert k.masuk is False
    assert "tidak lengkap" in k.alasan


def test_slot_penuh_ditolak() -> None:
    k = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, slot_tersisa=0))
    assert k.masuk is False
    assert "slot" in k.alasan


def test_biaya_terukur_masuk_ke_keputusan() -> None:
    """Biaya terukur (P2) harus dibawa di keputusan, bukan dihitung ulang di eksekutor."""
    murah = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=10.0, slot_tersisa=3))
    mahal = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=25.0, slot_tersisa=3))
    assert murah.cost_bps == 10.0 and mahal.cost_bps == 25.0


def test_tanpa_biaya_terukur_tetap_jalan_dengan_asumsi() -> None:
    """Buku tak terbaca (fee_bps=None) tidak boleh memblokir; jatuh ke asumsi, bukan gagal."""
    k = decide_entry(KANDIDAT, Konteks(equity_usd=100.0, fee_bps=None, slot_tersisa=3))
    assert k.masuk is True
    assert k.cost_bps is None
