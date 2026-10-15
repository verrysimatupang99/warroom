"""Tes endpoint /api/v1/leaderboard/strategi — termasuk status gagal yang jujur."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from warroom_api import auth
from warroom_core.db import Fact, session_scope


@pytest.fixture(autouse=True)
def _isolasi(bersihkan_db):
    yield


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


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


def test_endpoint_wajib_sesi(client) -> None:
    r = client.get("/api/v1/leaderboard/strategi")
    assert r.status_code == 401


def test_endpoint_kosong_tidak_mengarang_angka(client, make_user) -> None:
    _, sid = make_user("lb-kosong", role="viewer")
    r = client.get("/api/v1/leaderboard/strategi", headers=_cookie(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["total_baris"] >= 1 and body["strategi"]
    for row in body["strategi"]:
        assert row["status"] == "kosong"
        for angka in ("winrate_pct", "expectancy_r", "total_r", "max_drawdown_r", "pnl_usd"):
            assert row[angka] is None, f"{row['id']}: {angka} dikarang saat fakta kosong"
        assert row["rank"] is None and row["status_detail"]


def test_endpoint_menampilkan_setup_dan_status(client, make_user) -> None:
    _, sid = make_user("lb-isi", role="viewer")
    _fakta("snapshot", "pasar_akurasi", {
        "pasar": {
            "crypto": {
                "tersedia": True,
                "bukti": {"biaya_tercatat": True, "biaya_keterangan": "cost_bps terukur"},
                "per_setup": {
                    "SMC": {
                        "nama": "SMC multi-timeframe", "n": 12, "wins": 9, "losses": 3,
                        "mean_r": 0.5, "total_r": 6.0, "winrate_pct": 75.0,
                        "max_drawdown_r": 2.0,
                    },
                    "LOSING": {
                        "nama": "Losing", "n": 33, "wins": 3, "losses": 30,
                        "mean_r": -0.2, "total_r": -6.6, "winrate_pct": 9.1,
                        "total_pnl_usd": -3.0,
                    },
                },
            },
        },
    })
    r = client.get("/api/v1/leaderboard/strategi", headers=_cookie(sid))
    assert r.status_code == 200
    body = r.json()
    crypto = [row for row in body["strategi"] if row["pasar"] == "crypto"]
    assert len(crypto) == 2 and body["benched"] == 1

    smc = next(row for row in crypto if row["expectancy_r"] == 0.5)
    assert smc["rank"] == 1
    assert smc["winrate_pct"] == 75.0 and smc["total_r"] == 6.0
    assert smc["max_drawdown_r"] == 2.0
    assert smc["biaya"]["tercatat"] is True and smc["status"] == "aktif"

    rugi = next(row for row in crypto if row["benched"])
    assert rugi["status"] == "benched" and rugi["alasan_benched"]


def test_endpoint_meneruskan_alasan_gagal_pasar(client, make_user) -> None:
    _, sid = make_user("lb-gagal", role="viewer")
    _fakta("snapshot", "idx_akurasi", {
        "tersedia": False,
        "alasan": "ledger tidak terbaca: state/idx_ledger.db",
    })
    r = client.get("/api/v1/leaderboard/strategi", headers=_cookie(sid))
    assert r.status_code == 200
    idx = next(row for row in r.json()["strategi"] if row["pasar"] == "idx")
    # Kegagalan baca ledger = "gagal", bukan "kosong" dan bukan baris seludiang 0.
    assert idx["status"] == "gagal"
    assert "idx_ledger.db" in idx["status_detail"]
    assert idx["expectancy_r"] is None
