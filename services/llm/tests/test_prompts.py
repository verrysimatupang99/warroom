"""Tes registry prompt: berkas + tabel ``prompts`` (append-only, berversi)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from warroom_core.db import Prompt, session_scope
from warroom_llm.prompts import PromptRegistry, PromptSpec, active_prompt, load_prompts, sync_prompts

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def test_load_prompts_tiga_peran_dan_skema_cocok() -> None:
    prompts = load_prompts(PROMPTS_DIR)
    assert set(prompts) == {"narrator", "verifier", "anomaly"}
    for spec in prompts.values():
        assert spec.version.startswith(spec.role + "/")
        assert spec.body
        assert spec.schema_json.get("type") == "object"
        assert spec.contoh


def test_registry_get_dan_roles() -> None:
    reg = PromptRegistry.from_dir(PROMPTS_DIR)
    assert reg.roles() == ["anomaly", "narrator", "verifier"]
    assert reg.get("narrator").version == "narrator/1.0.0"


def test_sync_idempoten_dan_versi_baru_menonaktifkan_lama(db, bersih_llm) -> None:
    prompts = load_prompts(PROMPTS_DIR)
    with session_scope() as s:
        assert sync_prompts(s, prompts) == 3
    with session_scope() as s:
        assert sync_prompts(s, prompts) == 0  # idempoten

    baru = PromptSpec(role="narrator", version="narrator/1.0.1", body="versi baru", schema_json={})
    with session_scope() as s:
        assert sync_prompts(s, {"narrator": baru}) == 1
        aktif = active_prompt(s, "narrator")
        assert aktif is not None and aktif.version == "narrator/1.0.1"
        lama = s.scalars(select(Prompt).where(Prompt.version == "narrator/1.0.0")).one()
        assert lama.active is False
        # append-only: baris lama tetap ada
        jumlah = len(s.scalars(select(Prompt).where(Prompt.role == "narrator")).all())
        assert jumlah == 2


def test_registry_dari_db_dengan_fallback_berkas(db, bersih_llm) -> None:
    berkas = PromptRegistry.from_dir(PROMPTS_DIR)
    with session_scope() as s:
        reg = PromptRegistry.from_db(s, fallback=berkas)
    assert reg.roles() == ["anomaly", "narrator", "verifier"]
    assert reg.get("verifier").source.endswith("verifier.json")
