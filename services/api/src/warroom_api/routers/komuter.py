"""Router proxy /api/v1/komuter → backend KOMUTER (RUTE.JKT).

Sejarah singkat (jangan diulang): router ini dulu meng-``import`` modul Komuter
secara in-process dari ``/home/admin/rute-jkt/backend``. Ketika proyek itu
dipindah ke server Pakaicloud (``/opt/komuter``), path lama hilang dan setiap
endpoint melempar ``ModuleNotFoundError: No module named 'app'`` → HTTP 500.

Sekarang router meneruskan lewat HTTP ke backend Komuter yang hidup. Backend
default adalah NAT publik Pakaicloud (socat :20272 → :8930). Atur lewat env
``KOMUTER_BASE_URL`` bila alamatnya berubah (mis. pindah domain).

Prinsip:
- tidak ada duplikasi kode Komuter di server ini;
- kalau backend tidak terjangkau, laporkan ``tersedia: false`` + alasannya,
  bukan mengarang angka.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

KOMUTER_BASE_URL = os.environ.get("KOMUTER_BASE_URL", "http://31.58.103.2:20272").rstrip("/")
TIMEOUT_S = float(os.environ.get("KOMUTER_TIMEOUT_S", "12"))

router = APIRouter(prefix="/api/v1/komuter", tags=["komuter"])


async def _teruskan(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET ke backend Komuter, kembalikan JSON apa adanya.

    Kesalahan backend dibedakan dari kesalahan jaringan supaya operator tahu
    apakah yang bermasalah Komuter atau pipa War Room.
    """
    url = f"{KOMUTER_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as klien:
            r = await klien.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "tersedia": False,
                "sumber": KOMUTER_BASE_URL,
                "alasan": f"timeout {TIMEOUT_S}s menunggu backend Komuter",
                "error": type(exc).__name__,
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "tersedia": False,
                "sumber": KOMUTER_BASE_URL,
                "alasan": "backend Komuter tidak terjangkau",
                "error": type(exc).__name__,
            },
        ) from exc

    if r.status_code >= 400:
        raise HTTPException(
            status_code=r.status_code,
            detail={
                "tersedia": True,
                "sumber": KOMUTER_BASE_URL,
                "alasan": f"backend Komuter menjawab HTTP {r.status_code}",
                "body": r.text[:400],
            },
        )
    return r.json()


@router.get("/health")
async def komuter_health() -> dict[str, Any]:
    return await _teruskan("/health")


@router.get("/geocode")
async def komuter_geocode(q: str = Query(..., min_length=1)) -> dict[str, Any]:
    return await _teruskan("/geocode", {"q": q})


@router.get("/plan")
async def komuter_plan(
    from_lat: float = Query(...),
    from_lon: float = Query(...),
    to_lat: float = Query(...),
    to_lon: float = Query(...),
    preference: str = Query("TERCEPAT", pattern="^(TERCEPAT|SEDIKIT_TRANSIT)$"),
) -> dict[str, Any]:
    return await _teruskan(
        "/plan",
        {
            "from_lat": from_lat,
            "from_lon": from_lon,
            "to_lat": to_lat,
            "to_lon": to_lon,
            "preference": preference,
        },
    )


@router.get("/stations")
async def komuter_stations(
    kind: str | None = Query(None, description="Filter: KRL, MRT, LRT"),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if kind:
        params["kind"] = kind
    return await _teruskan("/stations", params)
