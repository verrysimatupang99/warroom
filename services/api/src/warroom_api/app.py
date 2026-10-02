"""War Room API (P1-T3) — REST `/api/v1/*`.

Yang sudah ada di P1: auth sesi + RBAC, health, freshness, gate evaluate, dan penulis fakta
(operator). SSE (`/api/v1/stream`, P1-T7) dan observability Prometheus (P1-T8) menyusul.

Aturan yang dikodekan: setiap angka berasal dari tabel `facts` (punya `fact_id`, `source`,
`observed_at`, `ttl_s`) — API tidak pernah menghitung ulang angka domain (ADR-005).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from warroom_core.db import Fact, User, session_scope
from warroom_core.gate import DEFAULT_CI, DEFAULT_MIN_N, GateInput, evaluate

from warroom_api import auth
from warroom_api.errors import install_error_handlers

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

    return app


app = create_app()