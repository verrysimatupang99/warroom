"""Pipeline keluaran: scrub → parse JSON → validasi skema → verifikasi kutipan fakta.

Dipakai baik oleh gateway runtime maupun eval harness, supaya hasil eval benar-benar
mencerminkan jalur produksi (bukan pemeriksa terpisah yang bisa menyimpang).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from warroom_llm.facts import (
    claims_without_citation,
    fact_ids_from_output,
    missing_fact_ids,
)
from warroom_llm.schemas import validate_output
from warroom_llm.scrub import scrub_all

__all__ = [
    "Decision",
    "evaluate_output",
    "extract_json",
    "insufficient_output",
    "screen_sparse_facts",
]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.S)
_OBJ_RE = re.compile(r"\{.*\}", flags=re.S)

Verdict = Literal["ok", "rejected", "insufficient"]


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    output: dict | None
    issues: tuple[str, ...] = ()
    fact_ids: tuple[int, ...] = ()


def insufficient_output(code: str) -> dict:
    """Keluaran ``insufficient`` yang **tidak memuat satu digit pun** (nol angka baru)."""
    return {
        "status": "insufficient",
        "pesan": "Belum bisa disimpulkan: fakta yang tersedia belum cukup.",
        "kode": code,
        "perlu": ["fakta tambahan yang punya fact_id"],
    }


def screen_sparse_facts(jumlah_fakta: int, min_facts: int) -> Decision | None:
    """Bila fakta kurang dari minimum → putuskan ``insufficient`` tanpa memanggil LLM."""
    if jumlah_fakta < min_facts:
        return Decision("insufficient", insufficient_output("fakta_kurang"), ("fakta_kurang",))
    return None


def extract_json(text: str) -> object | None:
    """Ambil JSON dari jawaban model (menerima code fence atau teks pembungkus)."""
    if not text:
        return None
    bersih = text.strip()
    m = _FENCE_RE.search(bersih)
    if m:
        bersih = m.group(1).strip()
    try:
        return json.loads(bersih)
    except ValueError:
        pass
    m2 = _OBJ_RE.search(bersih)
    if m2:
        try:
            return json.loads(m2.group(0))
        except ValueError:
            return None
    return None


def evaluate_output(
    role: str,
    raw: str,
    provided_ids: set[int],
    existing_ids: set[int] | None = None,
    env_names: tuple[str, ...] | None = None,
) -> Decision:
    """Nilai keluaran mentah model terhadap kontrak peran.

    Urutan penting: scrub lebih dulu (kebocoran kredensial = tolak), lalu bentuk JSON,
    skema, keberadaan ``fact_id``, terakhir kutipan angka.
    """
    bersih, kena_scrub = scrub_all(raw, env_names)
    if kena_scrub:
        return Decision("rejected", None, ("kredensial_terdeteksi",))

    data = extract_json(bersih)
    if data is None:
        return Decision("rejected", None, ("json_tidak_valid",))

    output, schema_issues = validate_output(role, data)
    if output is None:
        return Decision("rejected", None, tuple(schema_issues))

    cited = fact_ids_from_output(role, output)

    tak_diberikan = missing_fact_ids(cited, provided_ids)
    if tak_diberikan:
        return Decision("rejected", None, (f"fact_id_tidak_diberikan:{tak_diberikan}",))

    if existing_ids is not None:
        tak_ada = missing_fact_ids(cited, existing_ids)
        if tak_ada:
            return Decision("rejected", None, (f"fact_id_tidak_ada:{tak_ada}",))

    tanpa_kutipan = claims_without_citation(role, output)
    if tanpa_kutipan:
        return Decision("rejected", None, (f"angka_tanpa_fact_id:{','.join(tanpa_kutipan)}",))

    return Decision("ok", output, (), tuple(sorted(set(cited))))
