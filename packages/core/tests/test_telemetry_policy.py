"""Tes is_retired + wildcard (fakta legitim tak boleh tampil sebagai basi).

Latar: 29 fakta basi tampil di beranda padahal sebagian besar legitim tua
(pair crypto historis, brief AI yang job-nya disabled). is_retired kini
mendukung wildcard '*' di key. Sensor nyata TIDAK boleh ikut tertutup.
"""
from __future__ import annotations

import pytest

from warroom_core.telemetry_policy import is_retired, retired_pairs


@pytest.fixture(autouse=True)
def _polaka_default(monkeypatch):
    """Pakai default (mt5_snapshot + signal:*USDT + ai.brief:*), tanpa override env."""
    monkeypatch.delenv("WARROOM_RETIRED_FACTS", raising=False)


def test_pair_crypto_usdt_retired():
    # Pair crypto historis: liveness crypto kini dari job collect, bukan per-pair.
    assert is_retired("signal", "BTCUSDT")
    assert is_retired("signal", "1000PEPEUSDT")
    assert is_retired("signal", "APTUSDT")


def test_brief_ai_semua_key_retired():
    # Job llm-brief-* sengaja disabled pemilik -> semua key ai.brief legitim tua.
    for key in ("crypto", "forex", "idx", "gmgn", "polymarket"):
        assert is_retired("ai.brief", key)


def test_sensor_nyata_tidak_retired():
    # Sensor XAUUSD bukan pair *USDT -> tetap terlihat bila basi (masalah nyata).
    assert not is_retired("signal", "XAUUSD_TENCENT_SENSOR")


def test_snapshot_dan_prompt_registry_tidak_retired():
    assert not is_retired("snapshot", "pod_llm")
    assert not is_retired("ai.prompt_registry", "registry")


def test_mt5_snapshot_lama_tetap_retired():
    # Perilaku lama (default pemilik 1 Nov) tidak boleh hilang.
    assert is_retired("mt5_snapshot", "ringkas")


def test_wildcard_prefix_juga_bekerja():
    # '*' di akhir = prefix match (signal:BTC* -> BTCUSDT, BTCUSDC, dst).
    monkey = pytest.MonkeyPatch()
    monkey.setenv("WARROOM_RETIRED_FACTS", "signal:BTC*")
    try:
        assert is_retired("signal", "BTCUSDT")
        assert not is_retired("signal", "ETHUSDT")
    finally:
        monkey.undo()


def test_tanpa_wildcard_cocok_persis():
    monkey = pytest.MonkeyPatch()
    monkey.setenv("WARROOM_RETIRED_FACTS", "signal:XAUUSD_TENCENT_SENSOR")
    try:
        assert is_retired("signal", "XAUUSD_TENCENT_SENSOR")
        assert not is_retired("signal", "XAUUSD_TENCENT_SENSOR_LAIN")
    finally:
        monkey.undo()


def test_env_override_menimpa_default():
    monkey = pytest.MonkeyPatch()
    monkey.setenv("WARROOM_RETIRED_FACTS", "foo:bar")
    try:
        # default tidak berlaku saat env diset eksplisit
        assert not is_retired("signal", "BTCUSDT")
        assert is_retired("foo", "bar")
    finally:
        monkey.undo()


def test_retired_pairs_mengembalikan_frozenset():
    assert isinstance(retired_pairs(), frozenset)
