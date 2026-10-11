"""Fixture tes layanan LLM (P3).

Menjembatani fixture ``db`` root (DB tes terpisah) dengan helper gateway. Tes murni
(scrub/skema/pipeline tanpa DB) tidak meminta ``db``; tes yang menyentuh ``llm_calls``
memakai fixture ``bersih_llm``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from warroom_llm.config import LLMConfig
from warroom_llm.gateway import Gateway
from warroom_llm.prompts import PromptRegistry

ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = ROOT / "prompts"


@pytest.fixture
def prompts() -> PromptRegistry:
    return PromptRegistry.from_dir(PROMPTS_DIR)


def _config_dict(**over: object) -> dict:
    base: dict = {
        "primary": "nutaraline",
        "retry": {"attempts": 2, "backoffMs": 0},
        "circuit": {"failures": 5, "windowSec": 120, "cooldownSec": 300},
        "cache": {"ttlSec": 900, "maxEntries": 2000},
        "budget": {"dailyUsd": 3.0, "perRoleDailyUsd": {}},
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
        "pricing": {
            "nutaraline": {"in": 0.001, "out": 0.002},
            "qonek": {"in": 0.001, "out": 0.002},
        },
    }
    base.update(over)
    return base


@pytest.fixture
def config_factory():
    def _make(**over: object) -> LLMConfig:
        return LLMConfig.from_dict(_config_dict(**over))

    return _make


@pytest.fixture
def llm_config(config_factory) -> LLMConfig:
    return config_factory()


@pytest.fixture
def jawaban():
    """Bangun respons chat-completions palsu (untuk httpx.MockTransport)."""

    def _jawaban(content: str, tokens: tuple[int, int] = (10, 5)) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]},
            },
        )

    return _jawaban


@pytest.fixture
def gateway_factory(llm_config, prompts):
    """Bangun Gateway dengan transport palsu; tidur dinonaktifkan supaya tes cepat."""

    def _make(handler, *, config: LLMConfig | None = None, breaker=None, cache=None) -> Gateway:
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return Gateway(
            config or llm_config,
            prompts,
            http_client=client,
            breaker=breaker,
            cache=cache,
            sleep=lambda _s: None,
        )

    return _make


@pytest.fixture
def fakta(db):
    """Sisipkan baris ``facts`` nyata; kembalikan daftar ``fact_id``."""

    def _buat(jumlah: int = 1, kind: str = "verdict") -> list[int]:
        from warroom_core.db import Fact, session_scope

        ids: list[int] = []
        with session_scope() as s:
            for i in range(jumlah):
                f = Fact(
                    kind=kind,
                    key=f"uji-{i}",
                    value_json={"v": i},
                    source="uji",
                    observed_at=datetime.now(UTC),
                    ttl_s=3600,
                    hash=f"hash-{i}",
                )
                s.add(f)
                s.flush()
                ids.append(int(f.id))
        return ids

    return _buat


@pytest.fixture
def bersih_llm(db):
    """Isolasi tabel yang dipakai bersama lintas tes LLM."""
    from warroom_core.db import LLMCall, Prompt, session_scope

    with session_scope() as s:
        s.query(LLMCall).delete()
        s.query(Prompt).delete()
    yield
