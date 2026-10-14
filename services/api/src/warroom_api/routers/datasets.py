"""Router datasets & research — split beku (ADR-003) + katalog riset read-only.

Diekstrak dari app.py (P1-2, langkah 4). Refactor murni: path, status kode,
dan auth dependency (termasuk `require_role("owner")`) tidak berubah.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from warroom_core.db import ResearchRecord, ResearchRun, User, session_scope

from warroom_api import auth

router = APIRouter()


class FreezeBody(BaseModel):
    """Bekukan satu direktori dataset jadi split yang bisa dirujuk gate (ADR-003)."""

    dataset: str
    root: str
    # Bila True (bawaan), tolak dataset tanpa penanda hasil — split yang tak bisa dinilai
    # tidak boleh terlihat sah.
    require_outcome: bool = True


# --- split beku (ADR-003, P1 5 Okt 2026) ------------------------------------------
# Gate menerima "frozen:<id>"; endpoint ini yang membuat id itu NYATA.


@router.post("/api/v1/datasets/freeze")
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


@router.get("/api/v1/datasets/splits")
def datasets_splits(
    user: Annotated[User, Depends(auth.current_user)],
    dataset: str | None = Query(default=None),
) -> dict[str, Any]:
    from warroom_core import splits as _splits

    with session_scope() as s:
        rows = _splits.daftar(s, dataset=dataset)
    return {"splits": rows, "count": len(rows)}


@router.post("/api/v1/datasets/splits/{split_id}/verify")
def datasets_splits_verify(
    split_id: str, user: Annotated[User, Depends(auth.current_user)]
) -> dict[str, Any]:
    from warroom_core import splits as _splits

    with session_scope() as s:
        return _splits.verifikasi(s, split_id)


@router.get("/api/v1/research/runs")
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


@router.get("/api/v1/research/runs/{run_id}/records")
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


@router.get("/api/v1/research/runs/{run_id}")
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
