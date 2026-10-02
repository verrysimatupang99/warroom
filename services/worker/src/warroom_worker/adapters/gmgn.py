"""Adapter GMGN (baca-saja) — P4-T4.

Sumber: ``~/gmgn-paper/state`` (lokal) dan cache radar Azure yang sudah ada
(``~/live-trading/state/radar_cache.json``). Tidak ada SSH tulis, tidak ada perubahan
apa pun di host Azure/Tencent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from warroom_worker.adapters.io import baca_json, ringkas_dir

__all__ = ["gmgn_ringkas", "radar_ringkas"]

GMGN_STATE = "~/gmgn-paper/state"
RADAR_CACHE = "~/live-trading/state/radar_cache.json"


def gmgn_ringkas(state_dir: str | None = None) -> dict[str, Any]:
    """Ringkasan state GMGN paper: berkas, ukuran, umur. Gagal → status, bukan nol."""
    d = Path(state_dir or GMGN_STATE).expanduser()
    if not d.exists():
        return {"status": "tidak-ada", "dir": str(d)}
    ringkas = ringkas_dir(d, pakai_sudo=False)
    berkas: list[dict[str, Any]] = []
    try:
        for f in sorted(d.glob("*")):
            if f.is_file():
                st = f.stat()
                berkas.append({"nama": f.name, "bytes": st.st_size, "mtime": st.st_mtime})
    except OSError as exc:
        return {"status": "tidak-izin", "dir": str(d), "detail": type(exc).__name__}
    # cycle.lock = penanda proses; run_config = parameter aktif
    kunci = ("run_config.json", "positions.json", "signals.jsonl")
    isi: dict[str, Any] = {}
    for nama in kunci:
        b = baca_json(d / nama, pakai_sudo=False)
        if b.ok:
            isi[nama] = b.data
        else:
            isi[nama] = {"status": b.status}
    return {
        "status": ringkas.get("status", "ok"),
        "dir": str(d),
        "files": ringkas.get("files"),
        "bytes": ringkas.get("bytes"),
        "berkas": berkas[:40],
        "isi": isi,
    }


def radar_ringkas(cache_path: str | None = None) -> dict[str, Any]:
    """Radar Azure dibaca dari cache lokal (pola yang sudah ada) + umurnya.

    Sumber hidupnya di host Azure (baca-saja); yang kita baca di sini adalah cache —
    jadi kesegaran wajib ditampilkan, bukan disembunyikan.
    """
    b = baca_json(cache_path or RADAR_CACHE, pakai_sudo=False)
    if not b.ok:
        return {"status": b.status, "path": b.path, "detail": b.detail}
    return {
        "status": "ok",
        "path": b.path,
        "mtime": b.mtime.isoformat() if b.mtime else None,
        "sha256": b.sha256,
        "data": b.data,
        "sumber": "cache",  # penting: ini cache, bukan bacaan langsung dari Azure
    }