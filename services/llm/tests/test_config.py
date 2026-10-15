"""Tes konfigurasi provider (bentuk blueprint)."""

from __future__ import annotations

from pathlib import Path

import pytest
from warroom_llm.config import LLMConfig, default_config


def test_default_config_bentuk_baku_saat_berkas_tak_ada(tmp_path: Path, monkeypatch) -> None:
    """Berkas root tidak ada → bentuk baku (qonek → kiyara → nutaraline) tetap dipakai."""
    monkeypatch.setenv("WARROOM_LLM_CONFIG", str(tmp_path / "tidak-ada.json"))
    cfg = default_config()
    nama = [p.name for p in cfg.chain()]
    assert nama == ["qonek", "kiyara", "nutaraline"]
    assert cfg.primary == "qonek"
    assert cfg.timeout_ms == 45000
    assert cfg.retry_attempts == 2
    assert cfg.circuit_failures == 5
    assert cfg.cache_ttl_sec == 900
    assert cfg.budget_daily_usd == 3.0


def test_default_config_pricing_menutup_seluruh_rantai(tmp_path: Path, monkeypatch) -> None:
    """Anggaran fail-closed: setiap provider di rantai wajib punya entri harga.

    Provider tanpa harga membuat anggaran harian tak terhitung — gagal-tertutup akan
    memblokir SEMUA panggilan. Bentuk baku harus siap jalan tanpa blokir demikian.
    """
    monkeypatch.setenv("WARROOM_LLM_CONFIG", str(tmp_path / "tidak-ada.json"))
    cfg = default_config()
    tanpa_harga = [p.name for p in cfg.chain() if p.name not in cfg.pricing]
    assert tanpa_harga == []
    for harga in cfg.pricing.values():
        assert "in" in harga and "out" in harga


def test_default_config_memakai_berkas_root_bila_ada(tmp_path: Path, monkeypatch) -> None:
    """Berkas root ADALAH sumber kebenaran — rantai harus mengikuti isinya.

    Regresi produksi: `default_config()` dulu mengabaikan berkas dan selalu mengembalikan
    bentuk baku, sehingga mengubah `/etc/warroom/llm.json` tidak berpengaruh apa pun pada
    gateway yang benar-benar berjalan (urutan provider yang diminta owner tak pernah aktif).
    """
    p = tmp_path / "llm.json"
    p.write_text(
        '{"primary":"kiyara","providers":['
        '{"name":"kiyara","baseUrl":"https://kiyararouter.web.id/v1","keyEnv":"K_KEY",'
        '"models":{"fast":"m"}},'
        '{"name":"qonek","baseUrl":"https://qonek.web.id/v1","keyEnv":"Q_KEY","models":{"fast":"q"}},'
        '{"name":"nutaraline","baseUrl":"https://nutaraline.co.uk/v1","keyEnv":"N_KEY",'
        '"models":{"fast":"n"}}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("WARROOM_LLM_CONFIG", str(p))
    cfg = default_config()
    assert [x.name for x in cfg.chain()] == ["kiyara", "qonek", "nutaraline"]
    assert cfg.primary == "kiyara"


def test_provider_model_dan_key_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WARROOM_LLM_CONFIG", str(tmp_path / "tidak-ada.json"))
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
