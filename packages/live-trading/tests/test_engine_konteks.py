"""Integrasi konteks pasar ke jalur evaluasi engine — heat + filter funding/OI.

Yang dikunci:
1. Tanpa konteks (jalur scan), filter TIDAK dievaluasi: ok=None + alasan, keputusan
   tidak berubah, dan assessment tetap 6 aturan lama.
2. Dengan konteks, filter menjadi aturan keras: penolakan -> allowed=False + tier SKIP.
3. Baris verdict mencatat heat & filter apa adanya, termasuk saat ok=None.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from live_trading.config import get_settings
from live_trading.signals import engine, gates, heat


def _candle(o: float, hi: float, lo: float, c: float, i: int) -> list[Any]:
    return [i, str(o), str(hi), str(lo), str(c), "10", 0, "0", 0, "5", "0", "0"]


def _series(start: float, step: float, n: int = 200, tiap: int = 10) -> list[list[Any]]:
    out: list[list[Any]] = []
    px = start
    for i in range(n):
        px += step
        if i % tiap == tiap - 1:
            o, c = px, px - step * 3
            out.append(_candle(o, o + step, c - step, c, i))
        else:
            o, c = px - step, px + step / 2
            out.append(_candle(o, c + step, o - step, c, i))
    return out


def _client() -> httpx.Client:
    h1, h4, d1 = _series(100, 0.5), _series(90, 1.0), _series(80, 2.0)

    def handler(request: httpx.Request) -> httpx.Response:
        interval = request.url.params.get("interval")
        return httpx.Response(200, json={"1h": h1, "4h": h4}.get(interval, d1))

    return httpx.Client(transport=httpx.MockTransport(handler))


def _assessment(allowed: bool = True, tier: str = "STANDAR") -> gates.Assessment:
    return gates.Assessment(
        allowed=allowed,
        tier=tier,
        verdicts=tuple(
            gates.Verdict(rule=r, ok=True, reason="ok")
            for r in ("mtf_alignment", "poi_valid", "freshness", "sl_distance", "atr_min", "exposure")
        ),
    )


def test_gabung_filter_menolak_menjadi_skip() -> None:
    hasil = heat.HasilFilter(strategi="legacy-smc", ok=False, alasan="funding ekstrem searah")
    out = engine._gabung_filter(_assessment(), hasil)
    assert out.allowed is False
    assert out.tier == "SKIP"
    terakhir = out.verdicts[-1]
    assert terakhir.rule == "filter_funding_oi"
    assert terakhir.ok is False and terakhir.hard is True
    assert terakhir.reason == "funding ekstrem searah"


def test_gabung_filter_lolos_tidak_mengubah_tier() -> None:
    hasil = heat.HasilFilter(strategi="legacy-smc", ok=True, alasan="aman")
    out = engine._gabung_filter(_assessment(allowed=True, tier="PREMIUM"), hasil)
    assert out.allowed is True and out.tier == "PREMIUM"
    terakhir = out.verdicts[-1]
    assert terakhir.ok is True and terakhir.hard is False


def test_gabung_filter_n_a_tidak_menyentuh_assessment() -> None:
    awal = _assessment()
    hasil = heat.HasilFilter(strategi="legacy-smc", ok=None, alasan="n/a")
    assert engine._gabung_filter(awal, hasil) is awal


def test_evaluate_tanpa_konteks_tidak_mengubah_keputusan(tmp_path) -> None:
    s = get_settings(home=tmp_path)
    with _client() as client:
        _st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client)
    assert prop is not None
    assert {v.rule for v in hasil.verdicts} == {
        "mtf_alignment", "poi_valid", "freshness", "sl_distance", "atr_min", "exposure",
    }, "tanpa konteks, jangan menambah aturan yang tidak dievaluasi"
    f = prop["filter_funding_oi"]
    assert f["ok"] is None
    assert "tidak diambil" in f["alasan"]
    assert prop["heat"] is None

    baris = json.loads((s.state_dir / "verdicts.jsonl").read_text(encoding="utf-8").strip())
    assert baris["filter_funding_oi"]["ok"] is None
    assert "heat" not in baris, "tanpa konteks tidak ada angka heat yang boleh muncul"


def test_evaluate_dengan_konteks_menolak_dan_mencatat(tmp_path) -> None:
    s = get_settings(home=tmp_path)
    konteks = {"funding_pct": 0.09, "oi_delta_pct": 5.0, "volume_24j_usd_m": 900.0}
    with _client() as client:
        _st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client, konteks=konteks)

    assert prop is not None
    f = prop["filter_funding_oi"]
    assert f["ok"] is False
    assert hasil.allowed is False
    assert hasil.tier == "SKIP"
    aturan = [v for v in hasil.verdicts if v.rule == "filter_funding_oi"]
    assert len(aturan) == 1 and aturan[0].ok is False

    baris = json.loads((s.state_dir / "verdicts.jsonl").read_text(encoding="utf-8").strip())
    assert baris["allowed"] is False
    assert baris["filter_funding_oi"]["ok"] is False
    assert baris["heat"]["skor"] is not None, "konteks cukup untuk heat -> skor angka"
    assert baris["heat"]["cakupan"] > 0


def test_evaluate_konteks_dari_agents(tmp_path) -> None:
    """Jalur `lt smc --agents`: konteks diturunkan dari keluaran agents.collect."""
    s = get_settings(home=tmp_path)
    agents = {
        "pair": "TESTUSDT",
        "agents": {
            "orderflow": {"data": {"funding_pct": 0.002, "taker_ratio": 1.2}},
            "whale": {"data": {"oi_delta_24h_pct": 3.0}},
        },
    }
    with _client() as client:
        _st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client, agents=agents)
    assert prop is not None
    f = prop["filter_funding_oi"]
    assert f["ok"] is True, "funding 0,002% & OI +3% tidak boleh menolak"
    st_aturan = [v for v in hasil.verdicts if v.rule == "filter_funding_oi"]
    assert len(st_aturan) == 1 and st_aturan[0].ok is True

    baris = json.loads((s.state_dir / "verdicts.jsonl").read_text(encoding="utf-8").strip())
    assert baris["filter_funding_oi"]["ok"] is True
    assert baris["heat"]["skor"] is not None
    # agents tetap diteruskan apa adanya untuk atribusi measure
    assert baris["agents"] == agents


def test_evaluate_konteks_tak_terbaca_tetap_n_a(tmp_path) -> None:
    """Data ada tapi kosong (sumber gagal) -> ok None + alasan jujur, bukan 'lolos'."""
    s = get_settings(home=tmp_path)
    agents = {"agents": {"orderflow": {"data": {}}, "whale": {"data": {}}}}
    with _client() as client:
        _st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client, agents=agents)
    assert prop is not None
    f = prop["filter_funding_oi"]
    assert f["ok"] is None
    assert "tidak terbaca" in f["alasan"]
    assert not [v for v in hasil.verdicts if v.rule == "filter_funding_oi"]


def test_filter_tidak_menolak_konteks_normal(tmp_path) -> None:
    s = get_settings(home=tmp_path)
    konteks = {"funding_pct": -0.01, "oi_delta_pct": 1.0}
    with _client() as client:
        _st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client, konteks=konteks)
    assert prop is not None
    assert prop["filter_funding_oi"]["ok"] is True
    assert "filter_funding_oi" in {v.rule for v in hasil.verdicts}
