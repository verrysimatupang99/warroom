"""Canonical research and execution contracts shared by every market.

These contracts intentionally use stdlib dataclasses so the domain layer does not
inherit an API framework. API adapters may serialize them, but cannot weaken the
required fields or silently turn absent values into defaults.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import ClassVar, Literal

__all__ = ["ExecutionSpec", "HypothesisSpec", "SPEC_SCHEMA_VERSION", "SpecError"]


class SpecError(ValueError):
    """Raised when a research or execution contract is incomplete or unsafe."""


SPEC_SCHEMA_VERSION = "1"


def _json_ready(value: object) -> object:
    """Convert contract values to deterministic, JSON-compatible values."""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


class _CanonicalSpec:
    schema_version: ClassVar[str] = SPEC_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def _canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_type": type(self).__name__,
            "spec": _json_ready(self.to_dict()),
        }

    def to_json(self) -> str:
        """Return the stable wire representation used for artifact identity."""
        return json.dumps(
            self._canonical_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of schema version and contract contents."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


_REQUIRED_HYPOTHESIS = (
    "hypothesis_id", "market", "instrument_or_pool", "rule_version", "input_fields",
    "lookahead_policy", "cost_policy", "session_timezone", "entry_rule", "exit_rule",
    "stop_rule", "position_sizing", "baseline", "split", "population", "invalidation",
)


@dataclass(frozen=True, slots=True)
class HypothesisSpec(_CanonicalSpec):
    """Falsifiable, market-neutral research contract."""

    hypothesis_id: str
    market: str
    instrument_or_pool: str
    rule_version: str
    input_fields: tuple[str, ...]
    lookahead_policy: str
    cost_policy: str
    session_timezone: str
    entry_rule: str
    exit_rule: str
    stop_rule: str
    position_sizing: str
    baseline: str
    split: str
    population: str
    invalidation: str

    def __post_init__(self) -> None:
        for field in _REQUIRED_HYPOTHESIS:
            value = getattr(self, field)
            if isinstance(value, str) and not value.strip():
                raise SpecError(f"{field} wajib diisi")
        if not self.input_fields or any(not f.strip() for f in self.input_fields):
            raise SpecError("input_fields wajib memuat field yang nyata")

    def is_complete(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExecutionSpec(_CanonicalSpec):
    """Executable-price and risk contract for paper or future gated live paths."""

    entry_price_rule: str
    exit_price_rule: str
    stop_rule: str
    time_stop: str
    fee_policy: str
    slippage_policy: str
    latency_policy: str
    fill_policy: str
    risk_budget: str
    size_rule: str
    no_trade_conditions: tuple[str, ...]
    venue: str
    mode: Literal["paper", "shadow", "live"]
    as_of: datetime

    def __post_init__(self) -> None:
        for field in (
            "entry_price_rule", "exit_price_rule", "stop_rule", "time_stop",
            "fee_policy", "slippage_policy", "latency_policy", "fill_policy",
            "risk_budget", "size_rule", "venue",
        ):
            if not getattr(self, field).strip():
                raise SpecError(f"{field} wajib diisi")
        if not self.no_trade_conditions or any(not x.strip() for x in self.no_trade_conditions):
            raise SpecError("no_trade_conditions wajib eksplisit")
        if self.mode == "live":
            raise SpecError(
                "mode live memerlukan grant owner dan gate runtime; kontrak ini paper/shadow-only"
            )
        if self.as_of.tzinfo is None:
            raise SpecError("as_of wajib timezone-aware")

    def is_executable_contract(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
