"""Fakta bernomor + verifikasi ``fact_id`` (ADR-005, blueprint 04 §4).

Aturan: nilai masuk ke prompt sebagai blok ``FAKTA`` bernomor; LLM hanya boleh merujuk
nomor itu. Kalimat yang menyebut angka tanpa ``fact_id`` ditolak; ``fact_id`` yang tidak
ada di DB juga ditolak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "FactRef",
    "claims_without_citation",
    "fact_ids_from_output",
    "missing_fact_ids",
    "numbers_in",
    "render_fakta",
]

# Token angka berdiri sendiri ("n=1175", "79.0%", "n≥30") — label "F1" sengaja tidak cocok.
_NUM_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?(?![\w])")


@dataclass(frozen=True)
class FactRef:
    """Satu fakta yang diinjeksi ke prompt: nomor tampil (F1), nilai, dan ``fact_id`` DB."""

    fact_id: int
    label: str
    text: str


def render_fakta(facts: list[FactRef]) -> str:
    baris = [f"{f.label}: {f.text} (fact_id={f.fact_id})" for f in facts]
    return "BLOK FAKTA (hanya nomor ini yang boleh dirujuk):\n" + "\n".join(baris)


def numbers_in(text: str) -> list[str]:
    return _NUM_RE.findall(text or "")


def fact_ids_from_output(role: str, output: dict) -> list[int]:
    """Kumpulkan seluruh ``fact_id`` yang dikutip keluaran, sesuai bentuk tiap peran."""
    ids: list[int] = []
    if role == "narrator":
        for kalimat in output.get("kalimat") or []:
            ids.extend(int(x) for x in (kalimat.get("fact_ids") or []))
    elif role == "verifier":
        ids.extend(int(x) for x in (output.get("fact_ids") or []))
    elif role == "anomaly":
        for anomali in output.get("anomali") or []:
            ids.extend(int(x) for x in (anomali.get("fact_ids") or []))
    return ids


def _semua_ids(output: dict) -> list[int]:
    ids: list[int] = []
    if isinstance(output.get("fact_ids"), list):
        ids.extend(int(x) for x in output["fact_ids"])
    for key in ("kalimat", "anomali"):
        for item in output.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("fact_ids"), list):
                ids.extend(int(x) for x in item["fact_ids"])
    return ids


def claims_without_citation(role: str, output: dict) -> list[str]:
    """Kalimat/klaim yang menyebut angka tapi tidak punya ``fact_id``.

    ``magnitudo`` pada peran anomaly selalu berupa angka, jadi setiap anomali wajib
    mengutip minimal satu ``fact_id``.
    """
    pelanggaran: list[str] = []
    if role == "narrator":
        for i, kalimat in enumerate(output.get("kalimat") or []):
            if numbers_in(kalimat.get("teks", "")) and not (kalimat.get("fact_ids") or []):
                pelanggaran.append(f"kalimat[{i}]")
    elif role == "verifier":
        if numbers_in(output.get("alasan", "")) and not (output.get("fact_ids") or []):
            pelanggaran.append("alasan")
    elif role == "anomaly":
        for i, anomali in enumerate(output.get("anomali") or []):
            if not (anomali.get("fact_ids") or []):
                pelanggaran.append(f"anomali[{i}].magnitudo")
        if numbers_in(output.get("catatan", "")) and not _semua_ids(output):
            pelanggaran.append("catatan")
    return pelanggaran


def missing_fact_ids(cited: list[int], known: set[int]) -> list[int]:
    return sorted({i for i in cited if i not in known})
