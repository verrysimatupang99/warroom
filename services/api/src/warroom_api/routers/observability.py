"""Router observability — /metrics (Prometheus) & /api/v1/metrics (UI).

Diekstrak dari app.py (P1-2). Refactor murni.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from warroom_core.db import User, session_scope

from warroom_api import auth
from warroom_api.metrics import collect_metrics, render_prometheus

router = APIRouter()


@router.get("/metrics")
def metrics(
    request: Request,
    user: Annotated[User | None, Depends(auth.optional_user)],
) -> PlainTextResponse:
    publik = os.environ.get("WARROOM_METRICS_PUBLIC", "0").strip().lower() in {"1", "true", "yes"}
    # Scraper lokal (worker slo-check) boleh membaca tanpa sesi; nginx tidak mem-proxy
    # /metrics, jadi permukaan publik tetap localhost.
    klien = request.client.host if request.client else ""
    lokal = klien in {"127.0.0.1", "::1"}
    if user is None and not (publik or lokal):
        raise HTTPException(status_code=401, detail="belum login")
    with session_scope() as s:
        teks = render_prometheus(collect_metrics(s))
    return PlainTextResponse(teks, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/api/v1/metrics")
def metrics_ui(
    user: Annotated[User, Depends(auth.current_user)],
) -> PlainTextResponse:
    """Teks metrik yang sama, **wajib sesi** — nginx tidak mengekspos /metrics ke publik.

    UI (Biaya & LLMConsole) memakai jalur ini supaya tidak pernah mengenai 404 dari
    reverse proxy, sementara /metrics tetap hanya untuk scraper lokal.
    """
    with session_scope() as s:
        teks = render_prometheus(collect_metrics(s))
    return PlainTextResponse(teks, media_type="text/plain; version=0.0.4; charset=utf-8")
