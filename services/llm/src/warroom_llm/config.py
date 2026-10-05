"""Konfigurasi gateway LLM (``/etc/warroom/llm.json``, pola ``/etc/poly-pilot/agent-llm.json``).

Berkas ini root-only dan **tidak pernah** masuk repo/log/percakapan. Yang dicatat hanya
nama env var pembawa kunci (``keyEnv``), bukan nilainya.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_CONFIG_PATH", "ENV_CONFIG_PATH", "LLMConfig", "ProviderSpec", "default_config"]

ENV_CONFIG_PATH = "WARROOM_LLM_CONFIG"
DEFAULT_CONFIG_PATH = Path("/etc/warroom/llm.json")


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str
    key_env: str
    models: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMConfig:
    primary: str
    timeout_ms: int = 45000
    retry_attempts: int = 2
    retry_backoff_ms: int = 800
    circuit_failures: int = 5
    circuit_window_sec: int = 120
    circuit_cooldown_sec: int = 300
    cache_ttl_sec: int = 900
    cache_max_entries: int = 2000
    budget_daily_usd: float = 3.0
    budget_per_role: dict[str, float] = field(default_factory=dict)
    providers: tuple[ProviderSpec, ...] = ()
    # provider -> {"in": usd/1k token, "out": usd/1k token}; kosong = biaya tidak dihitung.
    pricing: dict[str, dict[str, float]] = field(default_factory=dict)
    # Gagal-tertutup: bila provider di rantai tidak punya entri `pricing` dan anggaran
    # harian > 0, anggaran TIDAK bisa dihitung — blokir, jangan anggap biaya nol.
    # Bisa dimatikan sadar lewat `budget.failClosedOnMissingPricing: false`.
    budget_fail_closed: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LLMConfig:
        retry = data.get("retry") or {}
        circuit = data.get("circuit") or {}
        cache = data.get("cache") or {}
        budget = data.get("budget") or {}
        providers = tuple(
            ProviderSpec(
                name=str(p["name"]),
                base_url=str(p.get("baseUrl", "")).rstrip("/"),
                key_env=str(p.get("keyEnv", "")),
                models=dict(p.get("models") or {}),
            )
            for p in (data.get("providers") or [])
        )
        primary = str(data.get("primary") or (providers[0].name if providers else ""))
        return cls(
            primary=primary,
            timeout_ms=int(data.get("timeoutMs", 45000)),
            retry_attempts=int(retry.get("attempts", 2)),
            retry_backoff_ms=int(retry.get("backoffMs", 800)),
            circuit_failures=int(circuit.get("failures", 5)),
            circuit_window_sec=int(circuit.get("windowSec", 120)),
            circuit_cooldown_sec=int(circuit.get("cooldownSec", 300)),
            cache_ttl_sec=int(cache.get("ttlSec", 900)),
            cache_max_entries=int(cache.get("maxEntries", 2000)),
            budget_daily_usd=float(budget.get("dailyUsd", 3.0)),
            budget_per_role={str(k): float(v) for k, v in (budget.get("perRoleDailyUsd") or {}).items()},
            providers=providers,
            pricing={str(k): dict(v) for k, v in (data.get("pricing") or {}).items()},
            budget_fail_closed=bool(budget.get("failClosedOnMissingPricing", True)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> LLMConfig:
        teks = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(teks))

    @classmethod
    def load(cls, path: str | Path | None = None) -> LLMConfig:
        """Muat dari env ``WARROOM_LLM_CONFIG`` atau ``/etc/warroom/llm.json``.

        Gagal dengan pesan yang tidak memuat kredensial bila berkas tidak ada.
        """
        kandidat = Path(path or os.environ.get(ENV_CONFIG_PATH) or DEFAULT_CONFIG_PATH)
        try:
            ada = kandidat.exists()
        except PermissionError:
            ada = False
        if not ada:
            raise FileNotFoundError(
                f"konfigurasi LLM tidak ditemukan di {kandidat} — tidak ada kredensial yang dicetak"
            )
        return cls.from_file(kandidat)

    def provider(self, name: str) -> ProviderSpec:
        for p in self.providers:
            if p.name == name:
                return p
        raise KeyError(f"provider tidak dikenal: {name}")

    def chain(self) -> list[ProviderSpec]:
        """Urutan coba: primary lebih dahulu, sisanya sesuai urutan daftar."""
        urut: list[ProviderSpec] = []
        nama: set[str] = set()
        if self.primary:
            try:
                urut.append(self.provider(self.primary))
                nama.add(self.primary)
            except KeyError:
                pass
        for p in self.providers:
            if p.name not in nama:
                urut.append(p)
                nama.add(p.name)
        return urut

    def model_for(self, provider: str, tier: str) -> str:
        models = self.provider(provider).models
        return models.get(tier) or models.get("fast") or next(iter(models.values()), "")

    def key_envs(self) -> tuple[str, ...]:
        return tuple(p.key_env for p in self.providers if p.key_env)


def default_config() -> LLMConfig:
    """Konfigurasi EFEKTIF gateway: berkas root bila ada, jika tidak bentuk baku.

    Berkas root (``/etc/warroom/llm.json`` atau ``WARROOM_LLM_CONFIG``) adalah sumber
    kebenaran. Tanpa jalur ini, suntingan pada berkas itu tidak berpengaruh apa pun —
    pernah terjadi di produksi: rantai live tetap ``nutaraline → qonek`` meski berkas
    diubah, sehingga urutan provider yang diminta owner tidak pernah benar-benar aktif.
    """
    try:
        return LLMConfig.load()
    except (FileNotFoundError, PermissionError):
        pass
    return LLMConfig.from_dict(
        {
            "primary": "nutaraline",
            "timeoutMs": 45000,
            "retry": {"attempts": 2, "backoffMs": 800},
            "circuit": {"failures": 5, "windowSec": 120, "cooldownSec": 300},
            "cache": {"ttlSec": 900, "maxEntries": 2000},
            # failClosedOnMissingPricing WAJIB true: tanpa harga, anggaran harian tak
            # bisa dihitung dan dulu diam-diam dianggap nol (fail-open, temuan 5 Okt 2026).
            "budget": {"dailyUsd": 3.0, "perRoleDailyUsd": {}, "failClosedOnMissingPricing": True},
            "providers": [
                {
                    "name": "nutaraline",
                    "baseUrl": "https://nutaraline.co.uk/v1",
                    "keyEnv": "HERMES_CUSTOM_NUTARALINE_CO_UK_API_KEY",
                    "models": {"fast": "mimo-v2.6-flash", "deep": "mimo-v2.6-flash"},
                },
                {
                    "name": "qonek",
                    "baseUrl": "https://qonek.web.id/v1",
                    "keyEnv": "QONEK_API_KEY",
                    "models": {"fast": "qonek/deepseek-v4.1-flash", "deep": "qonek/deepseek-v4.1-flash"},
                },
            ],
            # Harga per 1k token (USD) — nilai placeholder konservatif. Sesuaikan dengan
            # tarif provider yang disepakati; tanpa ini _cost() selalu None.
            "pricing": {
                "nutaraline": {"in": 0.001, "out": 0.002},
                "qonek": {"in": 0.001, "out": 0.002},
            },
        }
    )
