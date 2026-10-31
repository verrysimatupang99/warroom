"""Status operasional: unit systemd, timer, dan kesegaran berkas data.

Dipisah dari sistem.py supaya endpoint baca-saja ini tidak menambah impor DB
ke jalur yang dipanggil tiap detik oleh dashboard.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from warroom_api.auth import current_user

router = APIRouter()

# Unit yang relevan untuk dashboard. Bukan daftar semua unit di host —
# hanya yang menjalankan War Room dan turunannya.
UNIT = [
    "warroom-api",
    "warroom-web",
    "warroom-worker",
    "warroom-laya-verdict.timer",
    "warroom-pantau-tick.timer",
    "warroom-panel-sim.timer",
    "warroom-momentum-paper.timer",
    "warroom-backup-postgres.timer",
    "nginx",
    "poly-agent",
]

# Berkas data yang umurnya perlu dipantau (detik).
BERKAS = {
    "/var/lib/warroom/telemetry_log.csv": 120,
    "/var/lib/warroom/fills.csv": 86400,
    "/var/lib/warroom/panels.json": 120,
    "/var/lib/warroom/momentum_paper.json": 7200,
    "/var/lib/warroom/laya_verdict.json": 600,
}


async def _systemctl(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "systemctl",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    return out.decode().strip()


async def _status_unit(nama: str) -> dict[str, Any]:
    aktif = await _systemctl("is-active", nama)
    return {"unit": nama, "aktif": aktif or "unknown", "sehat": aktif == "active"}


@router.get("/api/v1/sistem/status", dependencies=[Depends(current_user)])
async def status_sistem() -> dict[str, Any]:
    """Ringkasan hidup/mati unit dan umur berkas data."""
    unit = await asyncio.gather(*(_status_unit(u) for u in UNIT))

    sekarang = time.time()
    berkas: list[dict[str, Any]] = []
    for jalur, ambang in BERKAS.items():
        p = Path(jalur)
        if not p.exists():
            berkas.append({"berkas": jalur, "ada": False, "umur_s": None, "basi": True})
            continue
        umur = int(sekarang - p.stat().st_mtime)
        berkas.append(
            {"berkas": jalur, "ada": True, "umur_s": umur, "basi": umur > ambang, "ambang_s": ambang}
        )

    sehat = sum(1 for u in unit if u["sehat"])
    return {
        "waktu": int(sekarang),
        "unit_total": len(unit),
        "unit_sehat": sehat,
        "unit": unit,
        "berkas": berkas,
    }
