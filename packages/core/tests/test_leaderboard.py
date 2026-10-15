"""Tes papan peringkat strategi — angka apa adanya dan status yang jujur."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from warroom_core.db import Fact, session_scope
from warroom_core.leaderboard import strategy_leaderboard


def _fakta(kind: str, key: str, value, umur_s: int = 10) -> None:
    with session_scope() as s:
        s.add(Fact(
            kind=kind,
            key=key,
            value_json=value,
            source="tes",
            observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
            ttl_s=1800,
            hash="h",
        ))


@pytest.fixture(autouse=True)
def _isolasi(bersihkan_db):
    yield


def test_db_kosong_status_kosong_bukan_nol() -> None:
    with session_scope() as s:
        hasil = strategy_leaderboard(s)
    assert hasil["total_baris"] == len(hasil["strategi"]) > 0
    for r in hasil["strategi"]:
        assert r["status"] == "kosong"
        assert r["expectancy_r"] is None and r["total_r"] is None
        assert r["rank"] is None
        # Kosong karena belum ada fakta — bukan gagal baca sumber.
        assert r["status_detail"]


def test_setup_berangka_diberi_rank_dan_karantina_ditandai() -> None:
    _fakta("snapshot", "pasar_akurasi", {
        "pasar": {
            "crypto": {
                "tersedia": True,
                "bukti": {"biaya_tercatat": True, "biaya_keterangan": "cost_bps terukur"},
                "per_setup": {
                    # Rugi, sampel besar → menyembunyikannya = menipu perbandingan.
                    "ARA_HUNTER": {
                        "nama": "ARA Hunter", "n": 40, "wins": 5, "losses": 35,
                        "mean_r": -0.35, "total_r": -14.0, "winrate_pct": 12.5,
                        "n_hari": 8, "total_pnl_usd": -9.2,
                    },
                    "SMC": {
                        "nama": "SMC", "n": 12, "wins": 9, "losses": 3,
                        "mean_r": 0.5, "total_r": 6.0, "winrate_pct": 75.0,
                        "max_drawdown_r": 2.0, "ringkas": {"max_drawdown_r": 2.0},
                    },
                },
            },
        },
    })
    with session_scope() as s:
        hasil = strategy_leaderboard(s)

    crypto = [r for r in hasil["strategi"] if r["pasar"] == "crypto"]
    assert len(crypto) == 2
    smc = next(r for r in crypto if r["nama"] == "SMC")
    ara = next(r for r in crypto if r["nama"] == "ARA Hunter")
    assert (smc["rank"], ara["rank"]) == (1, 2)
    assert smc["expectancy_r"] == 0.5 and smc["total_r"] == 6.0
    assert smc["max_drawdown_r"] == 2.0
    assert smc["status"] == "aktif" and smc["biaya"]["tercatat"] is True
    assert ara["status"] == "benched" and ara["benched"] is True
    assert ara["alasan_benched"] and "rugi" in ara["alasan_benched"]
    assert ara["rank"] == 2  # benched tetap diberi rank — datanya yang menyembunyikannya
    assert hasil["benched"] == 1


def test_pasar_gagal_dilaporkan_gagal_bukan_kosong() -> None:
    _fakta("snapshot", "idx_akurasi", {
        "tersedia": False,
        "alasan": "ledger tidak terbaca: state/idx_ledger.db",
    })
    with session_scope() as s:
        hasil = strategy_leaderboard(s)
    idx = next(r for r in hasil["strategi"] if r["pasar"] == "idx")
    assert idx["status"] == "gagal"
    assert "idx_ledger.db" in idx["status_detail"]
    # Mesin IDX dibekukan — angka historis tidak boleh terlihat seperti berjalan.
    assert idx["beku"] is True
