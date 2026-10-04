"""Kontrak kolektor — diuji tanpa jaringan (httpx.MockTransport)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from live_trading.collectors.crypto import CryptoCollector, taker_ratio
from live_trading.collectors.forex import ForexCollector, atr, ema
from live_trading.collectors.idx import ArjumCollector, QuotaExhausted
from live_trading.config import get_settings


# --------------------------------------------------------------------- murni
def test_taker_ratio_mengukur_agresi() -> None:
    """Kolom 9 (taker buy) dibanding kolom 5 (volume) — dikali 2 jadi rasio 1.0 = seimbang."""
    seimbang = [[0, 0, 0, 0, 0, "100", 0, 0, 0, "50"]]
    beli_kuat = [[0, 0, 0, 0, 0, "100", 0, 0, 0, "90"]]

    assert taker_ratio(seimbang) == 1.0
    assert taker_ratio(beli_kuat) == 1.8


def test_taker_ratio_data_kosong_bukan_angka_palsu() -> None:
    assert taker_ratio([]) is None
    assert taker_ratio([[0, 0, 0, 0, 0, "0", 0, 0, 0, "0"]]) is None


def test_ema_butuh_data_cukup() -> None:
    """Data kurang -> None, jangan menebak."""
    assert ema([1.0, 2.0], 5) is None
    assert ema([1.0] * 10, 5) == pytest.approx(1.0)


def test_atr_memasukkan_gap_dari_close_sebelumnya() -> None:
    """TR = max(range, |high-prevClose|, |low-prevClose|) — bukan cuma range bar itu."""
    highs = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5]

    # tiap bar: range 1.0, tapi high 1.5 di atas close sebelumnya -> TR 1.5
    assert atr(highs, lows, closes, period=3) == pytest.approx(1.5)
    assert atr([1.0], [0.0], [0.5], period=3) is None


# ----------------------------------------------------------------- IDX/Arjum
def _idx_collector(tmp_path: Path, handler) -> ArjumCollector:
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    s.arjum_key_path.write_text("sk_test_key", encoding="utf-8")
    return ArjumCollector(s, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_idx_cache_menghindari_panggilan_kedua(tmp_path: Path) -> None:
    """Cache TTL harus menghemat kuota: panggilan kedua tidak menyentuh jaringan."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json={"rows": [{"stock_code": "BBRI"}]},
            headers={"x-ratelimit-remaining": "5900", "x-ratelimit-limit": "6000"},
        )

    c = _idx_collector(tmp_path, handler)
    first = c.screener(limit=5)
    second = c.screener(limit=5)

    assert calls["n"] == 1, "panggilan kedua harus dari cache"
    assert first == second == {"rows": [{"stock_code": "BBRI"}]}


def test_idx_mencatat_sisa_kuota_dari_header(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"x-ratelimit-remaining": "4231"})

    c = _idx_collector(tmp_path, handler)
    c.health()

    assert c.quota()["remaining"] == 4231


def test_idx_berhenti_sebelum_kuota_habis(tmp_path: Path) -> None:
    """Guard harus mencegah request, bukan sekadar melaporkan setelah gagal."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={})

    c = _idx_collector(tmp_path, handler)
    c.settings.state_dir.mkdir(parents=True, exist_ok=True)
    c.quota_path.write_text(json.dumps({"remaining": 10, "limit": 6000}), encoding="utf-8")
    c.settings.arjum_min_remaining = 500

    with pytest.raises(QuotaExhausted):
        c.health()

    assert calls["n"] == 0, "tidak boleh ada request saat kuota di bawah ambang"


def test_idx_tanpa_key_gagal_jelas(tmp_path: Path) -> None:
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    c = ArjumCollector(s, client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))

    with pytest.raises(RuntimeError, match="API key"):
        c.health()


# --------------------------------------------------------------------- crypto
def test_crypto_snapshot_mengurai_endpoint_binance(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/premiumIndex"):
            return httpx.Response(200, json={"lastFundingRate": "0.0001"})
        if path.endswith("/openInterest"):
            return httpx.Response(200, json={"openInterest": "1234.5"})
        if path.endswith("/ticker/24hr"):
            return httpx.Response(
                200, json={"lastPrice": "84900.5", "priceChangePercent": "1.25", "quoteVolume": "5000000"}
            )
        if path.endswith("/klines"):
            return httpx.Response(200, json=[[0, 0, 0, 0, 0, "100", 0, 0, 0, "50"]])
        return httpx.Response(404, json={})

    s = get_settings(home=tmp_path)
    c = CryptoCollector(s, client=httpx.Client(transport=httpx.MockTransport(handler)))
    snap = c.pair_snapshot("BTCUSDT")

    assert snap["funding"] == pytest.approx(0.01)  # 0.0001 -> persen
    assert snap["oi"] == 1234.5
    assert snap["price"] == 84900.5
    assert snap["chg24h"] == 1.25
    assert snap["taker"] == 1.0
    assert snap["quote_vol"] == 5.0


def test_crypto_satu_pair_gagal_tidak_membunuh_sisanya(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "ETHUSDT" in str(request.url):
            return httpx.Response(500, json={})
        if request.url.path.endswith("/premiumIndex"):
            return httpx.Response(200, json={"lastFundingRate": "0"})
        if request.url.path.endswith("/openInterest"):
            return httpx.Response(200, json={"openInterest": "1"})
        if request.url.path.endswith("/ticker/24hr"):
            return httpx.Response(200, json={"lastPrice": "1", "priceChangePercent": "0", "quoteVolume": "0"})
        return httpx.Response(200, json=[[0, 0, 0, 0, 0, "1", 0, 0, 0, "1"]])

    s = get_settings(home=tmp_path)
    c = CryptoCollector(s, client=httpx.Client(transport=httpx.MockTransport(handler)))
    rows = c.digest(("BTCUSDT", "ETHUSDT"))

    assert len(rows) == 2
    assert "error" not in rows[0]
    assert rows[1]["error"] == "HTTPStatusError"


# ---------------------------------------------------------------------- forex
def test_forex_quote_menambahkan_symbol(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"close": 3800.5, "description": "Gold"})

    s = get_settings(home=tmp_path)
    c = ForexCollector(s, client=httpx.Client(transport=httpx.MockTransport(handler)))

    q = c.quote()

    assert q["symbol"] == "TVC:GOLD"
    assert q["close"] == 3800.5
