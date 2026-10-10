from datetime import UTC, datetime

import pytest
from warroom_core.adapters import Adapter, normalize_market_data
from warroom_core.signal import MarketData


def test_normalize_market_data_sets_common_shape_and_freshness():
    now = datetime.now(UTC)
    data = normalize_market_data(
        market="crypto", venue="okx", instrument="BTCUSDT",
        observed_at=now, price=100.0, spread_bps=2.0, liquidity_usd=1000,
        payload={"source": "test"},
    )
    assert isinstance(data, MarketData)
    assert data.market == "crypto"
    assert data.payload["source"] == "test"


def test_normalize_market_data_rejects_naive_timestamp_and_bad_price():
    with pytest.raises(ValueError):
        normalize_market_data("crypto", "okx", "BTCUSDT", datetime.now(), 100, None, None, {})
    with pytest.raises(ValueError):
        normalize_market_data("crypto", "okx", "BTCUSDT", datetime.now(UTC), 0, None, None, {})


def test_adapter_protocol_is_small_and_explicit():
    assert set(Adapter.__abstractmethods__) == {"fetch"}
