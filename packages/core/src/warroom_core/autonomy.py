"""Bounded autonomy (P5): registry parameter, usulan berbatas, gate keputusan, kill switch.

Batas yang dikodekan di sini (bukan di prompt):

- **`locked`** → parameter tidak bisa diusulkan sama sekali.
- **di luar `bounds`** → usulan ditolak + alasan tercatat (bukti nyata dari proyek Polymarket:
  ``weights.book 0,602`` → ``di_luar_bounds``).
- **menyentuh live atau ambang gate** → `prohibited` (harus manusia/owner).
- **paper & non-gate** → boleh diterapkan otomatis, tetap dengan bukti + hash konfigurasi.
- Setiap usulan menyimpan bukti (`n`, `win`, `be`, `ci`) dan keputusan gate.

Aturan mutlak: agen **tidak pernah** mengubah ambang gate atau rumus BE.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from warroom_core.db import Event, Parameter, Proposal
from warroom_core.gate import DEFAULT_CI, DEFAULT_MIN_N, GateInput, evaluate

__all__ = [
    "GATE_TERLARANG",
    "KEPUTUSAN_AI",
    "SEED",
    "kill_switch_aktif",
    "putuskan_usulan",
    "rollback",
    "seed_parameters",
    "set_kill_switch",
    "terapkan",
    "usulkan",
]

KEPUTUSAN_AI = Literal["diterapkan", "ditolak", "butuh_manusia", "prohibited"]

# Nama parameter yang menyentuh ambang gate/rumus BE — TIDAK BOLEH disentuh agen.
GATE_TERLARANG = ("gate.min_n", "gate.ci", "gate.be", "gate.rumus_be", "fee.rumpus")


@dataclass(frozen=True)
class Seed:
    """Parameter awal + batasnya. Angka batas diambil dari `04-lapisan-ai.md` §5."""

    name: str
    value: Any
    bounds: tuple[float, float] | None = None
    scope: str = "paper"
    locked: bool = False
    note: str = ""


# Nilai awal = nilai nyata agen Polymarket (dari agent-upgrades/lessons), bukan karangan.
SEED: tuple[Seed, ...] = (
    Seed(
        "agent.threshold", 0.82, (0.5, 0.9), "paper", False,
        "ambang skor agen (bukan ambang gate statistik)",
    ),
    Seed("agent.weights.mom", 0.305, (0.1, 0.8), "paper", False, "bobot momentum"),
    Seed("agent.weights.book", 0.594, (0.0, 0.6), "paper", False, "bobot buku order"),
    Seed("agent.weights.band", 0.121, (0.0, 0.5), "paper", False, "bobot pita harga"),
    Seed("risk.sizeUsd", 5.0, (1.0, 10.0), "paper", False, "ukuran per entry (USD)"),
    Seed("risk.maxOpen", 1, (1, 4), "paper", False, "posisi terbuka bersamaan"),
    Seed("mode", "paper", None, "live", True, "mode eksekusi — hanya owner"),
    Seed("gate.min_n", DEFAULT_MIN_N, None, "live", True, "ambang gate — hanya manusia"),
    Seed("gate.ci", DEFAULT_CI, None, "live", True, "tingkat kepercayaan gate — hanya manusia"),
    Seed("ai.kill_switch", False, None, "platform", False, "true = semua peran tulis AI berhenti"),
)


def seed_parameters(s: SASession) -> list[str]:
    """Daftarkan parameter yang belum ada. Nilai yang sudah ada TIDAK ditimpa."""
    ada = {p.name for p in s.scalars(select(Parameter)).all()}
    dibuat: list[str] = []
    for sp in SEED:
        if sp.name in ada:
            continue
        s.add(
            Parameter(
                name=sp.name,
                scope=sp.scope,
                value_json=sp.value,
                bounds_json=list(sp.bounds) if sp.bounds else None,
                locked=sp.locked,
                note=sp.note,
            )
        )
        dibuat.append(sp.name)
    s.flush()
    return dibuat


def _dalam_batas(nilai: Any, bounds: Any) -> bool:
    if bounds is None:
        return True
    if not isinstance(nilai, (int, float)) or isinstance(nilai, bool):
        return False
    lo, hi = bounds[0], bounds[1]
    return lo <= float(nilai) <= hi


def hash_konfigurasi(s: SASession) -> str:
    """Hash seluruh parameter (untuk jejak konfigurasi hasil)."""
    data = {p.name: p.value_json for p in s.scalars(select(Parameter).order_by(Parameter.name)).all()}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _sanitasi_split(s: SASession, evidence: dict[str, Any] | None) -> str | None:
    if not evidence:
        return None
    split_ev = evidence.get("split")
    if split_ev:
        from warroom_core import splits as _splits

        if _splits.split_untuk_gate(s, str(split_ev)) is None:
            return None
        return str(split_ev)
    return None


def putuskan_usulan(
    s: SASession,
    nama: str,
    nilai_baru: Any,
    *,
    evidence: dict[str, Any] | None = None,
) -> tuple[KEPUTUSAN_AI, str]:
    """Tentukan keputusan untuk satu usulan **tanpa** menerapkannya.

    Urutan pemeriksaan sengaja: terlarang → terkunci → di luar batas → butuh manusia → boleh.
    """
    p = s.scalar(select(Parameter).where(Parameter.name == nama))
    if p is None:
        return "ditolak", f"parameter '{nama}' tidak terdaftar"
    if nama in GATE_TERLARANG or nama.startswith("gate."):
        return "prohibited", "menyentuh ambang gate/rumus BE — hanya manusia (owner)"
    if p.locked:
        return "prohibited", "parameter terkunci (locked)"
    if not _dalam_batas(nilai_baru, p.bounds_json):
        return "ditolak", f"di_luar_bounds ({nilai_baru!r} vs {p.bounds_json!r})"
    if p.scope == "live":
        return "butuh_manusia", "menyentuh scope live — wajib keputusan manusia"

    # Bukti wajib untuk perubahan angka: tanpa n/win/be, usulan tidak bisa dinilai.
    if isinstance(nilai_baru, (int, float)) and not isinstance(nilai_baru, bool):
        if not evidence or not all(k in evidence for k in ("n", "win", "be")):
            return "ditolak", "bukti kurang: butuh n, win, be (dan split beku) sebelum mengubah angka"
        # "frozen:<id>" hanya bermakna bila id itu terdaftar. Kalau tidak terdaftar, buang
        # labelnya supaya gate menolak — bukan meloloskan split yang dikarang (ADR-003).
        split_ev = _sanitasi_split(s, evidence)
        g = evaluate(
            GateInput(
                n=int(evidence["n"]),
                win=int(evidence["win"]),
                be=float(evidence["be"]),
                ci=float(evidence.get("ci", DEFAULT_CI)),
                split=split_ev,
                label=evidence.get("label", "konfirmasi"),
            )
        )
        if g.verdict == "insufficient":
            return "ditolak", f"gate insufficient: {g.reason}"
    return "diterapkan", "paper & non-gate: boleh diterapkan otomatis"


def usulkan(
    s: SASession,
    nama: str,
    nilai_baru: Any,
    *,
    alasan: str,
    evidence: dict[str, Any] | None = None,
    actor: str = "learner",
    auto: bool = True,
) -> dict[str, Any]:
    """Catat usulan, putuskan, dan (bila boleh) terapkan. Selalu meninggalkan jejak."""
    p = s.scalar(select(Parameter).where(Parameter.name == nama))
    if p is None:
        raise ValueError(f"parameter '{nama}' tidak terdaftar")
    # Pagar kill switch (temuan 5 Okt 2026): saklar aktif ATAU tak terbaca → tidak ada
    # usulan sama sekali. Pagar ini di dalam `usulkan` supaya pemanggil yang lupa memeriksa
    # sendiri (mis. jalur baru) tetap gagal-tertutup.
    if kill_switch_aktif(s):
        return {
            "keputusan": "ditolak",
            "sebab": "kill switch AI aktif atau tak terbaca — tidak ada usulan",
            "proposal_id": None,
            "gate": "",
        }
    keputusan, sebab = putuskan_usulan(s, nama, nilai_baru, evidence=evidence)

    verdict_gate = ""
    if evidence and all(k in evidence for k in ("n", "win", "be")):
        split_ev = _sanitasi_split(s, evidence)
        verdict_gate = evaluate(
            GateInput(
                n=int(evidence["n"]),
                win=int(evidence["win"]),
                be=float(evidence["be"]),
                ci=float(evidence.get("ci", DEFAULT_CI)),
                split=split_ev,
                label=evidence.get("label", "konfirmasi"),
            )
        ).verdict

    pr = Proposal(
        parameter_name=nama,
        from_json=p.value_json,
        to_json=nilai_baru,
        reason=alasan,
        evidence_json=evidence or {},
        gate_verdict=verdict_gate,
        status=keputusan,
        rejected_reason="" if keputusan == "diterapkan" else sebab,
        decided_by=actor if keputusan == "diterapkan" else None,
        decided_at=datetime.now(UTC) if keputusan == "diterapkan" else None,
    )
    s.add(pr)
    s.flush()

    if keputusan == "diterapkan" and auto:
        pr.applied_at = datetime.now(UTC)
        p.value_json = nilai_baru
        pr.config_hash = hash_konfigurasi(s)

    s.add(
        Event(
            type="proposal.decided" if keputusan == "diterapkan" else "proposal.rejected",
            actor=actor,
            payload_json={
                "parameter": nama,
                "dari": pr.from_json,
                "ke": nilai_baru,
                "keputusan": keputusan,
                "sebab": sebab,
                "gate": verdict_gate,
            },
            fact_ids=[],
            severity="info" if keputusan == "diterapkan" else "warning",
        )
    )
    s.flush()
    return {"keputusan": keputusan, "sebab": sebab, "proposal_id": pr.id, "gate": verdict_gate}


def terapkan(s: SASession, proposal_id: int, *, actor: str = "owner") -> bool:
    """Terapkan usulan yang menunggu manusia (mis. scope live). Mencatat aktor."""
    pr = s.get(Proposal, proposal_id)
    if pr is None or pr.status != "butuh_manusia":
        return False
    p = s.scalar(select(Parameter).where(Parameter.name == pr.parameter_name))
    if p is None or p.locked:
        return False
    p.value_json = pr.to_json
    pr.status = "diterapkan"
    pr.decided_by = actor
    pr.decided_at = datetime.now(UTC)
    pr.applied_at = datetime.now(UTC)
    pr.config_hash = hash_konfigurasi(s)
    s.add(
        Event(
            type="proposal.applied",
            actor=actor,
            payload_json={"parameter": pr.parameter_name, "ke": pr.to_json,
                          "proposal_id": pr.id, "oleh_manusia": True},
            fact_ids=[],
            severity="warning",
        )
    )
    s.flush()
    return True


def rollback(s: SASession, proposal_id: int, *, actor: str = "owner") -> bool:
    """Kembalikan nilai sebelum usulan; tercatat sebagai event."""
    pr = s.get(Proposal, proposal_id)
    if pr is None or pr.applied_at is None:
        return False
    p = s.scalar(select(Parameter).where(Parameter.name == pr.parameter_name))
    if p is None:
        return False
    p.value_json = pr.from_json
    pr.status = "dibatalkan"
    pr.applied_at = None
    pr.config_hash = hash_konfigurasi(s)
    s.add(
        Event(
            type="proposal.rolled_back",
            actor=actor,
            payload_json={"parameter": pr.parameter_name, "kembali_ke": pr.from_json},
            fact_ids=[],
            severity="warning",
        )
    )
    s.flush()
    return True


# --- kill switch AI (P5-T5) -------------------------------------------------------------


def kill_switch_aktif(s: SASession) -> bool:
    """True = semua peran tulis AI berhenti; peran baca tetap jalan.

    Gagal-tertutup (temuan 5 Okt 2026): baris hilang ATAU nilainya bukan boolean False
    dihitung AKTIF. Hanya `false` eksplisit yang membuka tulisan AI — arah yang sama
    dengan default `paused=True` saat `operator.json` tak terbaca (live.py). Sebelumnya
    baris hilang dibaca sebagai "saklar mati", yaitu izin menulis justru saat statusnya
    paling tak bisa dipercaya.
    """
    p = s.scalar(select(Parameter).where(Parameter.name == "ai.kill_switch"))
    if p is None:
        return True
    return p.value_json is not False


def set_kill_switch(s: SASession, aktif: bool, *, actor: str = "owner") -> bool:
    """Nyalakan/matikan kill switch AI. Selalu tercatat (audit)."""
    p = s.scalar(select(Parameter).where(Parameter.name == "ai.kill_switch"))
    if p is None:
        return False
    sebelumnya = bool(p.value_json)
    p.value_json = bool(aktif)
    s.add(
        Event(
            type="ai.kill_switch",
            actor=actor,
            payload_json={"dari": sebelumnya, "ke": bool(aktif)},
            fact_ids=[],
            severity="warning" if aktif else "info",
        )
    )
    s.flush()
    return True