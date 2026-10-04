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


def cek_produksi(home: Path | None = None) -> list[tuple[str, float, float]]:
    from ..collectors.azure_watch import umur_file as _umur_radar

    h = Path(home or Path.home())
    return [
        ("snapshot", umur(h / "live-trading/state/snapshot.json"), 1200.0),
        ("verdicts", umur(h / "live-trading/state/verdicts.jsonl"), 2400.0),
        ("gmgn_siklus", umur(h / "gmgn-paper/state/cycle.log"), 4200.0),
        ("lp_mark", umur(h / "gmgn-scan/lp_mark.log"), 93600.0),
        # cache ditulis tiap snapshot sukses baca radar Azure (timer 15 mnt)
        ("radar_azure", _umur_radar(h / "live-trading/state/radar_cache.json"), 3600.0),
    ]


if __name__ == "__main__":
    for baris in jalankan(cek_produksi()):
        print(baris)
