"""Tes konfigurasi provider (bentuk blueprint)."""

from __future__ import annotations

from pathlib import Path

import pytest
from warroom_llm.config import LLMConfig, default_config


def test_default_config_rantai_primary_dulu() -> None:
    cfg = default_config()
    nama = [p.name for p in cfg.chain()]
    assert nama == ["nutaraline", "qonek"]
    assert cfg.primary == "nutaraline"
    assert cfg.timeout_ms == 45000
    assert cfg.retry_attempts == 2
    assert cfg.circuit_failures == 5
    assert cfg.cache_ttl_sec == 900
    assert cfg.budget_daily_usd == 3.0


def test_provider_model_dan_key_env() -> None:
    cfg = default_config()
    assert cfg.provider("nutaraline").base_url == "https://nutaraline.co.uk/v1"
    assert cfg.provider("nutaraline").key_env == "HERMES_CUSTOM_NUTARALINE_CO_UK_API_KEY"
    assert cfg.model_for("qonek", "fast") == "qonek/deepseek-v4.1-flash"
    assert "QONEK_API_KEY" in cfg.key_envs()


def test_model_tier_tidak_ada_jatuh_ke_fast() -> None:
    cfg = LLMConfig.from_dict(
        {
            "primary": "a",
            "providers": [{"name": "a", "baseUrl": "http://x", "keyEnv": "K", "models": {"fast": "m"}}],
        }
    )
    assert cfg.model_for("a", "deep") == "m"


def test_from_dict_membaca_nested() -> None:
    cfg = LLMConfig.from_dict(
        {
            "primary": "p",
            "retry": {"attempts": 3, "backoffMs": 100},
            "circuit": {"failures": 4, "windowSec": 60, "cooldownSec": 120},
            "cache": {"ttlSec": 30, "maxEntries": 5},
            "budget": {"dailyUsd": 1.5, "perRoleDailyUsd": {"narrator": 0.5}},
            "providers": [{"name": "p", "baseUrl": "http://p/", "keyEnv": "P_KEY", "models": {"fast": "m"}}],
        }
    )
    assert cfg.retry_attempts == 3
    assert cfg.circuit_window_sec == 60
    assert cfg.cache_max_entries == 5
    assert cfg.budget_per_role == {"narrator": 0.5}
    assert cfg.provider("p").base_url == "http://p"  # slash akhir dipangkas


def test_load_berkas_tidak_ada_tanpa_kredensial(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        LLMConfig.load(tmp_path / "tidak-ada.json")
    pesan = str(exc.value)
    assert "tidak ada kredensial" in pesan
    assert "://" not in pesan


def test_load_dari_berkas(tmp_path: Path) -> None:
    p = tmp_path / "llm.json"
    p.write_text(
        '{"primary":"x","providers":[{"name":"x","baseUrl":"http://x","keyEnv":"X_KEY","models":{"fast":"m"}}]}',
        encoding="utf-8",
    )
    cfg = LLMConfig.load(p)
    assert cfg.primary == "x"
