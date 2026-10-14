"""War Room API (P1-T3) — REST `/api/v1/*`.

Yang sudah ada di P1: auth sesi + RBAC, health, freshness, gate evaluate, dan penulis fakta
(operator). SSE (`/api/v1/stream`, P1-T7) dan observability Prometheus (P1-T8) menyusul.

Aturan yang dikodekan: setiap angka berasal dari tabel `facts` (punya `fact_id`, `source`,
`observed_at`, `ttl_s`) — API tidak pernah menghitung ulang angka domain (ADR-005).
"""

from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func, select
from warroom_core import prompts_dir
from warroom_core.db import User, session_scope

from warroom_api import auth, limits, live
from warroom_api.areas import AREA_KEYS, latest_facts
from warroom_api.errors import install_error_handlers
from warroom_api.metrics import collect_metrics, render_prometheus
from warroom_api.providers import provider_ringkas as _provider_ringkas
from warroom_api.routers import auth as auth_router
from warroom_api.routers import datasets as datasets_router
from warroom_api.routers import fakta as fakta_router
from warroom_api.routers import governance as governance_router
from warroom_api.routers import pasar as pasar_router
from warroom_api.routers import sistem as sistem_router
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="War Room API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)

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

    # --- pasar (gate, sinyal, verdict, ringkas) ---
    app.include_router(pasar_router.router)

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
            event_stream(daftar, last),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # --- observability (P1-T8) ----------------------------------------------------------

    @app.get("/metrics")
    def metrics(
        user: Annotated[User | None, Depends(auth.optional_user)],
    ) -> PlainTextResponse:
        publik = os.environ.get("WARROOM_METRICS_PUBLIC", "0").strip().lower() in {"1", "true", "yes"}
        if user is None and not publik:
            raise HTTPException(status_code=401, detail="belum login")
        with session_scope() as s:
            teks = render_prometheus(collect_metrics(s))
        return PlainTextResponse(teks, media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/api/v1/metrics")
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

    # --- alert & notifier (W5) ------------------------------------------------------------

    @app.get("/api/v1/alerts")
    def alerts_list(
        user: Annotated[User, Depends(auth.current_user)],
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        """Alert + status transport. Transport kosong **tidak pernah** diklaim terkirim."""
        from warroom_core.db import Alert, Event

        with session_scope() as s:
            rows = s.scalars(
                select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
            ).all()
            percobaan = s.scalar(
                select(Event.payload_json)
                .where(Event.type == "alert.sent")
                .order_by(Event.id.desc())
                .limit(1)
            )
            data = [
                {
                    "id": a.id,
                    "severity": a.severity,
                    "subject": a.subject,
                    "message": a.message,
                    "suggested_action": a.suggested_action,
                    "ack_at": a.ack_at.isoformat() if a.ack_at else None,
                    "snooze_until": a.snooze_until.isoformat() if a.snooze_until else None,
                    "created_at": a.created_at.isoformat(),
                    "percobaan": a.attempts or 0,
                    "kesalahan_terakhir": a.last_error,
                    # None = belum pernah dicoba; True = percobaan terakhir sukses.
                    "terakhir_ok": None if not (a.attempts or 0) else a.last_error is None,
                }
                for a in rows
            ]
        transport: dict[str, Any]
        try:
            from warroom_notifier.transport import transport_from_env

            tr = transport_from_env()
            transport = {"nama": tr.name, "terkonfigurasi": tr.name != "null"}
        except Exception as exc:  # noqa: BLE001 — jangan matikan halaman karena transport
            transport = {"nama": "error", "terkonfigurasi": False, "detail": type(exc).__name__}
        return {
            "transport": transport,
            "terbuka": sum(1 for d in data if d["ack_at"] is None),
            "alerts": data,
            "percobaan_terakhir": percobaan,
        }

    @app.post("/api/v1/alerts/{aid}/ack")
    def alerts_ack(
        aid: int,
        body: dict[str, Any],
        user: Annotated[User, Depends(auth.require_role("operator"))],
    ) -> dict[str, Any]:
        """Ack alert (atau snooze bila ``snooze_s`` > 0). Alert tidak pernah dihapus."""
        from datetime import timedelta

        from warroom_core.db import Alert, Event

        snooze_s = max(0, int(body.get("snooze_s") or 0))
        now = datetime.now(UTC)
        with session_scope() as s:
            a = s.get(Alert, aid)
            if a is None:
                raise HTTPException(status_code=404, detail="alert tidak ditemukan")
            if snooze_s > 0:
                a.snooze_until = now + timedelta(seconds=snooze_s)
                a.ack_at = None
            else:
                a.ack_at = now
                a.snooze_until = None
            s.add(
                Event(
                    type="alert.ack",
                    actor=user.username,
                    payload_json={"alert_id": aid, "snooze_s": snooze_s},
                    fact_ids=[],
                    severity="info",
                )
            )
        return {"ok": True, "id": aid, "snooze_s": snooze_s}

    # --- P6: kesiapan live + grant -------------------------------------------------------

    @app.get("/api/v1/live/arming")
    def live_arming(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        return live.arming_status().to_dict()

    @app.get("/api/v1/live/grants")
    def live_grants(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        from warroom_core.db import Grant

        with session_scope() as s:
            rows = s.scalars(select(Grant).order_by(Grant.granted_at.desc()).limit(100)).all()
            data = [
                {
                    "id": g.id,
                    "scope": g.scope,
                    "oleh": g.granted_by,
                    "message_id": g.message_id,
                    "alasan": g.reason,
                    "diberikan": g.granted_at.isoformat() if g.granted_at else None,
                    "kedaluwarsa": g.expires_at.isoformat() if g.expires_at else None,
                    "dicabut": g.revoked_at.isoformat() if g.revoked_at else None,
                }
                for g in rows
            ]
        return {"grants": data, "count": len(data), "scope_dikenal": list(live.SCOPE_DIKENAL)}

    @app.post("/api/v1/live/grant")
    def live_grant(
        body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        try:
            with session_scope() as s:
                hasil = live.grant_baru(
                    s,
                    scope=str(body.get("scope", "")),
                    granted_by=user.username,
                    message_id=str(body.get("message_id", "")),
                    reason=str(body.get("reason", "")),
                    ttl_s=body.get("ttl_s", 3600),
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, **hasil}

    @app.post("/api/v1/live/action")
    def live_action(
        body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        """Tidak pernah mengeksekusi apa pun. Hanya memeriksa grant → 409 bila kurang."""
        scope = str(body.get("scope", ""))
        with session_scope() as s:
            kurang = live.scope_kurang(s, scope)
        if kurang:
            raise HTTPException(
                status_code=409,
                detail={
                    "aksi": scope,
                    "kurang": kurang,
                    "catatan": "eksekusi nyata tetap milik owner di luar repo ini",
                },
            )
        return {
            "ok": True,
            "scope": scope,
            "catatan": "grant lengkap; tidak ada aksi yang dijalankan oleh API ini",
        }

    @app.post("/api/v1/live/dry-run")
    def live_dry_run(
        body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("operator"))]
    ) -> dict[str, Any]:
        """Uji kering read-only: ukur kedalaman buku (tanpa order) — P6-T3.

        Hanya subperintah yang di-allowlist yang diterima. Subperintah lain → **422**,
        bukan 200-dengan-pesan-gagal: permintaannya memang tidak sah, dan pemanggil
        tidak boleh menganggapnya berhasil. (Temuan audit 5 Okt 2026.)
        """
        sub = str(body.get("subperintah", "depth"))
        if sub not in live.SUBPERINTAH_DRY_RUN_DIIZINKAN:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "subperintah_ditolak",
                    "message": (
                        f"subperintah '{sub}' tidak diizinkan untuk uji kering; "
                        f"pilihan: {', '.join(sorted(live.SUBPERINTAH_DRY_RUN_DIIZINKAN))}"
                    ),
                },
            )
        return live.jalankan_kering_kedalaman(sub)

    # --- P3: LLM gateway (konsol, prompt, narasi) ----------------------------------------

    @app.get("/api/v1/ai/llm-console")
    def llm_console(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        """Kesehatan provider dari `llm_calls` — tanpa perhitungan manual."""
        from warroom_core.db import LLMCall

        with session_scope() as s:
            total = s.scalar(select(func.count()).select_from(LLMCall)) or 0
            per_provider = _provider_ringkas(s)
            per_peran = [
                {"role": r, "n": n, "gagal": g}
                for (r, n, g) in s.execute(
                    select(LLMCall.role, func.count(), func.count().filter(LLMCall.ok.is_(False)))
                    .group_by(LLMCall.role)
                ).all()
            ]
            biaya = float(s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0))) or 0)
        fallback_rate = (
            round(sum(p["fallback"] for p in per_provider) / total, 4) if total else None
        )
        return {
            "total_panggilan": total,
            "fallback_rate": fallback_rate,
            "biaya_usd": biaya,
            "per_provider": per_provider,
            "per_peran": per_peran,
            "catatan": "angka dihitung dari tabel llm_calls, bukan penghitung di memori",
        }

    @app.get("/api/v1/ai/prompts")
    def ai_prompts(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        from warroom_core.db import Prompt

        with session_scope() as s:
            rows = s.scalars(select(Prompt).order_by(Prompt.role, Prompt.version)).all()
            data = [
                {"role": p.role, "versi": p.version, "aktif": p.active,
                 "skema": bool(p.schema_json), "contoh": len(p.contoh_json or [])}
                for p in rows
            ]
        return {"prompts": data, "count": len(data)}

    @app.post("/api/v1/ai/narrate")
    def ai_narrate(
        body: dict[str, Any],
        request: Request,
        user: Annotated[User, Depends(auth.require_role("operator"))],
    ) -> dict[str, Any]:
        """Narasi ber-grounding dari fakta di DB. Tanpa fakta → `insufficient`, bukan tebakan."""
        if not NARRATE_LIMITER.izinkan(_kunci_klien(request)):
            raise HTTPException(status_code=429, detail="terlalu banyak permintaan narasi; coba lagi nanti")
        from warroom_llm import CallRequest, FactRef, Gateway
        from warroom_llm.config import default_config
        from warroom_llm.prompts import PromptRegistry

        area = str(body.get("area", "crypto"))
        kunci = AREA_KEYS.get(area, ())
        with session_scope() as s:
            terbaru = latest_facts(s)
            dipakai = [terbaru[k] for k in kunci if k in terbaru][:8]
            fakta = [
                FactRef(fact_id=f.id, label=f"F{i + 1}",
                        text=f"{f.key}={str(f.value_json)[:80]} (sumber={f.source}, umur_s="
                             f"{int((datetime.now(UTC) - f.observed_at).total_seconds())})")
                for i, f in enumerate(dipakai)
            ]
        gw = Gateway(config=default_config(), prompts=PromptRegistry.from_dir(str(prompts_dir())))
        hasil = gw.call(
            CallRequest(
                role="narrator",
                user=str(body.get("pertanyaan", f"Ringkas 2 kalimat untuk area {area}.")),
                facts=tuple(fakta),
                min_facts=1,
                use_cache=bool(body.get("cache", True)),
            )
        )
        return {
            "status": hasil.status,
            "provider": hasil.provider,
            "model": hasil.model,
            "fallback_from": hasil.fallback_from,
            "prompt_version": hasil.prompt_version,
            "latency_ms": hasil.latency_ms,
            "fact_ids": list(hasil.fact_ids),
            "output": hasil.output,
            "error_code": hasil.error_code,
            "catatan": "semua angka di keluaran harus berasal dari fact_ids di atas",
        }

    @app.post("/api/v1/ai/verifier")
    def ai_verifier(
        body: dict[str, Any],
        request: Request,
        user: Annotated[User | None, Depends(auth.optional_user)],
    ) -> dict[str, Any]:
        """Penilai kedua untuk kartu pod (P3-T5).

        Dipanggil **hanya** dari proses lokal: token layanan (`WARROOM_SERVICE_TOKEN`)
        atau berasal dari 127.0.0.1. Jalur sesi pengguna **wajib** peran `operator` —
        temuan audit 5 Okt 2026: sebelumnya `viewer` pun bisa memanggil, dan endpoint
        ini membakar kuota LLM berbayar. Setiap jalur dibatasi laju.
        """
        if not VERIFIER_LIMITER.izinkan(_kunci_klien(request)):
            raise HTTPException(status_code=429, detail="terlalu banyak permintaan verifier; coba lagi nanti")
        token_env = os.environ.get("WARROOM_SERVICE_TOKEN", "")
        token_kirim = request.headers.get("x-warroom-token", "")
        dari_lokal = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
        token_sah = bool(token_env) and hmac.compare_digest(token_env, token_kirim)
        # Sesi pengguna: wajib peran operator. Token/lokal: tanpa peran (proses internal).
        sesi_berwenang = user is not None and auth.has_role(user, "operator")
        if not sesi_berwenang and not token_sah and not dari_lokal:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "unauthenticated",
                    "message": "butuh sesi operator, token layanan, atau lokal",
                },
            )
        klaim = [str(k) for k in (body.get("klaim") or [])][:12]
        if not klaim:
            raise HTTPException(
                status_code=422,
                detail={"code": "klaim_kosong", "message": "kirim daftar `klaim` ringkas"},
            )
        from warroom_llm import CallRequest, FactRef, Gateway
        from warroom_llm.config import default_config
        from warroom_llm.prompts import PromptRegistry

        gw = Gateway(config=default_config(), prompts=PromptRegistry.from_dir(str(prompts_dir())))
        fakta = tuple(
            FactRef(fact_id=int(f["id"]), label=f"F{i + 1}",
                    text=f"{f['key']}={str(f['value_json'])[:80]} (sumber={f['source']})")
            for i, f in enumerate(body.get("fakta") or [])
            if isinstance(f, dict) and "id" in f and "key" in f
        )
        hasil = gw.call(
            CallRequest(
                role="verifier",
                user=f"Klaim pod {body.get('nama', '?')}: " + " | ".join(klaim),
                facts=fakta,
                min_facts=int(body.get("min_facts", 0)),
                use_cache=bool(body.get("cache", True)),
            )
        )
        return {
            "status": hasil.status,
            "setuju": (hasil.output or {}).get("setuju"),
            "catatan": (hasil.output or {}).get("catatan"),
            "provider": hasil.provider,
            "fallback_from": hasil.fallback_from,
            "fact_ids": list(hasil.fact_ids),
            "error_code": hasil.error_code,
        }

    return app


app = create_app()