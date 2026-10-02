"""Registry prompt: berkas di ``prompts/`` + tabel ``prompts`` (append-only, berversi).

Berkas adalah sumber kebenaran saat memuat; ``sync_prompts()`` mencerminkan versi baru ke
DB. Perubahan prompt = versi baru, tidak pernah menimpa — sehingga ``llm_calls.prompt_version``
tetap bisa menautkan hasil ke isi prompt yang benar-benar dipakai.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Prompt

from warroom_llm.schemas import ROLE_MODELS

__all__ = [
    "PromptRegistry",
    "PromptSpec",
    "active_prompt",
    "load_prompt_file",
    "load_prompts",
    "sync_prompts",
]


@dataclass(frozen=True)
class PromptSpec:
    role: str
    version: str
    body: str
    schema_json: dict = field(default_factory=dict)
    contoh: tuple[dict, ...] = ()
    catatan: str = ""
    source: str = "file"


def load_prompt_file(path: str | Path) -> PromptSpec:
    """Muat satu berkas prompt + gerbang anti-drift terhadap model pydantic peran."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    role = str(data["role"])
    model = ROLE_MODELS.get(role)
    if model is not None and data.get("schema_json") != model.model_json_schema():
        raise ValueError(f"schema_json untuk peran {role} menyimpang dari model pydantic ({p})")
    return PromptSpec(
        role=role,
        version=str(data["version"]),
        body=str(data["body"]),
        schema_json=dict(data.get("schema_json") or {}),
        contoh=tuple(data.get("contoh") or []),
        catatan=str(data.get("catatan", "")),
        source=str(p),
    )


def load_prompts(directory: str | Path) -> dict[str, PromptSpec]:
    out: dict[str, PromptSpec] = {}
    for p in sorted(Path(directory).glob("*.json")):
        spec = load_prompt_file(p)
        out[spec.role] = spec
    return out


def prompt_from_row(row: Prompt) -> PromptSpec:
    return PromptSpec(
        role=row.role,
        version=row.version,
        body=row.body,
        schema_json=dict(row.schema_json or {}),
        contoh=tuple(row.contoh_json or []),
        source="db",
    )


def sync_prompts(session: SASession, prompts: dict[str, PromptSpec]) -> int:
    """Simpan versi yang belum ada; nonaktifkan versi lama peran itu. Kembalikan jumlah baru."""
    ada = {(r, v) for r, v in session.execute(select(Prompt.role, Prompt.version)).all()}
    ditambah = 0
    for role, spec in prompts.items():
        if (role, spec.version) in ada:
            continue
        session.execute(update(Prompt).where(Prompt.role == role).values(active=False))
        session.add(
            Prompt(
                role=role,
                version=spec.version,
                body=spec.body,
                schema_json=spec.schema_json,
                contoh_json=list(spec.contoh),
                active=True,
            )
        )
        ditambah += 1
    session.flush()
    return ditambah


def active_prompt(session: SASession, role: str) -> PromptSpec | None:
    row = session.scalars(
        select(Prompt).where(Prompt.role == role, Prompt.active.is_(True)).order_by(Prompt.created_at.desc())
    ).first()
    return prompt_from_row(row) if row is not None else None


class PromptRegistry:
    """Akses prompt per peran; berkas default, opsional diambil dari DB bila ada."""

    def __init__(self, prompts: dict[str, PromptSpec]) -> None:
        self._p = dict(prompts)

    def get(self, role: str) -> PromptSpec:
        if role not in self._p:
            raise KeyError(f"prompt untuk peran tidak ada: {role}")
        return self._p[role]

    def roles(self) -> list[str]:
        return sorted(self._p)

    @classmethod
    def from_dir(cls, directory: str | Path) -> PromptRegistry:
        return cls(load_prompts(directory))

    @classmethod
    def from_db(cls, session: SASession, fallback: PromptRegistry | None = None) -> PromptRegistry:
        """Ambil versi aktif dari DB; jatuh ke berkas bila DB belum punya peran itu."""
        prompts: dict[str, PromptSpec] = {}
        for role in fallback.roles() if fallback else []:
            spec = active_prompt(session, role)
            prompts[role] = spec if spec is not None else fallback.get(role)  # type: ignore[union-attr]
        return cls(prompts)
