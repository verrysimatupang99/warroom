"""Tes jurnal sinyal: pencocokan alert → verdict dan ringkasan hasil."""

from __future__ import annotations

from datetime import UTC, datetime

from warroom_core.jurnal_sinyal import cocokkan, muat_outcomes, ringkas


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


def _out(
    ts: float,
    pair: str,
    side: str,
    *,
    allowed: bool = True,
    hasil: str = "tp1",
    r: float = 1.0,
) -> dict:
    return {
        "ts": _iso(ts),
        "_ts": ts,
        "pair": pair,
        "direction": side,
        "allowed": allowed,
        "tier": "PREMIUM",
        "hasil": hasil,
        "r": r,
        "entry": 10.0,
        "sl": 9.0,
        "tp1": 11.0,
    }


def test_muat_outcomes_melewati_baris_rusak(tmp_path) -> None:
    p = tmp_path / "outcomes.jsonl"
    p.write_text('{"ts":"2026-10-30T08:00:00+00:00","pair":"A"}\nbukan json\n\n', encoding="utf-8")
    rows = muat_outcomes(p)
    assert len(rows) == 1 and rows[0]["pair"] == "A" and rows[0]["_ts"] > 0


def test_cocokkan_memilih_verdict_terdekat_dan_dedupe() -> None:
    t = 1793347200.0
    outcomes = [
        _out(t - 3600, "INJUSDT", "SHORT"),
        _out(t - 60, "INJUSDT", "SHORT"),
        _out(t - 60, "INJUSDT", "LONG"),  # arah beda
        _out(t - 60, "INJUSDT", "SHORT", allowed=False),
    ]
    alerts = [
        {"id": 1, "t": int(t), "subject": "sinyal/INJUSDT/SHORT"},
        {"id": 2, "t": int(t + 5), "subject": "sinyal/INJUSDT/SHORT"},  # duplikat
        {"id": 3, "t": int(t), "subject": "sinyal/INJUSDT/LONG"},
    ]
    rows = cocokkan(alerts, outcomes)
    assert [r["alert_id"] for r in rows] == [1, 3]
    assert rows[0]["verdict"]["ts"] == _iso(t - 60)
    assert rows[1]["verdict"]["direction"] == "LONG"


def test_cocokkan_menolak_di_luar_jendela_dan_verdict_ditolak() -> None:
    t = 1793347200.0
    outcomes = [
        _out(t - 7 * 3600, "INJUSDT", "SHORT"),  # di luar 6 jam
        _out(t - 60, "INJUSDT", "SHORT", allowed=False),
    ]
    assert cocokkan([{"id": 1, "t": int(t), "subject": "sinyal/INJUSDT/SHORT"}], outcomes) == []


def test_ringkas_menghitung_expectancy_dan_tier() -> None:
    rows = [
        {"hasil": "tp1", "r": 1.0, "tier": "PREMIUM", "hasil_cache": "tp1"},
        {"hasil": "sl", "r": -1.0, "tier": "PREMIUM", "hasil_cache": "sl"},
        {"hasil": "tp1", "r": 1.0, "tier": "STANDAR", "hasil_cache": "tidak_terisi"},
        {"hasil": "tidak_terisi", "r": 0.0, "tier": "STANDAR", "hasil_cache": "tidak_terisi"},
        {"hasil": "terbuka", "r": 0.2, "tier": "PREMIUM", "hasil_cache": "terbuka"},
    ]
    r = ringkas(rows)
    assert r["n_terkirim"] == 5
    assert r["n_terisi"] == 4
    assert (r["tp1"], r["sl"]) == (2, 1)
    assert r["winrate"] == 50.0
    assert r["total_r"] == 1.2
    assert r["expectancy_r"] == 0.3
    assert r["expectancy_0r"] == 0.24
    assert r["kategori"]["tidak_terisi"] == 1
    assert r["per_tier"]["PREMIUM"]["n_terisi"] == 3
    assert r["per_tier"]["STANDAR"]["winrate"] == 100.0
    assert r["sama_cache"] == 4 and r["beda_cache"] == 1
