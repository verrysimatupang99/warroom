"""Router proxy read-only ke daftar cronjob di node MiniMax (Tencent).

MiniMax menjalankan 49 job cron; 17 aktif, 32 mati, 48 eksekusi terakhir OK,
1 gagal. War Room memakainya sebagai panel operasional: scheduler mana yang
hidup dan job mana yang|last gagal.

Semua akses baca-saja. Router meneruskan ke node MiniMax lewat Tailscale.
"""

from typing import Any

from fastapi import APIRouter

from warroom_api.routers.tencent import _fetch_tencent

router = APIRouter(prefix="/api/v1/cron", tags=["cron"])


@router.get("/summary")
async def cron_summary() -> dict[str, Any]:
    """Ringkasan scheduler: total, aktif, mati, dan status eksekusi terakhir."""
    return await _fetch_tencent("/cron/summary")


@router.get("/jobs")
async def cron_jobs() -> dict[str, Any]:
    """Daftar seluruh job cron beserta jadwal dan statusnya."""
    return await _fetch_tencent("/cron/jobs")


@router.get("/executions")
async def cron_executions() -> dict[str, Any]:
    """Riwayat eksekusi job cron terakhir."""
    return await _fetch_tencent("/cron/executions")


@router.get("/jobs/{job_id}")
async def cron_job(job_id: str) -> dict[str, Any]:
    """Detail satu job cron."""
    return await _fetch_tencent(f"/cron/jobs/{job_id}")
