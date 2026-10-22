"""Router proxy / internal handler untuk API KOMUTER (RUTE.JKT).

Menyediakan endpoint geocode, plan, stops, routes, dan health langsung
dari backend lokal berkecepatan tinggi tanpa latency cold-start Vercel.
"""

import sys
from typing import Any

from fastapi import APIRouter, Query

# Ensure komuter backend is importable
KOMUTER_BACKEND = "/home/admin/rute-jkt/backend"
if KOMUTER_BACKEND not in sys.path:
    sys.path.insert(0, KOMUTER_BACKEND)

router = APIRouter(prefix="/api/v1/komuter", tags=["komuter"])


@router.get("/health")
async def komuter_health() -> dict[str, Any]:
    from app.main import health
    return await health()


@router.get("/geocode")
async def komuter_geocode(q: str = Query(..., min_length=1)) -> dict[str, Any]:
    from app.main import geocode
    return await geocode(q=q)


@router.get("/plan")
async def komuter_plan(
    from_lat: float = Query(...),
    from_lon: float = Query(...),
    to_lat: float = Query(...),
    to_lon: float = Query(...),
    preference: str = Query("TERCEPAT", pattern="^(TERCEPAT|SEDIKIT_TRANSIT)$"),
) -> dict[str, Any]:
    from app.main import plan_route
    return await plan_route(
        from_lat=from_lat,
        from_lon=from_lon,
        to_lat=to_lat,
        to_lon=to_lon,
        preference=preference,
    )


@router.get("/stations")
async def komuter_stations(
    kind: str | None = Query(None, description="Filter: KRL, MRT, LRT"),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    from app.main import stations
    return await stations(kind=kind, limit=limit)
