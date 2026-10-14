"""Pod Poly: analis arm mirror + TP, lead merangkum."""

from __future__ import annotations

from typing import Any

from . import AnalysisResult, LaporanPod, _rangkum


def analyze_arm(snap: dict[str, Any]) -> AnalysisResult:
    poly = snap.get("poly_paper") or {}
    arms = poly.get("arms") or []
    if not arms:
        return AnalysisResult("arm", "abu", ["belum ada arm mirror"])
    plus = [a for a in arms if (a.get("pnl") or 0) > 0]
    det = ", ".join(f"{a.get('nama')} {a.get('pnl', 0):+.2f}" for a in arms[:4])
    st = "hijau" if len(plus) >= 2 else "kuning"
    return AnalysisResult("arm", st, [f"{len(plus)}/{len(arms)} arm profit: {det}"])


def analyze_tp(snap: dict[str, Any]) -> AnalysisResult:
    poly = snap.get("poly_paper") or {}
    total = sum(float(a.get("pnl") or 0) for a in poly.get("arms") or [])
    st = "hijau" if total > 0 else ("kuning" if total == 0 else "merah")
    return AnalysisResult("tp", st, [f"total {total:+.2f} USD paper"])


def lead(snap: dict[str, Any]) -> LaporanPod:
    analis = [analyze_arm(snap), analyze_tp(snap)]
    return LaporanPod(
        pod="poly",
        status=_rangkum(analis),
        ringkas=[a.baris() for a in analis],
        analis=analis,
    )
