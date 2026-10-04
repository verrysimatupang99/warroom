"""Kolektor DEX Screener: cache offline + chain map (tanpa jaringan)."""

import time

from live_trading.collectors import dexscreen


def test_cache_simpan_dan_baca(tmp_path) -> None:
    dexscreen.save_cache(tmp_path, {"boosts": [{"symbol": "X"}], "enrich": {}})
    d = dexscreen.load_cache(tmp_path)
    assert d is not None and d["boosts"][0]["symbol"] == "X"


def test_cache_basi_diabaikan(tmp_path) -> None:
    import json

    p = dexscreen._cache_file(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ts": time.time() - 99999, "boosts": []}), encoding="utf-8")
    assert dexscreen.load_cache(tmp_path) is None


def test_chain_map() -> None:
    assert dexscreen.CHAIN_MAP["sol"] == "solana"
    assert "arc" not in dexscreen.CHAIN_MAP  # jujur: tak didukung = skip


def test_radar_tabs_dex_boost() -> None:
    from live_trading import dashboard

    dex = {"boosts": [{"symbol": "0xabc", "chain": "solana", "url": "https://x", "description": "d"}],
           "enrich": {"sol:0xabc": {"bs_m5": 4.5}}}
    shadow = [{"key": "sol:0xabc", "symbol": "T", "cluster_wallets": 3,
               "cluster_buy_usd": 500, "ret_5m_pct": 2.0, "shadow_pct": 1.0}]
    html_out = dashboard._radar_tabs(shadow, [], dex)
    assert "DEX Boost" in html_out
    assert "4.5x" in html_out


def test_radar_tabs_narrative() -> None:
    from live_trading import dashboard

    dex = {"metas": {"metas": [
        {"name": "Dog", "slug": "dog", "marketCap": 1306837940,
         "volume": 207711967, "chg_h24": 2.29, "chg_h1": -0.45,
         "overlap": 2, "overlap_hit": ["0xabc"]},
    ]}}
    html_out = dashboard._radar_tabs([], [], dex)
    assert "Narrative" in html_out
    assert "Dog" in html_out
    assert "irisan sinyal" in html_out
