"""Endpoint baca per-area (P1-T6).

Setiap angka dikembalikan **apa adanya** dari `facts` (kind `snapshot`) lengkap dengan
metadata: `fact_id`, `source`, `observed_at`, `ttl_s`, `status` (segar/basi). Tidak ada
perhitungan ulang, tidak ada nilai default — kunci yang tidak ada **tidak muncul** (UI
wajib menampilkan `—`, bukan 0).

Pemetaan area→kunci sengaja eksplisit dan tumpang tindih bila memang begitu kenyataannya
(mis. `bagian` dipakai crypto, idx, forex, dan gmgn sekaligus).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Fact

__all__ = ["AREA_KEYS", "areas_summary", "facts_for_area", "latest_facts"]

AREA_KEYS: dict[str, tuple[str, ...]] = {
    "crypto": (
        "bagian", "kandidat", "pengukuran", "backtest",
        "equity", "ledger", "risiko", "posisi", "pod_llm",
        # kind `signal` diterbitkan job `signal-sync` (bukan bagian snapshot).
        # UI sudah mendeklarasikan topik `signal.` untuk area ini sejak awal.
        "signal",
    ),
    "idx": ("bagian", "kandidat", "pengukuran", "bandarmologi"),
    "forex": ("bagian",),
    "gmgn": ("bagian", "gmgn", "radar", "lp_paper"),
    "polymarket": ("bagian", "poly_paper", "lp_paper", "equity", "ledger"),
}

# Fakta dari kind NON-snapshot yang ikut tampil di area. Dipakai gate: GateBlok membaca
# fakta ber-key `verdict`/`gate`, dan fakta itu diterbitkan job `verdict-sync` dengan
# kind `poly.verdict` (bukan bagian dari snapshot domain). `recorder`/`cakupan` dipakai
# DatasetExplorer (P4-T3) — katalog dataset + cakupan baca, dari job `poly-sync`.
AREA_EXTRA: dict[str, tuple[tuple[str, str], ...]] = {
    "polymarket": (
        ("poly.verdict", "verdict"),
        ("poly.dataset", "recorder"),
        ("poly.akses", "cakupan"),
    ),
}


def _row(f: Fact, now: datetime) -> dict[str, Any]:
    umur = (now - f.observed_at).total_seconds()
    return {
        "fact_id": f.id,
        "kind": f.kind,
        "key": f.key,
        "value": f.value_json,
        "source": f.source,
        "observed_at": f.observed_at.isoformat(),
        "ttl_s": f.ttl_s,
        "age_s": round(umur, 1),
        "status": "segar" if umur <= f.ttl_s else "basi",
        "hash": f.hash,
    }


def latest_facts(s: SASession, kind: str = "snapshot") -> dict[str, Fact]:
    """Fakta terbaru per kunci (bukan nilai lama yang menyamar baru: dipilih by observed_at)."""
    sub = (
        select(Fact.key, func.max(Fact.observed_at).label("obs"))
        .where(Fact.kind == kind)
        .group_by(Fact.key)
        .subquery()
    )
    rows = s.scalars(
        select(Fact)
        .join(sub, (Fact.key == sub.c.key) & (Fact.observed_at == sub.c.obs))
        .where(Fact.kind == kind)
    ).all()
    return {f.key: f for f in rows}


def facts_for_area(s: SASession, area: str, now: datetime | None = None) -> dict[str, Any]:
    """Fakta satu area. Area tak dikenal → daftar kunci area yang ada (bukan error 500)."""
    t = now or datetime.now(UTC)
    kunci_area = AREA_KEYS.get(area)
    terbaru = latest_facts(s)
    if kunci_area is None:
        return {
            "area": area,
            "dikenal": False,
            "areas": sorted(AREA_KEYS),
            "facts": [],
            "data": {},
        }
    dipakai = [terbaru[k] for k in kunci_area if k in terbaru]
    # Fakta tambahan dari kind lain (mis. verdict untuk gate). Tidak terbaca → tidak muncul;
    # `kunci_hilang` tetap melaporkan kunci snapshot yang absen.
    extra: list[Fact] = []
    for kind, key in AREA_EXTRA.get(area, ()):
        f = latest_facts(s, kind).get(key)
        if f is not None:
            extra.append(f)
    return {
        "area": area,
        "dikenal": True,
        "kunci_diminta": list(kunci_area),
        "kunci_hilang": [k for k in kunci_area if k not in terbaru],
        "facts": [_row(f, t) for f in [*dipakai, *extra]],
        "data": {f.key: f.value_json for f in [*dipakai, *extra]},
    }


def areas_summary(s: SASession, now: datetime | None = None) -> list[dict[str, Any]]:
    """Ringkas tiap area: berapa fakta, berapa basi, kapan diperbarui terakhir."""
    t = now or datetime.now(UTC)
    out: list[dict[str, Any]] = []
    for area in AREA_KEYS:
        info = facts_for_area(s, area, t)
        basi = sum(1 for f in info["facts"] if f["status"] == "basi")
        terakhir = max((f["observed_at"] for f in info["facts"]), default=None)
        out.append(
            {
                "area": area,
                "fakta": len(info["facts"]),
                "hilang": len(info["kunci_hilang"]),
                "basi": basi,
                "observed_at_terakhir": terakhir,
            }
        )
    return out