"""Skema keluaran JSON per peran (pydantic v2).

Satu sumber kebenaran: model pydantic inilah yang memvalidasi keluaran; berkas prompt
menyimpan salinan ``schema_json`` dan registry menolak bila salinannya menyimpang
(gerbang anti-drift, lihat :mod:`warroom_llm.prompts`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

__all__ = ["AnomalyOut", "NarratorOut", "ROLE_MODELS", "VerifierOut", "model_for", "validate_output"]


class _Strict(BaseModel):
    """Tolak kunci tak dikenal + tanpa koersi tipe.

    ``strict=True`` penting: tanpa itu pydantic diam-diam mengubah string ``"true"``
    menjadi boolean, sehingga keluaran cacat lolos sebagai sah.
    """

    model_config = ConfigDict(extra="forbid", strict=True)


class Kalimat(_Strict):
    teks: str
    fact_ids: list[int]


class NarratorOut(_Strict):
    kalimat: list[Kalimat]
    nada: str


class VerifierOut(_Strict):
    setuju: bool
    alasan: str
    fact_ids: list[int]
    tingkat: Literal["yakin", "ragu", "kurang"]


class Anomali(_Strict):
    metrik: str
    arah: str
    magnitudo: float
    fact_ids: list[int]

    @field_validator("magnitudo", mode="before")
    @classmethod
    def _terima_int(cls, v: object) -> object:
        # LLM sering menulis 2 alih-alih 2.0; terima int, tolak bool (bukan angka).
        if isinstance(v, bool):
            raise ValueError("magnitudo tidak boleh boolean")
        if isinstance(v, int):
            return float(v)
        if isinstance(v, str):
            # LLM juga kadang mengirim angkanya sebagai string ("2.0"). Itu tetap angka yang
            # sama, bukan karangan — jadi diterima. Yang BUKAN angka (mis. "tinggi") ditolak,
            # karena menerimanya berarti mengarang besaran yang tidak ada di fakta.
            try:
                return float(v.strip())
            except ValueError as exc:
                raise ValueError("magnitudo harus berupa angka (mis. 2.0), bukan kata/teks") from exc
        return v


class AnomalyOut(_Strict):
    anomali: list[Anomali]
    catatan: str


ROLE_MODELS: dict[str, type[BaseModel]] = {
    "narrator": NarratorOut,
    "verifier": VerifierOut,
    "anomaly": AnomalyOut,
}


def model_for(role: str) -> type[BaseModel] | None:
    return ROLE_MODELS.get(role)


def validate_output(role: str, data: object) -> tuple[dict | None, list[str]]:
    """Validasi ``data`` terhadap skema peran. Kembalikan ``(hasil, daftar_masalah)``."""
    model = ROLE_MODELS.get(role)
    if model is None:
        return None, [f"peran_tidak_dikenal:{role}"]
    try:
        terverifikasi = model.model_validate(data)
    except ValidationError as exc:
        issues = [f"schema_invalid:{'.'.join(str(x) for x in e['loc'])}:{e['msg']}" for e in exc.errors()]
        return None, issues
    return terverifikasi.model_dump(), []
