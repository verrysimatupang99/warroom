"""6-agent — tiap agent mem-vote jujur, gagal = bias None, confluence dicatat.

 Yang diuji: pemetaan ambang (hipotesis), ketahanan terhadap API mati, dan
 penerusan field agents sampai ke hasil measure (atribusi per-agent).
"""

from __future__ import annotations

import httpx

from live_trading import measure
from live_trading.config import get_settings
from live_trading.signals import agents as ag


def _klines(n=20, px=100.0):
    return [[i * 3600000, str(px), str(px + 1), str(px - 1), str(px), "10"] for i in range(n)]


def _oi(n=25, awal=100.0, akhir=115.0):
    return [{"sumOpenInterest": str(awal + (akhir - awal) * i / (n - 1))} for i in range(n)]


def _handler(request):
    url = str(request.url)
    if "takerlongshortRatio" in url:
        return httpx.Response(200, json=[{"buySellRatio": "1.2"}])
    if "topLongShortAccountRatio" in url:
        return httpx.Response(200, json=[{"longShortRatio": "2.0"}])
    if "fundingRate" in url:
        return httpx.Response(200, json=[{"fundingRate": "0.0001"}])
    if "openInterestHist" in url:
        return httpx.Response(200, json=_oi())
    if "fng" in url:
        return httpx.Response(200, json={"data": [{"value": "80", "value_classification": "Extreme Greed"}]})
    if "klines" in url:
        return httpx.Response(200, json=_klines())
    if "ticker/24hr" in url:
        return httpx.Response(200, json={"priceChangePercent": "4.0"})
    return httpx.Response(404)


def _client(handler=_handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_confluence_dan_vote():
    s = get_settings()
    out = ag.collect(s, "BTCUSDT", _client())
    a = out["agents"]
    # orderflow: taker panas (+0.5) vs crowd long 66.7% (-0.5) = 0.0
    assert a["orderflow"]["bias"] == 0.0
    # whale: OI +15% = uang baru masuk
    assert a["whale"]["bias"] == 0.5
    # sentiment: rakus 80 = hati-hati long
    assert a["sentiment"]["bias"] == -0.5
    # risk: tidak mem-vote arah, tapi datanya ada
    assert a["risk"]["bias"] is None
    assert a["risk"]["data"]["atr_pct_1h"] is not None
    # macro: BTC +4% = risk-on
    assert a["macro"]["bias"] == 0.5
    assert out["n_voting"] == 4
    assert out["confluence"] == 0.12  # (0 + .5 - .5 + .5) / 4


def test_api_mati_semua_bias_none():
    s = get_settings()
    out = ag.collect(s, "BTCUSDT", _client(lambda r: httpx.Response(500)))
    assert all(a["bias"] is None for a in out["agents"].values())
    assert out["confluence"] is None
    assert out["n_voting"] == 0


def test_agents_terus_ke_hasil_measure():
    row = {
        "ts": "2026-09-29T00:00:00+00:00",
        "pair": "BTCUSDT",
        "direction": "long",
        "allowed": True,
        "entry": 100.0,
        "sl": 99.0,
        "tp1": 101.0,
        "agents": {"pair": "BTCUSDT", "confluence": 0.5, "n_voting": 2},
    }
    kl = [[i * 3600000, "100", "101", "99", "100.5", "10"] for i in range(12)]
    hasil = measure.resolve_one(row, kl)
    assert hasil["agents"] == {"pair": "BTCUSDT", "confluence": 0.5, "n_voting": 2}
