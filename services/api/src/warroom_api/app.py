"""War Room API (P1-T3) — REST `/api/v1/*`.

Yang sudah ada di P1: auth sesi + RBAC, health, freshness, gate evaluate, dan penulis fakta
(operator). SSE (`/api/v1/stream`, P1-T7) dan observability Prometheus (P1-T8) menyusul.

Aturan yang dikodekan: setiap angka berasal dari tabel `facts` (punya `fact_id`, `source`,
`observed_at`, `ttl_s`) — API tidak pernah menghitung ulang angka domain (ADR-005).
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from warroom_core.db import User, dispose_engine

from warroom_api import auth, limits
from warroom_api.errors import install_error_handlers
from warroom_api.laya_sentinel import laya_sentinel
from warroom_api.metrics import record_http
from warroom_api.routers import agents_hub as agents_hub_router
from warroom_api.routers import agy as agy_router
from warroom_api.routers import alert as alert_router
from warroom_api.routers import auth as auth_router
from warroom_api.routers import cron as cron_router
from warroom_api.routers import datasets as datasets_router
from warroom_api.routers import fakta as fakta_router
from warroom_api.routers import governance as governance_router
from warroom_api.routers import idx as idx_router
from warroom_api.routers import idx_edge as idx_edge_router
from warroom_api.routers import idx_ws as idx_ws_router
from warroom_api.routers import journal as journal_router
from warroom_api.routers import kalender as kalender_router
from warroom_api.routers import komuter as komuter_router
from warroom_api.routers import leaderboard as leaderboard_router
from warroom_api.routers import live as live_router
from warroom_api.routers import llm as llm_router
from warroom_api.routers import mt5_vault as mt5_vault_router
from warroom_api.routers import observability as observability_router
from warroom_api.routers import pasar as pasar_router
from warroom_api.routers import sistem as sistem_router
from warroom_api.routers import status_ops as status_ops_router
from warroom_api.routers import tencent as tencent_router
from warroom_api.routers import vault as vault_router
from warroom_api.stream import event_stream

__all__ = ["app", "create_app"]

# Pembatas laju in-process — didefinisikan TUNGGAL di `limits` (agar router yang
# dipisah, mis. routers/auth.py, memakai objek yang sama; penting untuk reset() uji).
# Diukur dari temuan audit 5 Okt 2026: login tanpa batas = brute force + amplifikasi
# scrypt (16 MiB/percobaan); verifier tanpa batas = kuota LLM berbayar bisa dibakar.
# Batas dapat dinaikkan lewat env untuk operasi yang sah, tapi tidak bisa dimatikan.
LOGIN_LIMITER = limits.LOGIN_LIMITER
VERIFIER_LIMITER = limits.VERIFIER_LIMITER
NARRATE_LIMITER = limits.NARRATE_LIMITER


def _kunci_klien(request: Request) -> str:
    """Kunci pembatas per pemanggil: IP klien bila ada, selain itu 'lokal'."""
    if request.client and request.client.host:
        return request.client.host
    return "lokal"


# --- skema permintaan/balasan ----------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mulai 24/7 Laya Sentinel Daemon di background
    sentinel_task = asyncio.create_task(laya_sentinel.start())
    yield
    laya_sentinel.is_running = False
    sentinel_task.cancel()
    dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="War Room API",
        version="0.1.0",
        docs_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def ukur_http(request, call_next):
        """Ukur hanya path /api/ agar p95 tidak tercampur scrape /metrics atau halaman web."""
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        mulai = time.perf_counter()
        try:
            respons = await call_next(request)
        except Exception:
            record_http(500, time.perf_counter() - mulai)
            raise
        record_http(respons.status_code, time.perf_counter() - mulai)
        return respons

    # CORS hanya bila diminta eksplisit lewat env. Produksi menaruh web dan API di origin
    # yang sama (Caddy), jadi tidak butuh CORS; daftar kosong = tidak ada header CORS.
    asal_diizinkan = [
        o.strip() for o in os.environ.get("WARROOM_CORS_ORIGINS", "").split(",") if o.strip()
    ]
    if asal_diizinkan:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=asal_diizinkan,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Warroom-Token"],
        )

    # --- auth ---
    app.include_router(auth_router.router)

    # --- sistem ---
    app.include_router(sistem_router.router)
    app.include_router(status_ops_router.router)

    # --- pasar (gate, sinyal, verdict, ringkas) ---
    app.include_router(pasar_router.router)
    app.include_router(tencent_router.router)
    app.include_router(komuter_router.router)
    app.include_router(idx_router.router)
    app.include_router(idx_edge_router.router)
    app.include_router(idx_ws_router.router)
    app.include_router(journal_router.router)
    app.include_router(kalender_router.router)
    app.include_router(cron_router.router)

    # --- papan peringkat strategi (baca fakta, angka + status jujur per setup) ---
    app.include_router(leaderboard_router.router)

    # --- split beku & riset (ADR-003) ---
    app.include_router(datasets_router.router)

    # --- fakta & area (penulis operator, baca per-area, sumber) ---
    app.include_router(fakta_router.router)

    # --- governance (parameter, usulan, kill switch, events) ---
    app.include_router(governance_router.router)

    # --- SSE (P1-T7) --------------------------------------------------------------------

    @app.get("/api/v1/stream")
    async def stream(
        request: Request,
        user: Annotated[User, Depends(auth.current_user)],
        topics: str | None = Query(None, description="mis. verdicts,trades,alerts"),
    ) -> StreamingResponse:
        daftar = [t.strip() for t in topics.split(",") if t.strip()] if topics else None
        last = request.headers.get("Last-Event-ID") or request.query_params.get("last_event_id")
        return StreamingResponse(
            event_stream(daftar, last, disconnect=request.is_disconnected),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # --- observability (P1-T8) ---
    app.include_router(observability_router.router)

    # --- alert & notifier (W5) ---
    app.include_router(alert_router.router)

    # --- P6: kesiapan live + grant ---
    app.include_router(live_router.router)

    # --- Vault kredensial MT5 (gudang salin-tempel, bukan auto-login) ---
    app.include_router(mt5_vault_router.router)
    app.include_router(vault_router.router)

    # --- P3: LLM gateway (konsol, prompt, narasi, verifier) ---
    app.include_router(llm_router.router)

    # --- AGY-CLI & Antigravity Web Control Manager ---
    app.include_router(agy_router.router)
    app.include_router(agents_hub_router.router)

    # --- Protected OpenAPI & Swagger UI (Hanya Admin dengan Sesi Sah) ---
    @app.get("/api/openapi.json", include_in_schema=False)
    async def get_protected_openapi(user: Annotated[User, Depends(auth.current_user)]):
        return JSONResponse(
            get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
        )

    @app.get("/api/docs", include_in_schema=False)
    async def get_protected_docs(user: Annotated[User, Depends(auth.current_user)]):
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - Swagger UI",
        )

    return app


app = create_app()