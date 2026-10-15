"""Skor panas (heat) 0–100 dari komponen terukur — satu kontrak untuk semua strategi.

Kenapa kontrak ini ada di core: heat dipakai membandingkan setup ANTAR strategi, jadi
cara menghitungnya tidak boleh berbeda per pemanggil. Yang boleh berbeda hanya bobot dan
referensi tiap komponen — dan itu disuplai pemanggil sebagai data, bukan logika.

Aturan kejujuran yang dikodekan di sini (sama dengan `market_signal.py`):

- **Tanpa komponen terukur → skor ``None``, bukan 0.** Nol adalah angka yang berarti
  "terukur nol"; bedanya penting saat orang membandingkan strategi.
- **Komponen yang tidak terbaca tidak menekan skor** — ia dikeluarkan dari rata-rata dan
  dilaporkan di ``catatan``; ``cakupan`` (0–1) memberi tahu berapa bagian bobot yang
  benar-benar terukur, supaya skor dari 1 dari 4 komponen tidak terlihat sama kuat
  dengan skor dari 4 komponen.
- **Normalisasi di-clamp**: nilai di atas ``referensi`` dianggap penuh (100), nilai
  negatif dianggap 0 (komponen bertanda harus dinormalkan pemanggil, mis. ``abs()``).

Modul murni: tanpa jaringan, tanpa berkas, tanpa efek samping.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["HeatComponent", "HeatScore", "hitung_heat"]


@dataclass(frozen=True, slots=True)
class HeatComponent:
    """Satu komponen heat: nilai terukur + skala referensinya.

    ``referensi`` = nilai yang dianggap "penuh" (skor komponen 100). Angka referensi
    adalah kebijakan pemanggil dan wajib bisa dikutip sumbernya di ``catatan``.
    """

    nama: str
    nilai: float | None
    referensi: float
    bobot: float = 1.0
    catatan: str = ""

    def __post_init__(self) -> None:
        if not self.nama.strip():
            raise ValueError("nama komponen wajib diisi")
        if self.referensi <= 0:
            raise ValueError(f"referensi komponen {self.nama!r} harus > 0")
        if self.bobot <= 0:
            raise ValueError(f"bobot komponen {self.nama!r} harus > 0")

    @property
    def skor(self) -> int | None:
        """0–100 untuk komponen ini; ``None`` kalau nilainya tidak terbaca."""
        if self.nilai is None:
            return None
        rasio = min(1.0, max(0.0, self.nilai / self.referensi))
        return round(100 * rasio)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nama": self.nama,
            "nilai": self.nilai,
            "referensi": self.referensi,
            "bobot": self.bobot,
            "skor": self.skor,
            "catatan": self.catatan,
        }


@dataclass(frozen=True, slots=True)
class HeatScore:
    """Hasil hitung heat: skor, cakupan, dan komponen apa adanya."""

    skor: int | None
    cakupan: float
    komponen: tuple[HeatComponent, ...]
    catatan: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skor": self.skor,
            "cakupan": self.cakupan,
            "komponen": [k.to_dict() for k in self.komponen],
            "catatan": self.catatan,
        }


def hitung_heat(komponen: Sequence[HeatComponent]) -> HeatScore:
    """Rata-rata berbobot skor komponen yang terukur; ``None`` kalau tidak ada.

    ``cakupan`` = bagian bobot yang terukur (0–1). Ini bukan hiasan: heat yang dihitung
    dari satu komponen tidak boleh dibandingkan buta dengan heat dari empat komponen.
    """
    if not komponen:
        raise ValueError("hitung_heat butuh minimal satu komponen")

    total_bobot = sum(k.bobot for k in komponen)
    terukur = [k for k in komponen if k.nilai is not None]
    bobot_terukur = sum(k.bobot for k in terukur)
    cakupan = round(bobot_terukur / total_bobot, 2)

    kosong = [k.nama for k in komponen if k.nilai is None]
    if not terukur:
        return HeatScore(
            skor=None,
            cakupan=0.0,
            komponen=tuple(komponen),
            catatan="tidak ada komponen terukur — skor n/a, bukan 0",
        )

    berbobot: list[float] = []
    for k in terukur:
        s = k.skor
        if s is not None:  # tidak mungkin None di sini, tetapi tipe harus dibuktikan
            berbobot.append(k.bobot * s)
    rata = sum(berbobot) / bobot_terukur
    catatan = f"{len(terukur)}/{len(komponen)} komponen terukur"
    if kosong:
        catatan += f"; tidak terbaca: {', '.join(kosong)}"
    return HeatScore(skor=round(rata), cakupan=cakupan, komponen=tuple(komponen), catatan=catatan)
