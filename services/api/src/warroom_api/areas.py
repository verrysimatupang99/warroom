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
        # sinyal+entry setup & akurasi per strategi (mesin pasar.py, 6 Okt)
        "crypto_sinyal", "pasar_akurasi", "dompet",
        # kind `signal` diterbitkan job `signal-sync` (bukan bagian snapshot).
        # UI sudah mendeklarasikan topik `signal.` untuk area ini sejak awal.
        "signal",
    ),
    "idx": (
        "bagian", "idx_posisi", "idx_ledger", "idx_equity", "idx_risiko",
        "idx_akurasi", "idx_sinyal", "pasar_akurasi", "bandarmologi_skor", "dompet",
    ),
    "forex": (
        "bagian", "forex_posisi", "forex_ledger", "forex_equity", "forex_risiko",
        "forex_sinyal", "pasar_akurasi", "dompet",
    ),
    "gmgn": (
        "bagian", "gmgn", "radar", "lp_paper", "lp_mark",
        "gmgn_posisi", "gmgn_ledger", "gmgn_equity", "gmgn_risiko", "pasar_akurasi",
        "dompet", "lp_verifikasi",
    ),
    "polymarket": (
        "bagian", "poly_paper", "lp_paper", "equity", "ledger",
        "poly_posisi", "poly_ledger", "poly_equity", "poly_risiko", "pasar_akurasi", "dompet",
    ),
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
    # Narasi LLM per market (6 Okt): kind `ai.brief`, key = nama area. Ditulis job
    # `llm-brief-<market>`; hanya tampil bila ada — tidak ada fakta = tidak ada kartu.
    "crypto": (("ai.brief", "crypto"),),
    "idx": (("ai.brief", "idx"),),
    "forex": (("ai.brief", "forex"),),
    "gmgn": (("ai.brief", "gmgn"),),
}

# Kind yang SELURUH faktanya milik satu area (banyak kunci, mis. `signal/AAVEUSDT`,
# `signal/TIAUSDT`, …). Sebelumnya mustahil didaftarkan lewat AREA_EXTRA yang memakai
# pasangan (kind, key) tetap — akibatnya daftar `AREA_KEYS["crypto"]` memuat "signal"
# tapi fakta itu TIDAK PERNAH sampai ke UI (temuan audit 7 Okt).
AREA_KIND: dict[str, tuple[str, ...]] = {
    "crypto": ("signal",),
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


def facts_for_area(
    s: SASession,
    area: str,
    now: datetime | None = None,
    *,
    terbaru: dict[str, Fact] | None = None,
    extra_cache: dict[str, dict[str, Fact]] | None = None,
) -> dict[str, Any]:
    """Fakta satu area. Area tak dikenal → daftar kunci area yang ada (bukan error 500).

    ``terbaru``/``extra_cache`` opsional: dipakai pemanggil batch (``areas_summary``)
    supaya `latest_facts` tidak dijalankan ulang per area (N+1 — temuan 5 Okt 2026).
    """
    t = now or datetime.now(UTC)
    kunci_area = AREA_KEYS.get(area)
    if terbaru is None:
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
        if extra_cache is not None and kind not in extra_cache:
            extra_cache[kind] = latest_facts(s, kind)
        f = (extra_cache[kind] if extra_cache is not None else latest_facts(s, kind)).get(key)
        if f is not None:
            extra.append(f)
    # Seluruh fakta per kind (mis. semua `signal/<PAIR>`). Dibatasi yang TTL-nya belum
    # lewat: kandidat 45 jam dengan TTL 6 jam BUKAN sinyal aktif — menyajikannya sama
    # dengan berbohong soal kesegaran. Yang basi tetap bisa diperiksa lewat /freshness.
    for kind in AREA_KIND.get(area, ()):
        if extra_cache is not None and kind not in extra_cache:
            extra_cache[kind] = latest_facts(s, kind)
        semua = extra_cache[kind] if extra_cache is not None else latest_facts(s, kind)
        for f in semua.values():
            obs = f.observed_at if f.observed_at.tzinfo else f.observed_at.replace(tzinfo=UTC)
            if (t - obs).total_seconds() <= f.ttl_s:
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
    """Ringkas tiap area: berapa fakta, berapa basi, kapan diperbarui terakhir.

    `latest_facts` dijalankan SEKALI untuk semua area (dulu sekali per area → 8 statement
    per permintaan; temuan N+1 5 Okt 2026). Hasil akhir identik dengan versi lama.
    """
    t = now or datetime.now(UTC)
    terbaru = latest_facts(s)
    extra_cache: dict[str, dict[str, Fact]] = {}
    out: list[dict[str, Any]] = []
    for area in AREA_KEYS:
        info = facts_for_area(s, area, t, terbaru=terbaru, extra_cache=extra_cache)
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