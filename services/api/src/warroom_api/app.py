"""War Room API (P1-T3) — REST `/api/v1/*`.

Yang sudah ada di P1: auth sesi + RBAC, health, freshness, gate evaluate, dan penulis fakta
(operator). SSE (`/api/v1/stream`, P1-T7) dan observability Prometheus (P1-T8) menyusul.

Aturan yang dikodekan: setiap angka berasal dari tabel `facts` (punya `fact_id`, `source`,
`observed_at`, `ttl_s`) — API tidak pernah menghitung ulang angka domain (ADR-005).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from warroom_core import autonomy
from warroom_core.db import Fact, User, session_scope
from warroom_core.gate import DEFAULT_CI, DEFAULT_MIN_N, GateInput, evaluate

from warroom_api import auth, live
from warroom_api.areas import AREA_KEYS, areas_summary, facts_for_area
from warroom_api.errors import install_error_handlers
from warroom_api.metrics import collect_metrics, render_prometheus
from warroom_api.stream import event_stream

__all__ = ["app", "create_app"]


# --- skema permintaan/balasan ----------------------------------------------------------


class LoginBody(BaseModel):
    username: str
    password: str
    totp: str | None = None


class GateBody(BaseModel):
    n: int
    win: int
    be: float
    ci: float = DEFAULT_CI
    min_n: int = DEFAULT_MIN_N
    split: str | None = None
    label: str = "konfirmasi"
    subject: str = ""
    rule: str = ""


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


def create_app() -> FastAPI:
    app = FastAPI(
        title="War Room API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)

    # --- auth -------------------------------------------------------------------------

    @app.post("/api/v1/auth/login")
    def login(body: LoginBody, response: Response) -> dict[str, Any]:
        sid = auth.login(body.username, body.password, body.totp)
        if sid is None:
            raise HTTPException(status_code=401, detail="kredensial tidak sah")
        response.set_cookie(
            auth.COOKIE_NAME,
            sid,
            httponly=True,
            samesite="lax",
            secure=auth.cookie_secure(),  # Caddy TLS (03-backend.md §10)
            max_age=int(auth.SESSION_TTL.total_seconds()),
            path="/",
        )
        return {"ok": True}

    @app.post("/api/v1/auth/logout")
    def logout(
        user: Annotated[User, Depends(auth.current_user)],
        wr_session: Annotated[str | None, Cookie(alias=auth.COOKIE_NAME)] = None,
    ) -> dict[str, Any]:
        with session_scope() as s:
            if wr_session:
                auth.revoke_session(s, wr_session)
        return {"ok": True}

    @app.get("/api/v1/auth/me")
    def me(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        return {"username": user.username, "role": user.role}

    # --- sistem -----------------------------------------------------------------------

    @app.get("/api/v1/health")
    def health(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        db_ok = True
        try:
            with session_scope() as s:
                s.execute(select(1))
        except Exception:  # noqa: BLE001 — kegagalan DB harus jadi status, bukan 500 mentah
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "time": datetime.now(UTC).isoformat(),
            "user": user.username,
        }

    @app.get("/api/v1/freshness")
    def freshness(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        """Umur setiap fakta terbaru vs TTL-nya. Tidak ada fakta → daftar kosong, bukan angka karangan."""
        now = datetime.now(UTC)
        out: list[dict[str, Any]] = []
        with session_scope() as s:
            # fakta terbaru per (kind,key)
            sub = (
                select(Fact.kind, Fact.key, func.max(Fact.observed_at).label("obs"))
                .group_by(Fact.kind, Fact.key)
                .subquery()
            )
            rows = s.scalars(
                select(Fact).join(
                    sub,
                    (Fact.kind == sub.c.kind) & (Fact.key == sub.c.key) & (Fact.observed_at == sub.c.obs),
                )
            ).all()
            for f in rows:
                age = (now - f.observed_at).total_seconds()
                out.append(
                    {
                        "kind": f.kind,
                        "key": f.key,
                        "source": f.source,
                        "observed_at": f.observed_at.isoformat(),
                        "age_s": round(age, 1),
                        "ttl_s": f.ttl_s,
                        "status": "segar" if age <= f.ttl_s else "basi",
                    }
                )
        out.sort(key=lambda r: (r["status"] != "basi", r["kind"], r["key"]))
        return {"facts": out, "count": len(out), "checked_at": now.isoformat()}

    # --- gate (satu implementasi, ADR-003) ---------------------------------------------

    @app.post("/api/v1/gate/evaluate")
    def gate_evaluate(body: GateBody, user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        r = evaluate(
            GateInput(
                n=body.n,
                win=body.win,
                be=body.be,
                ci=body.ci,
                min_n=body.min_n,
                split=body.split,
                label=body.label,  # type: ignore[arg-type]
                subject=body.subject,
                rule=body.rule,
            )
        )
        return {
            "verdict": r.verdict,
            "reason": r.reason,
            "ci_low": r.ci_low,
            "ci_high": r.ci_high,
            "win_rate": r.win_rate,
            "be": r.be,
            "n": r.n,
            "required_n": r.required_n,
            "policy_version": r.policy_version,
            "notes": r.notes,
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

    @app.get("/api/v1/areas")
    def areas(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        with session_scope() as s:
            return {"areas": areas_summary(s)}

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
        """Uji kering read-only: ukur kedalaman buku (tanpa order) — P6-T3."""
        sub = str(body.get("subperintah", "depth"))
        return live.jalankan_kering_kedalaman(sub)

    return app


app = create_app()