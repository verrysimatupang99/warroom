"""Research-only persistence contract for versioned specs and artifacts.

This module deliberately builds a validated preview only. Database writers may persist
its output, but this layer never performs I/O and cannot authorize live execution.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from warroom_core.specs import ExecutionSpec, HypothesisSpec

__all__ = ["ResearchValidationError", "build_research_run_preview"]


class ResearchValidationError(ValueError):
    """Raised when a research record cannot be safely persisted."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _versioned_json(value: dict[str, Any]) -> tuple[dict[str, Any], str]:
    document = _jsonable(value)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return document, hashlib.sha256(encoded).hexdigest()


def build_research_run_preview(
    research_key: str,
    hypothesis: HypothesisSpec,
    execution: ExecutionSpec,
    provenance: dict[str, Any],
    artifacts: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Return a fail-closed, DB-ready research snapshot without writing anywhere."""
    if not research_key.strip():
        raise ResearchValidationError("research_key wajib diisi")
    if not provenance or any(not str(key).strip() for key in provenance):
        raise ResearchValidationError("provenance wajib diisi")
    if execution.mode == "live":
        raise ResearchValidationError("research-only preview menolak mode live")

    hypothesis_json, hypothesis_hash = _versioned_json(hypothesis.to_dict())
    execution_json, execution_hash = _versioned_json(execution.to_dict())
    validated_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        kind = str(artifact.get("kind", "")).strip()
        uri = str(artifact.get("uri", "")).strip()
        sha256 = str(artifact.get("sha256", "")).lower().strip()
        if not kind or not uri:
            raise ResearchValidationError("artifact kind dan uri wajib diisi")
        if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise ResearchValidationError("artifact sha256 wajib berupa hash hex 64 karakter")
        validated_artifacts.append(_jsonable({**artifact, "kind": kind, "uri": uri, "sha256": sha256}))

    return {
        "research_key": research_key.strip(),
        "status": "draft",
        "hypothesis_id": hypothesis.hypothesis_id,
        "hypothesis_version": hypothesis.rule_version,
        "hypothesis_json": hypothesis_json,
        "hypothesis_hash": hypothesis_hash,
        "execution_json": execution_json,
        "execution_hash": execution_hash,
        "provenance": _jsonable(provenance),
        "artifacts": validated_artifacts,
    }
