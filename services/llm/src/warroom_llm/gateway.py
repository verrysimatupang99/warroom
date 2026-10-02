"""Gateway LLM: rantai provider (nutaraline → qonek), circuit breaker, cache, dan audit.

Kontrak blueprint 04: angka tidak pernah lahir dari LLM (gagal = ``insufficient``), setiap
panggilan tercatat di ``llm_calls``, konten eksternal = data bukan perintah, kredensial
tidak pernah mencetak dirinya ke log.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import func, select
from warroom_core.db import Fact, LLMCall, session_scope

from warroom_llm.config import LLMConfig
from warroom_llm.facts import FactRef, render_fakta
from warroom_llm.pipeline import evaluate_output, insufficient_output, screen_sparse_facts
from warroom_llm.prompts import PromptRegistry, PromptSpec
from warroom_llm.providers import CircuitBreaker, ProviderClient, ProviderError, ResultCache
from warroom_llm.scrub import scrub_all
from warroom_llm.untrusted import ANTI_INJECTION_RULES, wrap_untrusted

__all__ = ["EXEMPT_BUDGET_ROLES", "CallRequest", "CallResult", "Gateway"]

# Peran baca esensial tetap jalan saat anggaran habis; peran lain dijeda (blueprint 04 §7).
EXEMPT_BUDGET_ROLES = frozenset({"narrator"})


def _hash_json(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class CallRequest:
    role: str
    user: str = ""
    facts: tuple[FactRef, ...] = ()
    untrusted: tuple[tuple[str, str], ...] = ()
    tier: str = "fast"
    min_facts: int = 1
    use_cache: bool = True
    cache_salt: str = ""


@dataclass(frozen=True)
class CallResult:
    status: str  # ok | insufficient
    role: str
    prompt_version: str = ""
    output: dict | None = None
    provider: str | None = None
    model: str | None = None
    fallback_from: str | None = None
    fact_ids: tuple[int, ...] = ()
    result_hash: str | None = None
    latency_ms: int | None = None
    cached: bool = False
    error_code: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    issues: tuple[str, ...] = field(default_factory=tuple)


class Gateway:
    """Orkestrasi satu panggilan LLM ber-peran."""

    def __init__(
        self,
        config: LLMConfig,
        prompts: PromptRegistry,
        *,
        http_client: Any = None,
        cache: ResultCache | None = None,
        breaker: CircuitBreaker | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        session_factory: Callable[[], AbstractContextManager[Any]] = session_scope,
    ) -> None:
        self._cfg = config
        self._prompts = prompts
        self._client = ProviderClient(config, http_client)
        self._cache = cache or ResultCache(config.cache_ttl_sec, config.cache_max_entries, clock=clock)
        self._breaker = breaker or CircuitBreaker(
            config.circuit_failures, config.circuit_window_sec, config.circuit_cooldown_sec, clock=clock
        )
        self._clock = clock
        self._sleep = sleep
        self._session = session_factory

    # --- penyusunan prompt -------------------------------------------------------------

    def _messages(self, spec: PromptSpec, req: CallRequest) -> tuple[str, str]:
        """Perintah + fakta di ``system``; konten tak tepercaya + tugas di ``user``.

        Konten eksternal sengaja tidak pernah masuk ``system`` supaya batas perintah/data
        tetap tegas (anti prompt-injection).
        """
        system_parts = [spec.body, ANTI_INJECTION_RULES]
        if req.facts:
            system_parts.append(render_fakta(list(req.facts)))
        for contoh in spec.contoh[:2]:
            system_parts.append("CONTOH: " + json.dumps(contoh, ensure_ascii=False))
        system = "\n\n".join(system_parts)

        user_parts = [wrap_untrusted(isi, label) for label, isi in req.untrusted]
        user_parts.append(
            req.user or "Buat keluaran JSON sesuai skema peran dan blok FAKTA. Jangan menambah angka baru."
        )
        return system, "\n\n".join(user_parts)

    def _cache_key(self, spec: PromptSpec, req: CallRequest) -> str:
        blob = json.dumps(
            {
                "role": req.role,
                "version": spec.version,
                "tier": req.tier,
                "facts": [[f.fact_id, f.label, f.text] for f in req.facts],
                "untrusted": [[label, isi] for label, isi in req.untrusted],
                "user": req.user,
                "min_facts": req.min_facts,
                "salt": req.cache_salt,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    # --- akses DB ----------------------------------------------------------------------

    def _log(self, **fields: Any) -> None:
        with self._session() as s:
            s.add(LLMCall(**fields))

    def _existing_ids(self, ids: set[int]) -> set[int]:
        if not ids:
            return set()
        with self._session() as s:
            rows = s.execute(select(Fact.id).where(Fact.id.in_(sorted(ids)))).all()
        return {int(r[0]) for r in rows}

    def _budget_blocked(self, role: str) -> bool:
        if role in EXEMPT_BUDGET_ROLES:
            return False
        limit_role = self._cfg.budget_per_role.get(role)
        try:
            with self._session() as s:
                hari_ini = func.date(LLMCall.created_at) == func.current_date()
                if limit_role is not None:
                    terpakai = s.execute(
                        select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(
                            LLMCall.role == role, hari_ini
                        )
                    ).scalar()
                    if float(terpakai or 0) >= limit_role:
                        return True
                total = s.execute(
                    select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(hari_ini)
                ).scalar()
                return float(total or 0) >= self._cfg.budget_daily_usd
        except Exception:  # noqa: BLE001 — DB galat tidak boleh memblokir; kegagalan dicatat jalur log
            return False

    def _cost(self, provider: str, tokens_in: int | None, tokens_out: int | None) -> float | None:
        harga = self._cfg.pricing.get(provider)
        if not harga:
            return None
        masuk = (tokens_in or 0) / 1000 * float(harga.get("in", 0))
        keluar = (tokens_out or 0) / 1000 * float(harga.get("out", 0))
        return round(masuk + keluar, 8)

    # --- panggilan --------------------------------------------------------------------

    def call(self, req: CallRequest) -> CallResult:
        t0 = self._clock()
        try:
            spec = self._prompts.get(req.role)
        except KeyError:
            return CallResult(
                status="insufficient",
                role=req.role,
                output=insufficient_output("peran_tidak_dikenal"),
                error_code="peran_tidak_dikenal",
            )

        # 1) fakta kurang → insufficient deterministik, nol angka, tanpa menyentuh provider.
        sparse = screen_sparse_facts(len(req.facts), req.min_facts)
        if sparse is not None:
            self._log(
                role=req.role,
                provider="none",
                model="",
                prompt_version=spec.version,
                ok=False,
                error_code="fakta_kurang",
                latency_ms=0,
            )
            return CallResult(
                status="insufficient",
                role=req.role,
                prompt_version=spec.version,
                output=sparse.output,
                error_code="fakta_kurang",
                issues=sparse.issues,
            )

        # 2) anggaran harian.
        if self._budget_blocked(req.role):
            self._log(
                role=req.role,
                provider="none",
                model="",
                prompt_version=spec.version,
                ok=False,
                error_code="budget_terlampaui",
                latency_ms=0,
            )
            return CallResult(
                status="insufficient",
                role=req.role,
                prompt_version=spec.version,
                output=insufficient_output("budget_terlampaui"),
                error_code="budget_terlampaui",
            )

        # 3) cache.
        key = self._cache_key(spec, req)
        if req.use_cache:
            tersimpan = self._cache.get(key)
            if tersimpan is not None:
                self._log(
                    role=req.role,
                    provider="cache",
                    model="",
                    prompt_version=spec.version,
                    ok=True,
                    latency_ms=0,
                    result_hash=tersimpan.result_hash,
                    fact_ids=list(tersimpan.fact_ids),
                )
                return replace(tersimpan, cached=True, latency_ms=0)

        system, user = self._messages(spec, req)
        system, _ = scrub_all(system, self._cfg.key_envs())
        user, _ = scrub_all(user, self._cfg.key_envs())
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        provided_ids = {f.fact_id for f in req.facts}
        existing_ids = self._existing_ids(provided_ids)
        chain = self._cfg.chain()
        timeout_s = max(0.001, self._cfg.timeout_ms / 1000)
        percobaan = max(1, self._cfg.retry_attempts)
        errors: list[str] = []

        for idx, prov in enumerate(chain):
            fallback_from = chain[idx - 1].name if idx > 0 else None
            model = self._cfg.model_for(prov.name, req.tier)

            if self._breaker.is_open(prov.name):
                errors.append(f"{prov.name}:circuit_open")
                self._log(
                    role=req.role,
                    provider=prov.name,
                    model=model,
                    prompt_version=spec.version,
                    ok=False,
                    fallback_from=fallback_from,
                    error_code="circuit_open",
                    latency_ms=0,
                )
                continue

            for attempt in range(1, percobaan + 1):
                a0 = self._clock()
                try:
                    comp = self._client.complete(prov, model, messages, timeout_s)
                except ProviderError as exc:
                    lat = int((self._clock() - a0) * 1000)
                    self._breaker.record_failure(prov.name)
                    self._log(
                        role=req.role,
                        provider=prov.name,
                        model=model,
                        prompt_version=spec.version,
                        ok=False,
                        fallback_from=fallback_from,
                        error_code=exc.code,
                        latency_ms=lat,
                    )
                    errors.append(f"{prov.name}:{exc.code}")
                    if attempt < percobaan:
                        self._sleep(self._cfg.retry_backoff_ms * attempt / 1000)
                    continue

                lat = int((self._clock() - a0) * 1000)
                decision = evaluate_output(
                    req.role, comp.content, provided_ids, existing_ids, env_names=self._cfg.key_envs()
                )
                cost = self._cost(prov.name, comp.tokens_in, comp.tokens_out)

                if decision.verdict == "ok":
                    self._breaker.record_success(prov.name)
                    rh = _hash_json(decision.output)
                    self._log(
                        role=req.role,
                        provider=prov.name,
                        model=model,
                        prompt_version=spec.version,
                        tokens_in=comp.tokens_in,
                        tokens_out=comp.tokens_out,
                        cost_usd=cost,
                        latency_ms=lat,
                        ok=True,
                        fallback_from=fallback_from,
                        result_hash=rh,
                        fact_ids=list(decision.fact_ids),
                    )
                    hasil = CallResult(
                        status="ok",
                        role=req.role,
                        prompt_version=spec.version,
                        output=decision.output,
                        provider=prov.name,
                        model=model,
                        fallback_from=fallback_from,
                        fact_ids=decision.fact_ids,
                        result_hash=rh,
                        latency_ms=lat,
                        tokens_in=comp.tokens_in,
                        tokens_out=comp.tokens_out,
                        cost_usd=cost,
                    )
                    if req.use_cache:
                        self._cache.put(key, hasil)
                    return hasil

                kode = decision.issues[0] if decision.issues else "keluaran_tidak_valid"
                self._breaker.record_failure(prov.name)
                self._log(
                    role=req.role,
                    provider=prov.name,
                    model=model,
                    prompt_version=spec.version,
                    tokens_in=comp.tokens_in,
                    tokens_out=comp.tokens_out,
                    cost_usd=cost,
                    latency_ms=lat,
                    ok=False,
                    fallback_from=fallback_from,
                    error_code=kode,
                )
                errors.append(f"{prov.name}:{kode}")
                break  # jawaban tidak valid: jangan retry jawaban yang sama, pindah provider.

        lat_total = int((self._clock() - t0) * 1000)
        self._log(
            role=req.role,
            provider="none",
            model="",
            prompt_version=spec.version,
            ok=False,
            error_code="semua_provider_gagal",
            latency_ms=lat_total,
        )
        return CallResult(
            status="insufficient",
            role=req.role,
            prompt_version=spec.version,
            output=insufficient_output("semua_provider_gagal"),
            error_code="semua_provider_gagal",
            issues=tuple(errors),
            latency_ms=lat_total,
        )
