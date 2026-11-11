"""Test OpenMarketProvider: parsing coin/lookback/candle (mock) + live (skip jika tak ada key)."""
import json
import os
import urllib.request

import pytest
from warroom_core.strategi_config.provider import OpenMarketProvider, provider_untuk


def test_coin_parsing():
    p = OpenMarketProvider.__new__(OpenMarketProvider)  # tanpa __init__ (tak butuh key)
    assert p._coin("BTC") == "BTC"
    assert p._coin("BTCUSDT") == "BTC"
    assert p._coin("BTC-USDT") == "BTC"
    assert p._coin("eth-usdt") == "ETH"
    assert p._coin("PEPEUSDT") == "PEPE"


def test_lookback():
    p = OpenMarketProvider.__new__(OpenMarketProvider)
    # < 1440 menit pakai menit, >= 1440 pakai hari
    assert p._lookback("1m", 100) == "100m"       # 1*100=100m
    assert p._lookback("1h", 10) == "600m"        # 60*10=600m
    assert p._lookback("1h", 300) == "12d"        # 60*300=18000m -> 12d
    assert p._lookback("1d", 10) == "10d"         # 1440*10=14400m -> 10d


def test_interval_map():
    assert OpenMarketProvider.INTERVAL["1h"] == "HOUR"
    assert OpenMarketProvider.INTERVAL["1d"] == "DAY"
    assert OpenMarketProvider.INTERVAL["5m"] == "FIVE_MINUTES"


def test_provider_untuk_openmarket(monkeypatch):
    monkeypatch.setenv("OPENMARKET_API_KEY", "dummy")
    prov = provider_untuk("openmarket")
    assert isinstance(prov, OpenMarketProvider)


def test_no_key_raises(monkeypatch):
    monkeypatch.delenv("OPENMARKET_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenMarketProvider()


def test_candle_parsing(monkeypatch):
    """Parsing rows -> Candle dict, pakai mock respons (format terverifikasi via MCP)."""
    monkeypatch.setenv("OPENMARKET_API_KEY", "dummy")
    p = OpenMarketProvider()

    fake = {
        "series": [{
            "columns": ["t", "open", "high", "low", "close", "volume"],
            "rows": [
                ["2026-11-04T11:00:00Z", 78608.86, 78718, 78466.14, 78477.25, 420.49],
                ["2026-11-11T09:00:00Z", 73728.22, 73877.94, 73621.54, 73621.55, 145.19],
            ],
        }]
    }

    def fake_urlopen(req, timeout=20):
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(fake).encode()
        return R()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    candles = p.candles("BTC", "1h", limit=10)
    assert len(candles) == 2
    assert candles[0]["open"] == 78608.86
    assert candles[0]["close"] == 78477.25
    assert candles[-1]["volume"] == 145.19
    assert isinstance(candles[0]["time"], float)
    assert candles[0]["time"] > 1_700_000_000  # epoch masuk akal


@pytest.mark.skipif(not os.environ.get("OPENMARKET_API_KEY"), reason="butuh OPENMARKET_API_KEY")
def test_live_btc():
    p = OpenMarketProvider()
    candles = p.candles("BTC", "1h", limit=50)
    assert len(candles) > 0
    assert set(candles[0]) >= {"time", "open", "high", "low", "close", "volume"}
