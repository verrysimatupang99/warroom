"""Klien provider, circuit breaker, dan cache hasil (blueprint 04 §2/§7).

Tanpa I/O jaringan tersembunyi: ``ProviderClient`` menerima ``httpx.Client`` sehingga tes
bisa menyuntikkan ``MockTransport`` (HTTP 500/timeout) tanpa menyentuh internet.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any

import httpx

from warroom_llm.config import LLMConfig, ProviderSpec

__all__ = ["CircuitBreaker", "Completion", "ProviderClient", "ProviderError", "ResultCache"]


class ProviderError(Exception):
    """Kegagalan satu percobaan provider — selalu punya kode yang dicatat di ``llm_calls``."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Completion:
    content: str
    tokens_in: int | None = None
    tokens_out: int | None = None


class CircuitBreaker:
    """Buka sirkuit setelah N kegagalan dalam jendela waktu; tutup lagi setelah cooldown."""

    def __init__(
        self,
        failures: int,
        window_sec: int,
        cooldown_sec: int,
        clock=time.monotonic,
    ) -> None:
        self._failures = max(1, failures)
        self._window = window_sec
        self._cooldown = cooldown_sec
        self._clock = clock
        self._kegagalan: dict[str, deque[float]] = {}
        self._buka_sampai: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        sampai = self._buka_sampai.get(provider)
        if sampai is None:
            return False
        if self._clock() >= sampai:
            self._buka_sampai.pop(provider, None)
            self._kegagalan.pop(provider, None)
            return False
        return True

    def record_failure(self, provider: str) -> None:
        now = self._clock()
        dq = self._kegagalan.setdefault(provider, deque())
        dq.append(now)
        while dq and now - dq[0] > self._window:
            dq.popleft()
        if len(dq) >= self._failures:
            self._buka_sampai[provider] = now + self._cooldown

    def record_success(self, provider: str) -> None:
        self._kegagalan.pop(provider, None)
        self._buka_sampai.pop(provider, None)


class ResultCache:
    """Cache in-memory hasil berdasarkan hash(prompt_version + fakta + peran) — TTL + batas entri."""

    def __init__(self, ttl_sec: int, max_entries: int, clock=time.monotonic) -> None:
        self._ttl = ttl_sec
        self._max = max(1, max_entries)
        self._clock = clock
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        ts, value = item
        if self._clock() - ts > self._ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> None:
        self._data[key] = (self._clock(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)


class ProviderClient:
    """Satu POST ``/chat/completions`` ke provider OpenAI-compatible."""

    def __init__(self, config: LLMConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client or httpx.Client()
        self._owns = client is None

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def complete(
        self,
        spec: ProviderSpec,
        model: str,
        messages: list[dict[str, str]],
        timeout_s: float,
    ) -> Completion:
        key = os.environ.get(spec.key_env, "") if spec.key_env else ""
        headers = {"Content-Type": "application/json"}
        if key:
            # Nilai kunci tidak pernah dicetak/dilog — hanya dipakai di header permintaan.
            headers["Authorization"] = f"Bearer {key}"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = self._client.post(
                f"{spec.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("koneksi", type(exc).__name__) from exc

        if resp.status_code >= 400:
            raise ProviderError(f"http_{resp.status_code}", f"status {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError("json_tidak_valid", "respons bukan JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("kosong", "tidak ada choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("kosong", "konten kosong")

        usage = data.get("usage") or {}
        return Completion(
            content=content,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )
