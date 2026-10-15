"""Beekeeper: deteksi expectancy turun per strategi, lalu merekam usulan revisi aturan.

Batas yang dikodekan di sini (bukan di prompt):

- **Hanya mengusulkan.** Tidak ada parameter yang diubah di jalur ini; setiap usulan
  berstatus ``butuh_manusia`` dan satu-satunya jalur penerapan adalah
  ``autonomy.apply_proposal`` oleh manusia. Sengaja tidak memakai ``autonomy.propose``
  karena modul itu boleh menerapkan sendiri usulan paper & non-gate — mandat sektor ini
  tidak memberi Beekeeper hak itu.
- **Gagal-tertutup terhadap kill switch.** Saklar aktif ATAU nilainya tak terbaca →
  tidak ada usulan sama sekali (arah sama dengan ``autonomy.propose``).
- **Mengusulkan bukan mengubah ambang.** Parameter ``gate.*`` dan parameter terkunci
  tidak pernah bisa jadi target usulan (ADR-006: ambang gate = hak owner).

Deteksinya deterministik: dua jendela trading tuntas per strategi (basis = lebih tua,
baru = lebih muda). Syarat usulan = expectancy baru negatif, turun cukup jauh dari
basis, dan bedanya bukan derau (|t| Welch ≥ 2 — disiplin yang sama dengan
``measure.report``).

Modul ini murni terhadap sumber data: baris hasil disuplai pemanggil (mis. job worker
dari ledger/backtest). Baris yang belum tereksekusi, tak bertanda strategi, atau tak
bertanda waktu DILUARKAN, bukan dihitung nol — sumber tak terbaca tidak boleh memicu
usulan.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.autonomy import GATE_TERLARANG, kill_switch_aktif
from warroom_core.db import Event, Parameter, Proposal

__all__ = [
    "AMBANG_T",
    "JENDELA",
    "PENURUNAN_R",
    "Usulan",
    "deteksi_penurunan",
    "usulkan",
]

# Ukuran satu jendela, selaras MIN_SAMPEL_AKTIF di strategi_terpilih (bukti, bukan selera).
JENDELA = 20
# Selisih expectancy (R/trade) minimum antar jendela baru supaya layak disebut "turun".
PENURUNAN_R = 0.5
# Bedanya harus nyata, bukan derau — sama dengan disiplin putusan di measure.report.
AMBANG_T = 2.0


@dataclass(frozen=True)
class Usulan:
    """Temuan deteksi satu strategi: dua jendela expectancy yang berbeda nyata."""

    strategi: str
    expectansi_basis_r: float
    expectansi_baru_r: float
    n_basis: int
    n_baru: int
    t: float | None

    def evidence(self) -> dict[str, Any]:
        return {
            "strategi": self.strategi,
            "expectansi_basis_r": round(self.expectansi_basis_r, 3),
            "expectansi_baru_r": round(self.expectansi_baru_r, 3),
            "n_basis": self.n_basis,
            "n_baru": self.n_baru,
            # t tak hingga (jendela tanpa variansi) tidak boleh masuk JSON — tandai
            # pakai bendera; None di sini bermakna "beda tanpa derau", bukan "tak dihitung".
            "t_welch": round(self.t, 2) if self.t is not None and math.isfinite(self.t) else None,
            "signifikan_tanpa_variansi": self.t is not None and math.isinf(self.t),
            "jendela": JENDELA,
            "ambang_penurunan_r": PENURUNAN_R,
        }


def _waktu(nilai: Any) -> datetime | None:
    if isinstance(nilai, datetime):
        return nilai
    if isinstance(nilai, str):
        try:
            return datetime.fromisoformat(nilai.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _t_welch(a: list[float], b: list[float]) -> float | None:
    """t Welch untuk selisih dua rata-rata (None bila tak bisa dihitung)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    se2 = statistics.stdev(a) ** 2 / n1 + statistics.stdev(b) ** 2 / n2
    selisih = statistics.fmean(a) - statistics.fmean(b)
    if se2 == 0:
        # Kedua jendela tanpa variansi (mis. semua TP1 lalu semua SL): selisih rata-rata
        # adalah pergeseran konstanta, bukan derau — t tak hingga untuk selisih apa pun.
        return math.inf if selisih != 0 else 0.0
    return selisih / se2**0.5


def deteksi_penurunan(rows: list[dict[str, Any]]) -> list[Usulan]:
    """Bandingkan dua jendela teratas per strategi; kembalikan yang layak diusulkan.

    Baris wajib punya ``strategi``, ``r`` (R/trade, None = belum tuntas), dan ``ts``.
    Harus ada 2×JENDELA baris tuntas sebelum apa pun disimpulkan — di bawah itu,
    "expectancy turun" hanya derau (lihat syarat n≥20 di strategi_terpilih/measure).
    """
    per_strategi: dict[str, list[tuple[datetime, float]]] = {}
    for row in rows:
        nama = str(str(row.get("strategi", "") or "").strip())
        r = row.get("r")
        waktu = _waktu(row.get("ts"))
        if not nama or r is None or waktu is None:
            continue
        per_strategi.setdefault(nama, []).append((waktu, float(r)))

    usulan: list[Usulan] = []
    for nama, seri in per_strategi.items():
        if len(seri) < 2 * JENDELA:
            continue
        seri.sort(key=lambda x: x[0])
        basis = [v for _, v in seri[-2 * JENDELA : -JENDELA]]
        baru = [v for _, v in seri[-JENDELA:]]
        e_basis, e_baru = statistics.fmean(basis), statistics.fmean(baru)
        t = _t_welch(basis, baru)
        turun_nyata = (e_basis - e_baru) >= PENURUNAN_R and t is not None and abs(t) >= AMBANG_T
        if e_baru < 0 and turun_nyata:
            usulan.append(
                Usulan(
                    strategi=nama,
                    expectansi_basis_r=e_basis,
                    expectansi_baru_r=e_baru,
                    n_basis=len(basis),
                    n_baru=len(baru),
                    t=t,
                )
            )
    return usulan


def usulkan(
    s: SASession,
    u: Usulan,
    *,
    parameter: str,
    nilai_baru: Any,
    alasan: str,
    actor: str = "beekeeper",
) -> dict[str, Any]:
    """Rekam usulan revisi aturan sebagai Proposal yang MENUNGGU persetujuan manusia.

    Mengembalikan {keputusan, sebab, proposal_id, gate}. ``butuh_manusia`` berarti baris
    Proposal tertulis tanpa menyentuh nilai parameter apa pun; ``ditolak`` berarti tidak
    ada yang ditulis (kill switch, target tak terdaftar, gate, atau terkunci).
    """
    if kill_switch_aktif(s):
        return {
            "keputusan": "ditolak",
            "sebab": "kill switch AI aktif atau tak terbaca — tidak ada usulan",
            "proposal_id": None,
            "gate": "",
        }
    p = s.scalar(select(Parameter).where(Parameter.name == parameter))
    if p is None:
        return {
            "keputusan": "ditolak",
            "sebab": f"parameter '{parameter}' tidak terdaftar",
            "proposal_id": None,
            "gate": "",
        }
    if parameter in GATE_TERLARANG or parameter.startswith("gate."):
        return {
            "keputusan": "ditolak",
            "sebab": "menyentuh ambang gate/rumus BE — hanya manusia (ADR-006)",
            "proposal_id": None,
            "gate": "",
        }
    if p.locked:
        return {
            "keputusan": "ditolak",
            "sebab": "parameter terkunci (locked)",
            "proposal_id": None,
            "gate": "",
        }

    pr = Proposal(
        parameter_name=parameter,
        from_json=p.value_json,
        to_json=nilai_baru,
        reason=alasan,
        evidence_json=u.evidence(),
        gate_verdict="",
        # Selalu menunggu: Beekeeper tidak punya jalur penerapan otomatis.
        status="butuh_manusia",
    )
    s.add(pr)
    s.add(
        Event(
            type="beekeeper.usulan",
            actor=actor,
            payload_json={
                "strategi": u.strategi,
                "parameter": parameter,
                "dari": p.value_json,
                "ke": nilai_baru,
                "evidence": u.evidence(),
            },
            fact_ids=[],
            severity="warning",
        )
    )
    s.flush()
    return {
        "keputusan": "butuh_manusia",
        "sebab": "usulan Beekeeper selalu menunggu persetujuan manusia",
        "proposal_id": pr.id,
        "gate": "",
    }
