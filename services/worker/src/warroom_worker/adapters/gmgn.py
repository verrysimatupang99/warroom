"""Adapter GMGN (baca-saja) — P4-T4.

Sumber: ``~/gmgn-paper/state`` (lokal) dan **state radar lokal**
(``~/live-trading/state/radar_state.json``, hasil `lt radar-update`). Tidak ada SSH,
tidak ada perubahan apa pun di host lain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from warroom_worker.adapters.io import baca_json, ringkas_dir

__all__ = ["gmgn_ringkas", "radar_ringkas"]

GMGN_STATE = "~/gmgn-paper/state"
RADAR_STATE = "~/live-trading/state/radar_state.json"


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


def radar_ringkas(state_path: str | None = None) -> dict[str, Any]:
    """Radar rantai dibaca dari state **lokal** hasil `lt radar-update`.

    Sejak 6 Okt 2026 radar dijalankan di Webdock sendiri (recreate dari VM Azure yang
    akan dimatikan) — tidak ada lagi SSH. Kesegaran tetap dibawa apa adanya: ``mtime``
    dari ``diambil_epoch`` (kapan radar benar-benar jalan), bukan waktu berkas disentuh.
    """
    b = baca_json(state_path or RADAR_STATE, pakai_sudo=False)
    if not b.ok:
        return {"status": b.status, "path": b.path, "detail": b.detail}
    data = b.data if isinstance(b.data, dict) else {}
    diambil = data.get("diambil_epoch")
    chains = data.get("chains") if isinstance(data.get("chains"), list) else None
    return {
        "status": "ok",
        "path": b.path,
        "mtime": b.mtime.isoformat() if b.mtime else None,
        "diambil_epoch": diambil,
        "sha256": b.sha256,
        "data": data,
        "chains": chains,
        "sumber": "lokal",  # radar lokal Webdock, bukan cache host lain
    }