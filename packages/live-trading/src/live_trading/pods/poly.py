"""Pod Poly: analis arm mirror + TP, lead merangkum."""

from __future__ import annotations

from typing import Any

from . import HasilAnalis, LaporanPod, _rangkum


def analis_arm(snap: dict[str, Any]) -> HasilAnalis:
    poly = snap.get("poly_paper") or {}
    arms = poly.get("arms") or []
    if not arms:
        return HasilAnalis("arm", "abu", ["belum ada arm mirror"])
    plus = [a for a in arms if (a.get("pnl") or 0) > 0]
    det = ", ".join(f"{a.get('nama')} {a.get('pnl', 0):+.2f}" for a in arms[:4])
    st = "hijau" if len(plus) >= 2 else "kuning"
    return HasilAnalis("arm", st, [f"{len(plus)}/{len(arms)} arm profit: {det}"])


def analis_tp(snap: dict[str, Any]) -> HasilAnalis:
    poly = snap.get("poly_paper") or {}
    total = sum(float(a.get("pnl") or 0) for a in poly.get("arms") or [])
    st = "hijau" if total > 0 else ("kuning" if total == 0 else "merah")
    return HasilAnalis("tp", st, [f"total {total:+.2f} USD paper"])


def lead(snap: dict[str, Any]) -> LaporanPod:
    analis = [analis_arm(snap), analis_tp(snap)]
    return LaporanPod(
        pod="poly",
        status=_rangkum(analis),
        ringkas=[a.baris() for a in analis],
        analis=analis,
    )
