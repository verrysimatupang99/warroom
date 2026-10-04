"""Pod IDX: analis mirror + konsentrasi. MENTOK FASE 2 — tanpa auto-order."""

from __future__ import annotations

from typing import Any

from . import HasilAnalis, LaporanPod, _rangkum

FASE_CAP = "cap Fase 2: order disiapkan, eksekusi manual di broker"


def analis_mirror(snap: dict[str, Any]) -> HasilAnalis:
    m = ((snap.get("bagian") or {}).get("idx616")) or {}
    buka = m.get("terbuka") or []
    unik = {(x.get("ticker"), x.get("setup")) for x in buka}
    if not buka:
        return HasilAnalis("mirror", "abu", ["tidak ada sinyal terbuka", FASE_CAP])
    return HasilAnalis(
        "mirror", "hijau", [f"{len(unik)} unik/{len(buka)} event", FASE_CAP]
    )


def analis_konsentrasi(snap: dict[str, Any]) -> HasilAnalis:
    m = ((snap.get("bagian") or {}).get("idx616")) or {}
    ps = m.get("per_setup") or {}
    tot = sum(float(v.get("r") or 0) for v in ps.values())
    if not ps or tot <= 0:
        return HasilAnalis("konsentrasi", "abu", ["belum ada data tutup"])
    top_k, top_v = max(ps.items(), key=lambda kv: float(kv[1].get("r") or 0))
    share = float(top_v.get("r") or 0) / tot * 100
    st = "kuning" if share > 60 else "hijau"
    return HasilAnalis(
        "konsentrasi", st, [f"{top_k} {share:.0f}% dari total R"]
    )


def lead(snap: dict[str, Any]) -> LaporanPod:
    analis = [analis_mirror(snap), analis_konsentrasi(snap)]
    return LaporanPod(
        pod="idx", status=_rangkum(analis), ringkas=[a.baris() for a in analis], analis=analis
    )
