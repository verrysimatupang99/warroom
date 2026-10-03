"""Tes gate service (P1-T2).

Angka acuan diambil dari studi live Polymarket (`docs/blueprint/01-studi-polymarket.md` §3):
win rate 79,0% pada n=1.175, CI95 76,6–81,2%, BE 77,0%, fee nyata 0.
"""

from __future__ import annotations

import pytest
from warroom_core.gate import (
    DEFAULT_CI,
    GateInput,
    evaluate,
    required_n,
    wilson_interval,
)

# --- Wilson: cocok dengan angka studi -------------------------------------------------


def test_wilson_cocok_angka_studi_polymarket() -> None:
    """n=1.175, win=928 (79,0%) → CI95 76,6–81,2% seperti di dokumen studi."""
    low, high = wilson_interval(928, 1175, ci=0.95)
    assert low == pytest.approx(0.766, abs=0.001)
    assert high == pytest.approx(0.812, abs=0.001)


def test_wilson_ci_90_lebih_sempit_dari_ci_95() -> None:
    low90, high90 = wilson_interval(928, 1175, ci=0.90)
    low95, high95 = wilson_interval(928, 1175, ci=0.95)
    assert low90 > low95
    assert high90 < high95


def test_wilson_tanpa_sampel_mengembalikan_seluruh_rentang() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_tolak_win_di_luar_rentang() -> None:
    with pytest.raises(ValueError):
        wilson_interval(5, 3)


# --- Aturan mutlak: lolos HANYA bila ci_low > be --------------------------------------


def test_lolos_hanya_bila_ci_low_melewati_be() -> None:
    """Properti inti: pada n=required_n harus lolos; pada n-1 harus gagal."""
    be, p = 0.77, 0.79
    n = required_n(be, p, DEFAULT_CI)
    assert n is not None

    def verdict_at(nn: int) -> str:
        win = int(p * nn + 0.5)
        return evaluate(GateInput(n=nn, win=win, be=be, split="frozen:uji")).verdict

    assert verdict_at(n) == "lolos"
    assert verdict_at(n - 1) == "gagal"


def test_gagal_nyaris_ci_low_di_atas_be() -> None:
    """Kasus nyata: ci_low 0,7696 vs BE 0,7700 → gagal (bukan 'hampir lolos')."""
    r = evaluate(GateInput(n=1175, win=928, be=0.77, ci=0.90, split="frozen:studi-2026-09"))
    assert r.verdict == "gagal"
    assert r.ci_low < r.be
    # dan memang belum lolos pada CI95 juga
    assert evaluate(GateInput(n=1175, win=928, be=0.77, ci=0.95, split="frozen:x")).verdict == "gagal"


def test_insufficient_bila_n_di_bawah_min_n() -> None:
    r = evaluate(GateInput(n=12, win=11, be=0.70, split="frozen:x"))
    assert r.verdict == "insufficient"
    assert "min_n" in r.reason


def test_insufficient_bila_split_tidak_dibekukan() -> None:
    r = evaluate(GateInput(n=500, win=420, be=0.70, split=None))
    assert r.verdict == "insufficient"
    assert "split" in r.reason
    r2 = evaluate(GateInput(n=500, win=420, be=0.70, split="semua-data"))
    assert r2.verdict == "insufficient"


def test_eksplorasi_tidak_bisa_dipromosikan() -> None:
    """Hasil grid search tidak boleh lolos walau angkanya bagus (kebijakan: eksplorasi ≠ konfirmasi)."""
    r = evaluate(GateInput(n=5000, win=4500, be=0.70, split="frozen:x", label="eksplorasi"))
    assert r.verdict == "insufficient"
    assert "eksplorasi" in r.reason


def test_tanpa_sampel_insufficient_bukan_gagal() -> None:
    r = evaluate(GateInput(n=0, win=0, be=0.77))
    assert r.verdict == "insufficient"
    assert r.required_n is None


def test_win_di_luar_rentang_ditolak_keras() -> None:
    with pytest.raises(ValueError):
        evaluate(GateInput(n=10, win=11, be=0.5, split="frozen:x"))


# --- required_n -----------------------------------------------------------------------


def test_required_n_none_bila_win_rate_di_bawah_be() -> None:
    """Menambah sampel tidak akan menolong; ini temuan, bukan alasan menurunkan ambang."""
    assert required_n(0.80, 0.79) is None
    assert required_n(0.80, 0.80) is None


def test_required_n_masuk_akal() -> None:
    """79% vs BE 77%: ratusan–ribuan sampel, bukan 10 dan bukan tak hingga."""
    n = required_n(0.77, 0.79, 0.90)
    assert n is not None and 500 < n < 5000


def test_gagal_menyarankan_jumlah_sampel() -> None:
    r = evaluate(GateInput(n=300, win=237, be=0.77, ci=0.90, split="frozen:x"))
    assert r.verdict == "gagal"
    assert r.required_n is not None
    assert any("butuh n" in c for c in r.notes)


def test_win_rate_di_bawah_be_memberi_catatan_jujur() -> None:
    r = evaluate(GateInput(n=300, win=200, be=0.77, ci=0.90, split="frozen:x"))
    assert r.verdict == "gagal"
    assert r.required_n is None
    assert any("tidak akan meloloskan" in c for c in r.notes)


# --- koreksi klaster (deff) — W3, kasus nyata 3 Okt 2026 ------------------------------


def test_deff_bawah_satu_ditolak() -> None:
    """Koreksi tidak boleh mempersempit CI (arah melonggarkan) — ditolak, bukan dibiarkan."""
    with pytest.raises(ValueError):
        evaluate(GateInput(n=100, win=80, be=0.7, deff=0.9, split="frozen:x"))
    with pytest.raises(ValueError):
        required_n(0.77, 0.79, deff=0.9)


def test_deff_hanya_mempersulit() -> None:
    """deff > 1: ci_low turun dan required_n naik — tidak pernah sebaliknya."""
    tanpa = evaluate(GateInput(n=3977, win=3107, be=0.7662, ci=0.95, split="frozen:x"))
    deff = evaluate(GateInput(n=3977, win=3107, be=0.7662, ci=0.95, deff=1.345, split="frozen:x"))
    assert deff.ci_low < tanpa.ci_low
    assert (deff.required_n or 0) > (tanpa.required_n or 0)
    assert deff.notes and "koreksi klaster" in deff.notes[0]


def test_kasus_favorit_polymarket_dua_kebijakan() -> None:
    """Kasus nyata 3 Okt: 90% tanpa deff lolos; 95% + deff (alat Poly) belum.

    Angka dari `qa/favorite-live-verdict.py --json`: n=3977, win=3107, be=0.7662,
    deff=1.345. Keputusan kebijakan (mana yang otoritatif) ada di manusia —
    `docs/blueprint/07-perintah-kerja-hermes.md` §B.
    """
    longgar = evaluate(GateInput(n=3977, win=3107, be=0.7662, ci=0.90, split="frozen:x"))
    ketat = evaluate(GateInput(n=3977, win=3107, be=0.7662, ci=0.95, deff=1.345, split="frozen:x"))
    assert longgar.verdict == "lolos"
    assert ketat.verdict == "gagal"
    assert ketat.ci_low == pytest.approx(0.7659, abs=0.001)