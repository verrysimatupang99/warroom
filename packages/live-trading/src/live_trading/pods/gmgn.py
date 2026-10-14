"""Pod GMGN: analis radar + LP, lead merangkum."""

from __future__ import annotations

from typing import Any

from . import AnalysisResult, LaporanPod, _rangkum


def analyze_radar(snap: dict[str, Any]) -> AnalysisResult:
    r = snap.get("radar") or {}
    chains = r.get("chains") or []
    prime = [c for c in chains if c.get("window") == "PRIME"]
    if not prime:
        return AnalysisResult("radar", "kuning", ["tidak ada chain PRIME"])
    det = ", ".join(f"{c.get('chain')} V/L {c.get('avg_vl')}" for c in prime[:3])
    return AnalysisResult("radar", "hijau", [f"PRIME: {det}"])


def analyze_lp(snap: dict[str, Any]) -> AnalysisResult:
    lp = snap.get("lp_paper") or {}
    pos = lp.get("posisi") or []
    if not pos:
        return AnalysisResult("lp", "abu", ["tidak ada posisi paper"])
    keluar = [x for x in pos if x.get("verdict") == "KELUAR"]
    if keluar:
        det = "; ".join(f"{x.get('symbol')} CABUT ({x.get('alasan')})" for x in keluar)
        return AnalysisResult("lp", "kuning", [det])
    if any(x.get("verdict") is None for x in pos):
        return AnalysisResult("lp", "abu", ["verdict keluar setelah cron mark"])
    return AnalysisResult("lp", "hijau", [f"{len(pos)} posisi TAHAN"])


def lead(snap: dict[str, Any]) -> LaporanPod:
    analis = [analyze_radar(snap), analyze_lp(snap)]
    return LaporanPod(
        pod="gmgn",
        status=_rangkum(analis),
        ringkas=[a.baris() for a in analis],
        analis=analis,
    )
