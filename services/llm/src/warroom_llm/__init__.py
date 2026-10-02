"""War Room LLM gateway (P3).

Kontrak: ``04-lapisan-ai.md``. Angka tidak pernah lahir dari LLM — hanya narasi/verifikasi
atas fakta ber-``fact_id``. Konfigurasi provider: ``/etc/warroom/llm.json`` (root-only,
tidak pernah masuk repo/log/percakapan).

Isi paket:

- :mod:`warroom_llm.gateway` — orkestrasi rantai provider, circuit breaker, cache, audit.
- :mod:`warroom_llm.prompts` — registry prompt (berkas + tabel ``prompts``).
- :mod:`warroom_llm.pipeline` — scrub → JSON → skema → verifikasi ``fact_id``.
- :mod:`warroom_llm.evals` — eval harness deterministik per peran.
"""

from __future__ import annotations

from warroom_llm.config import LLMConfig, ProviderSpec, default_config
from warroom_llm.evals import EvalReport, GoldenCase, load_golden, run_case, run_suite
from warroom_llm.facts import FactRef, render_fakta
from warroom_llm.gateway import CallRequest, CallResult, Gateway
from warroom_llm.pipeline import Decision, evaluate_output, insufficient_output
from warroom_llm.prompts import PromptRegistry, PromptSpec, load_prompts, sync_prompts
from warroom_llm.providers import CircuitBreaker, ProviderClient, ProviderError, ResultCache
from warroom_llm.scrub import scrub, scrub_all
from warroom_llm.untrusted import ANTI_INJECTION_RULES, detect_injection, wrap_untrusted

__all__ = [
    "ANTI_INJECTION_RULES",
    "CallRequest",
    "CallResult",
    "CircuitBreaker",
    "Decision",
    "EvalReport",
    "FactRef",
    "Gateway",
    "GoldenCase",
    "LLMConfig",
    "PromptRegistry",
    "PromptSpec",
    "ProviderClient",
    "ProviderError",
    "ProviderSpec",
    "ResultCache",
    "default_config",
    "detect_injection",
    "evaluate_output",
    "insufficient_output",
    "load_golden",
    "load_prompts",
    "render_fakta",
    "run_case",
    "run_suite",
    "scrub",
    "scrub_all",
    "sync_prompts",
    "wrap_untrusted",
]
