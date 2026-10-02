"""Tes eval harness deterministik: golden set per peran (narrator, verifier, anomaly)."""

from __future__ import annotations

from pathlib import Path

from warroom_llm.evals import MIN_KASUS_PER_PERAN, GoldenCase, run_case, run_suite
from warroom_llm.facts import FactRef

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"


def test_golden_set_lulus_semua() -> None:
    laporan = run_suite(GOLDEN_DIR)
    assert laporan.gagal == 0, f"kasus gagal: {laporan.detail_gagal}"
    assert laporan.ok is True


def test_minimal_20_kasus_untuk_minimal_3_peran() -> None:
    laporan = run_suite(GOLDEN_DIR)
    assert laporan.total >= MIN_KASUS_PER_PERAN
    assert set(laporan.roles) >= {"narrator", "verifier", "anomaly"}
    for role in ("narrator", "verifier", "anomaly"):
        assert laporan.per_peran[role] >= MIN_KASUS_PER_PERAN, f"{role} kurang dari 20 kasus"


def test_run_case_menangkap_ekspektasi_yang_salah() -> None:
    kasus = GoldenCase(
        id="uji-salah",
        role="narrator",
        provided_facts=(FactRef(101, "F1", "n=1175"),),
        existing_fact_ids=frozenset({101}),
        candidate={"kalimat": [{"teks": "win 88%", "fact_ids": []}], "nada": "x"},
        expect_verdict="ok",  # sengaja salah: seharusnya rejected
        expect_code=None,
    )
    hasil = run_case(kasus)
    assert hasil["ok"] is False
    assert hasil["got"].startswith("rejected/")
