"""Test strategi Fase 3: market: openmarket memuat & provider resolve."""
from pathlib import Path

import pytest
from warroom_core.strategi_config.config import muat_config
from warroom_core.strategi_config.provider import OpenMarketProvider, provider_untuk

ROOT = Path(__file__).resolve().parents[3]
YAML = ROOT / "strategi" / "openmarket_breakout.yaml"


def test_yaml_ada():
    assert YAML.exists(), f"strategi openmarket hilang: {YAML}"


def test_muat_config_openmarket():
    cfg = muat_config(YAML)
    assert cfg.id == "openmarket_breakout"
    assert cfg.market == "openmarket"
    assert cfg.waktu == "1h"
    assert cfg.simbol == ["BTC", "ETH", "SOL", "BNB", "XRP"]
    # formula tervalidasi saat muat_config (fail-closed) -> cukup lolos berarti OK
    assert "ema_tren" in cfg.variabel


def test_provider_untuk_openmarket(monkeypatch):
    monkeypatch.setenv("OPENMARKET_API_KEY", "dummy")
    prov = provider_untuk("openmarket")
    assert isinstance(prov, OpenMarketProvider)


def test_market_tak_dikenal_fail_closed():
    with pytest.raises(ValueError):
        provider_untuk("saham_nyasar")
