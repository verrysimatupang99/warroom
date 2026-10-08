from datetime import UTC

from warroom_core.signal import MarketData

from live_trading.adapters.crypto import CryptoAdapter


class StubCollector:
    def pair_snapshot(self, pair: str) -> dict[str, object]:
        assert pair == "BTCUSDT"
        return {"pair": pair, "price": 100.0, "funding": 0.01, "oi": 12.0}


def test_crypto_adapter_normalizes_collector_snapshot_without_inventing_liquidity():
    data = CryptoAdapter(StubCollector()).fetch("BTCUSDT")
    assert isinstance(data, MarketData)
    assert data.market == "crypto"
    assert data.venue == "binance-fapi"
    assert data.instrument == "BTCUSDT"
    assert data.price == 100.0
    assert data.spread_bps is None
    assert data.liquidity_usd is None
    assert data.observed_at.tzinfo == UTC
    assert data.payload["funding"] == 0.01
