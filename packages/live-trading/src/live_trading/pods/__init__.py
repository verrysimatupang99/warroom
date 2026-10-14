"""Pod Fase 1: analis deterministik per proyek + lead per pod.

Aturan keras (lihat AGENTS.md):
- Analis hanya MEMBACA snapshot/state. Tidak ada LLM di jalur ini.
- Output analis = fakta + status. Tidak ada eksekusi, tidak ada rekomendasi live.
- IDX mentok Fase 2 (tanpa auto-order saham retail) — dicatat di pod idx.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    nama: str
    status: str  # hijau | kuning | merah | abu
    fakta: list[str] = field(default_factory=list)

    def baris(self) -> str:
        return f"{self.nama}: " + ("; ".join(self.fakta) if self.fakta else "n/a")


@dataclass
class LaporanPod:
    pod: str
    status: str
    ringkas: list[str] = field(default_factory=list)
    analis: list[AnalysisResult] = field(default_factory=list)


def _rangkum(analis: list[AnalysisResult]) -> str:
    order = {"merah": 3, "kuning": 2, "abu": 1, "hijau": 0}
    return max(analis, key=lambda a: order.get(a.status, 0)).status if analis else "abu"
