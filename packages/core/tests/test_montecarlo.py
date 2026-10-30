"""Tes bootstrap Monte Carlo: deterministik, P(profit), drawdown."""

from __future__ import annotations

from warroom_core.montecarlo import bootstrap


def test_kosong() -> None:
    assert bootstrap([]) == {"n_sampel": 0, "n_simulasi": 0}


def test_semua_positif_p_profit_100() -> None:
    h = bootstrap([1.0, 0.5, 0.25], n=200, seed=1)
    assert h["p_profit"] == 100.0
    assert h["total_p5"] > 0
    assert h["maxdd_p95"] == 0.0


def test_campuran_deterministik_dan_drawdown() -> None:
    h1 = bootstrap([1, -1, 1, -1, 2, -0.5], n=500, seed=7)
    h2 = bootstrap([1, -1, 1, -1, 2, -0.5], n=500, seed=7)
    assert h1 == h2
    assert 0 <= h1["p_profit"] <= 100
    assert h1["total_p5"] <= h1["total_p50"] <= h1["total_p95"]
    assert h1["maxdd_p95"] >= 0


def test_semua_negatif_tidak_pernah_profit() -> None:
    h = bootstrap([-1.0, -0.5], n=100, seed=2)
    assert h["p_profit"] == 0.0
    assert h["total_p95"] < 0
