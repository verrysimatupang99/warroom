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
    cek: list[tuple[str, float, float]] = [
        ("snapshot", umur(h / "live-trading/state/snapshot.json"), 1200.0),
        ("verdicts", umur(h / "live-trading/state/verdicts.jsonl"), 2400.0),
    ]
    # gmgn paper & LP paper: masih RENCANA, sumber datanya belum dibangun.
    # Cek sengaja digerbang keberadaan berkas: kalau folder/berkasnya belum ada,
    # itu fitur yang belum jadi — bukan kegagalan, jadi tidak boleh memunculkan
    # AWAS permanen yang menyamarkan kegagalan nyata. Begitu sumbernya ada,
    # cek otomatis aktif dan langsung mendeteksi kalau datanya berhenti mengalir.
    if (h / "gmgn-paper/state").exists():
        cek.append(("gmgn_siklus", umur(h / "gmgn-paper/state/cycle.log"), 4200.0))
    if (h / "live-trading/state/lp_mark_terakhir.json").exists():
        cek.append(("lp_mark", umur(h / "live-trading/state/lp_mark_terakhir.json"), 93600.0))
    cek.append(
        # Radar kini LOKAL (recreate 6 Okt): ditulis tiap kali `lt radar-update` jalan.
        ("radar_lokal", umur(h / "live-trading/state/radar_state.json"), 3600.0)
    )
    # Agen trading di Azure. Berkas denyut ditulis timer root mt5-beat
    # (lihat /usr/local/sbin/mt5-beat.sh) HANYA bila telemetri EA masih
    # segar <=120 dtk. Unit ini tidak punya grup sudo, jadi berkas perantara
    # ini menggantikan pembacaan access.log langsung.
    #
    # Gerbang "EA dimatikan" (9 Nov 2026): EA WarRoom_AutoTrader di Azure
    # `mt5-trader-vm` berhenti melapor sejak 31 Okt 2026 karena subscription
    # Azure di-disable. Berkas denyut tetap ada (basi), jadi tanpa gerbang ini
    # watchdog berteriak "mt5_telemetri basi ~11.800 mnt" tiap 30 menit
    # selamanya — AWAS permanen yang justru menyamarkan kegagalan nyata
    # (alasan yang sama dengan gerbang gmgn_siklus / lp_mark di atas).
    # Hapus berkas penanda ini begitu EA dinyalakan lagi; cek otomatis aktif.
    if not (h / "live-trading/state/mt5_ea_offline").exists():
        cek.append(("mt5_telemetri", umur(h / "live-trading/state/mt5_telemetri.beat"), 600.0))
    return cek


if __name__ == "__main__":
    for baris in jalankan(check_production()):
        print(baris)
