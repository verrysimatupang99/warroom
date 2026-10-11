"""Eval harness deterministik: golden set per peran + pemeriksa yang sama dengan produksi.

Setiap kasus menjalankan :func:`warroom_llm.pipeline.evaluate_output` (jalur yang sama
dipakai gateway), jadi hasil eval bermakna — bukan pemeriksa terpisah yang bisa menyimpang.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from warroom_llm.facts import FactRef
from warroom_llm.pipeline import evaluate_output

__all__ = ["EvalReport", "GoldenCase", "load_golden", "run_case", "run_suite"]

MIN_KASUS_PER_PERAN = 20


@dataclass(frozen=True)
class GoldenCase:
    id: str
    role: str
    provided_facts: tuple[FactRef, ...]
    existing_fact_ids: frozenset[int]
    candidate: Any
    expect_verdict: str  # ok | rejected
    expect_code: str | None = None


@dataclass(frozen=True)
class EvalReport:
    total: int
    lulus: int
    gagal: int
    per_peran: dict[str, int]
    roles: tuple[str, ...]
    detail_gagal: tuple[dict[str, Any], ...]

    @property
    def ok(self) -> bool:
        return (
            self.gagal == 0
            and len(self.roles) >= 3
            and all(count >= MIN_KASUS_PER_PERAN for count in self.per_peran.values())
        )


def _fact(raw: dict[str, Any]) -> FactRef:
    return FactRef(fact_id=int(raw["fact_id"]), label=str(raw["label"]), text=str(raw["text"]))


def load_golden(path: str | Path) -> list[GoldenCase]:
    kasus: list[GoldenCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        raw = json.loads(line)
        provided = tuple(_fact(f) for f in raw.get("provided_facts") or [])
        existing = raw.get("existing_fact_ids")
        if existing is None:
            existing = [f.fact_id for f in provided]
        kasus.append(
            GoldenCase(
                id=str(raw["id"]),
                role=str(raw["role"]),
                provided_facts=provided,
                existing_fact_ids=frozenset(int(x) for x in existing),
                candidate=raw["candidate"],
                expect_verdict=str(raw["expect"]["verdict"]),
                expect_code=raw["expect"].get("code"),
            )
        )
    return kasus


def run_case(case: GoldenCase, *, env_names: tuple[str, ...] | None = None) -> dict[str, Any]:
    provided = {f.fact_id for f in case.provided_facts}
    if isinstance(case.candidate, str):
        raw = case.candidate
    else:
        raw = json.dumps(case.candidate, ensure_ascii=False)
    decision = evaluate_output(case.role, raw, provided, set(case.existing_fact_ids), env_names=env_names)
    kode = decision.issues[0] if decision.issues else None
    cocok_verdict = decision.verdict == case.expect_verdict
    cocok_kode = True
    if case.expect_code is not None:
        kode_kategori = kode.split(":", 1)[0] if kode else None
        cocok_kode = bool(kode) and (kode_kategori == case.expect_code or kode == case.expect_code)
    return {
        "id": case.id,
        "role": case.role,
        "ok": cocok_verdict and cocok_kode,
        "expect": f"{case.expect_verdict}/{case.expect_code}",
        "got": f"{decision.verdict}/{kode}",
    }


def run_suite(directory: str | Path) -> EvalReport:
    """Jalankan seluruh berkas ``*.jsonl`` di ``directory``; kembalikan rekap per peran."""
    kasus: list[GoldenCase] = []
    for berkas in sorted(Path(directory).glob("*.jsonl")):
        kasus.extend(load_golden(berkas))
    hasil = [run_case(k) for k in kasus]
    per_peran: dict[str, int] = {}
    for k in kasus:
        per_peran[k.role] = per_peran.get(k.role, 0) + 1
    gagal = tuple(h for h in hasil if not h["ok"])
    return EvalReport(
        total=len(hasil),
        lulus=len(hasil) - len(gagal),
        gagal=len(gagal),
        per_peran=per_peran,
        roles=tuple(sorted(per_peran)),
        detail_gagal=gagal,
    )
