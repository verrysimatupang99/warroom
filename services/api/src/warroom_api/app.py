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
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from warroom_core import autonomy, prompts_dir
from warroom_core.db import Fact, ResearchRecord, ResearchRun, User, session_scope
from warroom_core.db.session import SASession

from warroom_api import auth, limits, live
from warroom_api.areas import AREA_KEYS, areas_summary, facts_for_area, latest_facts
from warroom_api.errors import install_error_handlers
from warroom_api.metrics import collect_metrics, render_prometheus
from warroom_api.routers import auth as auth_router
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


class FreezeBody(BaseModel):
    """Bekukan satu direktori dataset jadi split yang bisa dirujuk gate (ADR-003)."""

    dataset: str
    root: str
    # Bila True (bawaan), tolak dataset tanpa penanda hasil — split yang tak bisa dinilai
    # tidak boleh terlihat sah.
    require_outcome: bool = True


class FactBody(BaseModel):
    kind: str
    key: str
    value: Any
    source: str
    observed_at: datetime
    ttl_s: int = Field(ge=0)
    hash: str = ""


class FactsBody(BaseModel):
    facts: list[FactBody]


def _riwayat_kunci(s: SASession, kind: str, key: str, n: int) -> list[dict[str, Any]]:
    """N versi terbaru satu kunci fakta (untuk menarik riwayat di UI)."""
    rows = s.scalars(
        select(Fact).where(Fact.kind == kind, Fact.key == key).order_by(Fact.observed_at.desc()).limit(n)
    ).all()
    now = datetime.now(UTC)
    return [
        {
            "fact_id": f.id,
            "value": f.value_json,
            "source": f.source,
            "observed_at": f.observed_at.isoformat(),
            "ttl_s": f.ttl_s,
            "status": "segar" if (now - f.observed_at).total_seconds() <= f.ttl_s else "basi",
        }
        for f in rows
    ]


def _provider_ringkas(s: SASession) -> list[dict[str, Any]]:
    """Kesehatan per provider dari `llm_calls` — satu tempat (dipakai ai/status & llm-console).

    Tanpa penghitung di memori: `ok_rate` dihitung dari jumlah baris, `error_terakhir`
    diambil dari baris gagal terbaru per provider (kode HTTP/kelas error, bukan tebakan).
    """
    from warroom_core.db import LLMCall

    per = s.execute(
        select(
            LLMCall.provider,
            func.count(),
            func.count().filter(LLMCall.ok.is_(True)),
            func.count().filter(LLMCall.ok.is_(False)),
            func.count().filter(LLMCall.fallback_from.is_not(None)),
            func.percentile_cont(0.5).within_group(LLMCall.latency_ms.asc().nulls_last()),
            func.percentile_cont(0.95).within_group(LLMCall.latency_ms.asc().nulls_last()),
            func.coalesce(func.sum(LLMCall.tokens_in), 0),
            func.coalesce(func.sum(LLMCall.tokens_out), 0),
        ).group_by(LLMCall.provider)
    ).all()
    error_terakhir: dict[str, str] = {}
    for (p, code) in s.execute(
        select(LLMCall.provider, LLMCall.error_code)
        .where(LLMCall.error_code.is_not(None))
        .order_by(LLMCall.created_at.desc(), LLMCall.id.desc())
    ).all():
        error_terakhir.setdefault(str(p), str(code))
    return [
        {
            "provider": p,
            "n": n,
            "ok": ok_n,
            "gagal": g,
            "ok_rate": round(ok_n / n, 4) if n else None,
            "fallback": f,
            "p50_ms": p50,
            "p95_ms": p95,
            "token_in": ti,
            "token_out": to,
            "error_terakhir": error_terakhir.get(str(p)),
        }
        for (p, n, ok_n, g, f, p50, p95, ti, to) in per
    ]


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

    # --- split beku (ADR-003, P1 5 Okt 2026) ------------------------------------------
    # Gate menerima "frozen:<id>"; endpoint ini yang membuat id itu NYATA.

    @app.post("/api/v1/datasets/freeze")
    def datasets_freeze(
        body: FreezeBody, user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        from warroom_core import splits as _splits

        with session_scope() as s:
            try:
                hasil = _splits.bekukan(
                    s,
                    dataset=body.dataset,
                    root=body.root,
                    created_by=user.email,
                    require_outcome=body.require_outcome,
                )
            except (FileNotFoundError, ValueError) as exc:
                raise HTTPException(
                    status_code=422, detail={"code": "bekukan_gagal", "message": str(exc)}
                ) from exc
        return hasil

    @app.get("/api/v1/datasets/splits")
    def datasets_splits(
        user: Annotated[User, Depends(auth.current_user)],
        dataset: str | None = Query(default=None),
    ) -> dict[str, Any]:
        from warroom_core import splits as _splits

        with session_scope() as s:
            rows = _splits.daftar(s, dataset=dataset)
        return {"splits": rows, "count": len(rows)}

    @app.post("/api/v1/datasets/splits/{split_id}/verify")
    def datasets_splits_verify(
        split_id: str, user: Annotated[User, Depends(auth.current_user)]
    ) -> dict[str, Any]:
        from warroom_core import splits as _splits

        with session_scope() as s:
            return _splits.verifikasi(s, split_id)

    @app.get("/api/v1/research/runs")
    def research_runs(
        user: Annotated[User, Depends(auth.current_user)],
        research_key: str | None = Query(default=None, max_length=120),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        """Read-only research catalog; contract snapshots are not recomputed here."""
        with session_scope() as s:
            q = select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(limit)
            if research_key:
                q = q.where(ResearchRun.research_key == research_key)
            rows = s.scalars(q).all()
            return {
                "runs": [
                    {
                        "id": r.id,
                        "research_key": r.research_key,
                        "hypothesis_id": r.hypothesis_id,
                        "hypothesis_version": r.hypothesis_version,
                        "hypothesis_hash": r.hypothesis_hash,
                        "execution_hash": r.execution_hash,
                        "status": r.status,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    }
                    for r in rows
                ],
                "count": len(rows),
            }

    @app.get("/api/v1/research/runs/{run_id}/records")
    def research_records(run_id: str, user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        with session_scope() as s:
            if s.get(ResearchRun, run_id) is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "not_found", "message": "research run tidak ditemukan"},
                )
            query = (
                select(ResearchRecord)
                .where(ResearchRecord.research_run_id == run_id)
                .order_by(ResearchRecord.created_at.asc())
            )
            rows = s.scalars(query).all()
            return {
                "records": [
                    {
                        "id": r.id,
                        "kind": r.kind,
                        "uri": r.uri,
                        "sha256": r.sha256,
                        "status": r.status,
                        "provenance": r.provenance_json,
                        "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
                "count": len(rows),
            }

    @app.get("/api/v1/research/runs/{run_id}")
    def research_run(run_id: str, user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        with session_scope() as s:
            row = s.get(ResearchRun, run_id)
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "not_found", "message": "research run tidak ditemukan"},
                )
            records = s.scalars(
                select(ResearchRecord)
                .where(ResearchRecord.research_run_id == run_id)
                .order_by(ResearchRecord.created_at.asc())
            ).all()
            artifacts = [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "uri": r.uri,
                    "sha256": r.sha256,
                    "status": r.status,
                    "provenance": r.provenance_json,
                    "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
            return {
                "id": row.id,
                "research_key": row.research_key,
                "hypothesis_id": row.hypothesis_id,
                "hypothesis_version": row.hypothesis_version,
                "hypothesis_hash": row.hypothesis_hash,
                "hypothesis": row.hypothesis_json,
                "execution_hash": row.execution_hash,
                "execution": row.execution_json,
                "status": row.status,
                "provenance": row.provenance_json,
                "artifacts": artifacts,
                "artifact_count": len(artifacts),
                "evidence_status": "available" if artifacts else "blocked",
                "blocked_reason": None if artifacts else "no_artifact_records",
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }

    # --- penulis fakta (operator) -------------------------------------------------------

    @app.post("/api/v1/facts")
    def publish_facts(
        body: FactsBody, user: Annotated[User, Depends(auth.require_role("operator"))]
    ) -> dict[str, Any]:
        saved = 0
        with session_scope() as s:
            for f in body.facts:
                s.add(
                    Fact(
                        kind=f.kind,
                        key=f.key,
                        value_json=f.value,
                        source=f.source,
                        observed_at=f.observed_at,
                        ttl_s=f.ttl_s,
                        hash=f.hash,
                    )
                )
                saved += 1
        return {"saved": saved, "by": user.username}

    # --- baca per-area (P1-T6) ----------------------------------------------------------

    @app.get("/api/v1/areas/{area}")
    def area_detail(
        area: str,
        user: Annotated[User, Depends(auth.current_user)],
        riwayat: int = Query(0, ge=0, le=50, description="sertakan N versi lama per kunci"),
    ) -> dict[str, Any]:
        """Fakta satu area lengkap dengan metadata (`fact_id`, sumber, umur, status).

        Area tak dikenal tidak melempar 500 — balasannya menyebut daftar area yang ada.
        """
        with session_scope() as s:
            info = facts_for_area(s, area)
            if not info.get("dikenal", False):
                return info
            if riwayat:
                for f in info["facts"]:
                    f["riwayat"] = _riwayat_kunci(s, f["kind"], f["key"], riwayat)
            return info

    @app.get("/api/v1/areas")
    def areas(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        with session_scope() as s:
            return {"areas": areas_summary(s)}

    @app.get("/api/v1/sumber")
    def sumber_data(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        """Daftar SUMBER DATA tiap pasar — satu tempat, biar tidak ada tebakan.

        Revisi pemilik 10 Okt: "Crypto OKX" (ganti MEXC total).
        Revisi pemilik 7 Okt: "sumber data: Crypto MEXC; IDX Stock Arjum; Forex TVC;
        Polymarket Dokumentasi PM; Meme: Meteora=Solana, Robinhood=Uniswap". Daftar ini
        dipakai UI (halaman market + Sistem) supaya pembaca tahu angka ini datang dari mana.
        """
        return {
            "sumber": [
                {"pasar": "crypto", "label": "Crypto", "sumber": "OKX",
                 "keterangan": (
                     "Harga & depth dari OKX (venue paper). "
                     "Sinyal = SMC multi-timeframe, gate 6 aturan."
                 )},
                {"pasar": "idx", "label": "IDX", "sumber": "Stock Arjum",
                 "keterangan": "Bandarmologi/BSJP dari Stock Arjum + arsip tick; mesin lama (Tencent) beku."},
                {"pasar": "forex", "label": "Forex", "sumber": "TVC",
                 "keterangan": "Chart/series TradingView (TVC:) untuk bias & struktur."},
                {"pasar": "polymarket", "label": "Polymarket", "sumber": "Dokumentasi PM",
                 "keterangan": "Arm B favorit 0,70–0,95; aturan & contoh dari dokumentasi Polymarket."},
                {
                    "pasar": "gmgn",
                    "label": "Meme / DEX",
                    "sumber": "GMGN + FOMO",
                    "keterangan": (
                        "Memecoin: pemindaian GMGN/FOMO "
                        "(sol, bsc, base, eth, robinhood, arc, stable)."
                    ),
                },
                {
                    "pasar": "lp",
                    "label": "LP",
                    "sumber": "Meteora (Solana) · Uniswap (Robinhood Chain)",
                    "keterangan": (
                        "LP Solana lewat Meteora (DLMM/DAMM v2); LP Robinhood Chain lewat "
                        "Uniswap v2/v3/v4. Dua protokol BERBEDA."
                    ),
                },
            ],
            "sumber_atom": [
                {"nama": "OKX", "dipakai": "harga & eksekusi paper crypto"},
                {"nama": "Stock Arjum", "dipakai": "IDX bandarmologi/BSJP"},
                {"nama": "TVC (TradingView)", "dipakai": "forex (bias/struktur)"},
                {"nama": "Dokumentasi Polymarket", "dipakai": "aturan & dataset Polymarket"},
                {"nama": "GMGN / FOMO", "dipakai": "memecoin baru + smart money"},
                {"nama": "Meteora", "dipakai": "LP Solana (DLMM, DAMM v2)"},
                {"nama": "Uniswap", "dipakai": "LP Robinhood Chain (v2/v3/v4)"},
            ],
        }

    @app.get("/api/v1/facts/{kind}/{key}")
    def fact_satu(
        kind: str,
        key: str,
        user: Annotated[User, Depends(auth.current_user)],
        riwayat: int = Query(1, ge=1, le=50, description="jumlah nilai terbaru"),
    ) -> dict[str, Any]:
        with session_scope() as s:
            rows = s.scalars(
                select(Fact)
                .where(Fact.kind == kind, Fact.key == key)
                .order_by(Fact.observed_at.desc())
                .limit(riwayat)
            ).all()
        if not rows:
            raise HTTPException(status_code=404, detail=f"fakta {kind}/{key} belum ada")
        now = datetime.now(UTC)
        return {
            "kind": kind,
            "key": key,
            "facts": [
                {
                    "fact_id": f.id,
                    "value": f.value_json,
                    "source": f.source,
                    "observed_at": f.observed_at.isoformat(),
                    "ttl_s": f.ttl_s,
                    "status": "segar" if (now - f.observed_at).total_seconds() <= f.ttl_s else "basi",
                }
                for f in rows
            ],
        }

    def _area_endpoint(area: str):
        def _baca(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
            with session_scope() as s:
                return facts_for_area(s, area)

        return _baca

    for _area in AREA_KEYS:
        app.get(f"/api/v1/{_area}", name=f"area_{_area}")(_area_endpoint(_area))

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

    # --- P5: parameter, usulan, kill switch AI -------------------------------------------

    @app.get("/api/v1/params")
    def params(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        from warroom_core.db import Parameter

        with session_scope() as s:
            rows = s.scalars(select(Parameter).order_by(Parameter.name)).all()
            data = [
                {
                    "nama": p.name,
                    "nilai": p.value_json,
                    "batas": p.bounds_json,
                    "terkunci": p.locked,
                    "scope": p.scope,
                    "catatan": p.note,
                    "diperbarui": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in rows
            ]
        return {"params": data, "count": len(data)}

    @app.get("/api/v1/proposals")
    def proposals(
        user: Annotated[User, Depends(auth.current_user)],
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        from warroom_core.db import Proposal

        with session_scope() as s:
            rows = s.scalars(
                select(Proposal).order_by(Proposal.created_at.desc()).limit(limit)
            ).all()
            data = [
                {
                    "id": pr.id,
                    "parameter": pr.parameter_name,
                    "dari": pr.from_json,
                    "ke": pr.to_json,
                    "alasan": pr.reason,
                    "bukti": pr.evidence_json,
                    "gate": pr.gate_verdict,
                    "status": pr.status,
                    "ditolak_karena": pr.rejected_reason,
                    "diputuskan_oleh": pr.decided_by,
                    "diterapkan_pada": pr.applied_at.isoformat() if pr.applied_at else None,
                    "config_hash": pr.config_hash,
                    "dibuat": pr.created_at.isoformat() if pr.created_at else None,
                }
                for pr in rows
            ]
        return {"proposals": data, "count": len(data)}

    @app.post("/api/v1/proposals/{pid}/apply")
    def proposal_apply(
        pid: int, user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        with session_scope() as s:
            ok = autonomy.terapkan(s, pid, actor=user.username)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail="usulan tidak bisa diterapkan (sudah diterapkan atau parameter terkunci)",
            )
        return {"ok": True, "oleh": user.username}

    @app.post("/api/v1/proposals/{pid}/rollback")
    def proposal_rollback(
        pid: int, user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        with session_scope() as s:
            ok = autonomy.rollback(s, pid, actor=user.username)
        if not ok:
            raise HTTPException(status_code=409, detail="usulan belum pernah diterapkan")
        return {"ok": True, "oleh": user.username}

    @app.get("/api/v1/ai/status")
    def ai_status(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        from warroom_core.db import LLMCall, Proposal

        with session_scope() as s:
            return {
                "kill_switch": autonomy.kill_switch_aktif(s),
                "usulan_menunggu": s.scalar(
                    select(func.count()).select_from(Proposal).where(Proposal.status == "butuh_manusia")
                )
                or 0,
                "panggilan_llm": s.scalar(select(func.count()).select_from(LLMCall)) or 0,
                # Kesehatan provider (W6): mana yang gagal dan dengan kode apa.
                "provider": _provider_ringkas(s),
            }

    @app.post("/api/v1/ai/kill-switch")
    def ai_kill_switch(
        body: dict[str, Any], user: Annotated[User, Depends(auth.require_role("owner"))]
    ) -> dict[str, Any]:
        aktif = bool(body.get("aktif"))
        with session_scope() as s:
            ok = autonomy.set_kill_switch(s, aktif, actor=user.username)
        if not ok:
            raise HTTPException(status_code=409, detail="parameter kill switch belum terdaftar")
        return {"ok": True, "kill_switch": aktif, "oleh": user.username}

    @app.get("/api/v1/events")
    def events_list(
        user: Annotated[User, Depends(auth.current_user)],
        limit: int = Query(120, ge=1, le=500),
        tipe: str | None = Query(
            None,
            description=(
                "prefix tipe, boleh daftar dipisah koma (mis. 'trade.,signal.,verdict.'). "
                "Dipakai panel Kejadian Area: tanpa filter, 120 baris terakhir hampir pasti "
                "didominasi job.ran sehingga kejadian area tak pernah terlihat."
            ),
        ),
    ) -> dict[str, Any]:
        """Kejadian terakhir dari tabel `events` (append-only).

        Dipakai panel "Kejadian Area": SSE hanya mengirim kejadian BARU (tanpa
        Last-Event-ID ia mulai dari sekarang — perilaku yang benar untuk CPU/DB),
        sehingga panel selalu kosong sampai ada kejadian baru. Backfill lewat
        endpoint ini; angka & tipe apa adanya dari DB.
        """
        from warroom_core.db import Event

        with session_scope() as s:
            q = select(Event)
            if tipe:
                from sqlalchemy import or_

                prefiks = [t.strip() for t in tipe.split(",") if t.strip()]
                q = q.where(or_(*[Event.type.like(f"{p}%") for p in prefiks]))
            rows = s.scalars(q.order_by(Event.id.desc()).limit(limit)).all()
            return {
                "events": [
                    {
                        "id": e.id,
                        "type": e.type,
                        "actor": e.actor,
                        "severity": e.severity,
                        "payload": e.payload_json,
                        "fact_ids": e.fact_ids,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in rows
                ],
                "count": len(rows),
            }

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