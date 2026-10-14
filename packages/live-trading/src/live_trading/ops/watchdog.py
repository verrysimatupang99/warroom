"""Watchdog gabungan semua loop: 1 baris bila sehat, sebut nama bila sakit."""

from __future__ import annotations

import time
from pathlib import Path


def umur(path: str | Path) -> float:
    try:
        return time.time() - Path(path).stat().st_mtime
    except OSError:
        return float("inf")


def jalankan(cek: list[tuple[str, float, float]]) -> list[str]:
    """cek = [(nama, umur_detik, batas_detik)]. Sehat: ['SEHAT n/n']."""
    basi = [f"{nama} basi {u / 60:.0f} mnt" for nama, u, b in cek if u > b]
    if not basi:
        return [f"SEHAT {len(cek)}/{len(cek)}"]
    return [f"AWAS {len(cek) - len(basi)}/{len(cek)}", *basi]


def check_production(home: Path | None = None) -> list[tuple[str, float, float]]:
    h = Path(home or Path.home())
    return [
        ("snapshot", umur(h / "live-trading/state/snapshot.json"), 1200.0),
        ("verdicts", umur(h / "live-trading/state/verdicts.jsonl"), 2400.0),
        ("gmgn_siklus", umur(h / "gmgn-paper/state/cycle.log"), 4200.0),
        ("lp_mark", umur(h / "live-trading/state/lp_mark_terakhir.json"), 93600.0),
        # Radar kini LOKAL (recreate 6 Okt): ditulis tiap kali `lt radar-update` jalan.
        ("radar_lokal", umur(h / "live-trading/state/radar_state.json"), 3600.0),
    ]


if __name__ == "__main__":
    for baris in jalankan(check_production()):
        print(baris)
