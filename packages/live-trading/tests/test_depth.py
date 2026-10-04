"""Kedalaman buku order (L2) — pengukuran yang menentukan asumsi fill.

Konteks: uji maker menyimpulkan edge live-trading bersyarat pada biaya 0 bps DAN
kedalaman fill ≤5 bps. Yang kedua itu dulu diasumsikan dari candle; modul ini
mengukurnya dari buku nyata. Tes di sini menjaga agar pengukurannya benar — bukan
agar hasilnya bagus.
"""

from __future__ import annotations

import httpx
import pytest

from live_trading.collectors import depth
from live_trading.config import get_settings


def _book(bids, asks) -> dict:
    return {"bids": [[str(p), str(s)] for p, s in bids],
            "asks": [[str(p), str(s)] for p, s in asks]}


def test_parse_book_mengurut_harga_terbaik_dulu() -> None:
    bids, asks = depth.parse_book(_book(
        bids=[(99.0, 1.0), (100.0, 2.0), (98.0, 3.0)],
        asks=[(102.0, 1.0), (101.0, 2.0), (103.0, 3.0)],
    ))
    assert [b.price for b in bids] == [100.0, 99.0, 98.0]      # bid terbaik = tertinggi
    assert [a.price for a in asks] == [101.0, 102.0, 103.0]    # ask terbaik = terendah


def test_mid_dari_bid_dan_ask_terbaik() -> None:
    bids, asks = depth.parse_book(_book(bids=[(100.0, 1.0)], asks=[(102.0, 1.0)]))
    assert depth.mid_price(bids, asks) == 101.0


def test_mid_none_kalau_satu_sisi_kosong() -> None:
    bids, asks = depth.parse_book(_book(bids=[(100.0, 1.0)], asks=[]))
    assert depth.mid_price(bids, asks) is None


def test_depth_at_menghitung_bps_dan_kumulatif() -> None:
    # mid = 100; bid di 100 (0 bps), 99.9 (10 bps), 99.5 (50 bps)
    levels = [depth.BookLevel(100.0, 10.0), depth.BookLevel(99.9, 10.0), depth.BookLevel(99.5, 10.0)]
    out = depth.depth_at(levels, mid=100.0, max_bps=20.0)
    assert len(out) == 2, "level 50 bps harus di luar ambang 20"
    assert out[0]["bps"] == 0.0
    assert out[0]["notional_usd"] == 1000.0
    assert out[1]["bps"] == pytest.approx(10.0, abs=0.01)
    assert out[1]["cum_notional_usd"] == pytest.approx(1000.0 + 999.0, abs=1.0)


def test_depth_at_berhenti_di_ambang() -> None:
    levels = [depth.BookLevel(100.0, 1.0), depth.BookLevel(99.0, 1.0)]   # 0 dan ~100 bps
    out = depth.depth_at(levels, mid=100.0, max_bps=50.0)
    assert len(out) == 1, "level 100 bps di luar ambang 50"


def test_depth_report_dua_sisi() -> None:
    # mid = 100 → 20 bps = 0.2, jadi level harus di dalam [99.8, 100.2]
    r = depth.depth_report(_book(
        bids=[(99.95, 100.0), (99.90, 100.0)],
        asks=[(100.05, 100.0), (100.10, 100.0)],
    ), "TESTUSDT", max_bps=20.0)
    assert r["pair"] == "TESTUSDT"
    assert r["mid"] == 100.0
    assert r["bid"]["best"] == 99.95
    assert r["ask"]["best"] == 100.05
    assert r["bid"]["total_notional_usd"] > 0
    assert r["ask"]["total_notional_usd"] > 0
    # ~5 bps dan ~10 bps harus masuk
    assert len(r["bid"]["levels"]) == 2


def test_depth_report_level_di_luar_ambang_dibuang() -> None:
    """Level yang jauh dari mid tidak boleh masuk — kalau masuk, angkanya menyesatkan."""
    r = depth.depth_report(_book(
        bids=[(99.95, 100.0), (99.0, 100.0)],      # 5 bps dan 100 bps
        asks=[(100.05, 100.0)],
    ), "TESTUSDT", max_bps=20.0)
    assert len(r["bid"]["levels"]) == 1, "level 100 bps harus dibuang"


def test_depth_report_buku_kosong_bukan_angka_palsu() -> None:
    """Buku kosong harus error eksplisit, bukan mid=0 yang terlihat seperti data."""
    r = depth.depth_report(_book(bids=[], asks=[]), "XUSDT")
    assert "error" in r
    assert "mid" not in r


def test_notional_at_bps_memilih_level_terdalam_yang_muat() -> None:
    report = {"bid": {"levels": [
        {"bps": 1.0, "cum_notional_usd": 100.0},
        {"bps": 5.0, "cum_notional_usd": 500.0},
        {"bps": 10.0, "cum_notional_usd": 900.0},
    ]}}
    assert depth.notional_at_bps(report, "bid", 0.5) == 0.0
    assert depth.notional_at_bps(report, "bid", 1.0) == 100.0
    assert depth.notional_at_bps(report, "bid", 7.0) == 500.0
    assert depth.notional_at_bps(report, "bid", 100.0) == 900.0


def test_notional_at_bps_sisi_hilang_bukan_error() -> None:
    assert depth.notional_at_bps({}, "bid", 5.0) == 0.0


def test_collector_menolak_http_error_dengan_pesan() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"msg": "boom"})

    c = depth.DepthCollector(get_settings(),
                             client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = c.report("FAILUSDT")
    assert "error" in r
    assert "FAILUSDT" in r["pair"]


def test_collector_parsing_payload_nyata() -> None:
    payload = {"lastUpdateId": 1, "bids": [["99.5", "2"], ["99.0", "4"]],
               "asks": [["100.5", "2"], ["101.0", "4"]]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert "depth" in str(request.url)
        return httpx.Response(200, json=payload)

    c = depth.DepthCollector(get_settings(),
                             client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = c.report("OKUSDT", limit=5, max_bps=100.0)
    assert r["pair"] == "OKUSDT"
    assert r["mid"] == 100.0
    # sisi bid: 99.5 (~50 bps) dan 99.0 (~100 bps)
    assert depth.notional_at_bps(r, "bid", 60.0) > 0
