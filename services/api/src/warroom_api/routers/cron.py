"""Panel scheduler lokal: tabel `jobs` + event `job.ran`.

Sebelumnya router ini mem-proxy node MiniMax (Tencent), yang sudah tidak ada. Akibatnya
ketiga endpoint selalu `unavailable`, padahal worker lokal punya jadwal deklaratif di
tabel `jobs` dan riwayat di `events`. Router ini membaca sumber lokal itu apa adanya:
tidak ada job yang dijalankan, diubah, atau ditebak statusnya.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from warroom_core.db import Event, Job, session_scope

from warroom_api import auth

router = APIRouter(prefix="/api/v1/cron", tags=["cron"], dependencies=[Depends(auth.current_user)])

STATUS_BELUM = "belum-jalan"


def _iso(nilai: datetime | None) -> str | None:
    return nilai.isoformat() if nilai else None


def _job(j: Job, now: datetime) -> dict[str, Any]:
    return {
        "id": j.id,
        "name": j.name,
        "enabled": j.enabled,
        "interval_s": j.interval_s,
        "next_run_at": _iso(j.next_run_at),
        "last_run_at": _iso(j.last_run_at),
        "umur_detik": round(max(0.0, (now - j.last_run_at).total_seconds()), 1)
        if j.last_run_at
        else None,
        "last_status": j.last_status or STATUS_BELUM,
        "last_detail": j.last_detail,
        "note": j.note,
        "payload": j.payload_json,
    }


@router.get("/summary")
def cron_summary() -> dict[str, Any]:
    """Ringkasan scheduler lokal, dihitung dari status terakhir tiap job."""
    now = datetime.now(UTC)
    with session_scope() as s:
        jobs = s.scalars(select(Job).order_by(Job.name)).all()
        hitung = {STATUS_BELUM: 0, "ok": 0, "gagal": 0, "dilewati": 0}
        for j in jobs:
            status = j.last_status or STATUS_BELUM
            hitung[status] = hitung.get(status, 0) + 1
        gagal = [j for j in jobs if j.last_status == "gagal"]
        terakhir_gagal = None
        if gagal:
            j = max(gagal, key=lambda x: x.last_run_at or datetime.min.replace(tzinfo=UTC))
            terakhir_gagal = {
                "job": j.name,
                "last_run_at": _iso(j.last_run_at),
                "detail": j.last_detail,
            }
    return {
        "sumber": "lokal:jobs",
        "total": len(jobs),
        "aktif": sum(1 for j in jobs if j.enabled),
        "mati": sum(1 for j in jobs if not j.enabled),
        "status_terakhir": hitung,
        "terakhir_gagal": terakhir_gagal,
        "diperbarui": now.isoformat(),
    }


@router.get("/jobs")
def cron_jobs() -> dict[str, Any]:
    """Seluruh job beserta jadwal dan hasil terakhirnya."""
    now = datetime.now(UTC)
    with session_scope() as s:
        jobs = s.scalars(select(Job).order_by(Job.name)).all()
        data = [_job(j, now) for j in jobs]
    return {"sumber": "lokal:jobs", "jumlah": len(data), "jobs": data}


@router.get("/jobs/{job_id}")
def cron_job(job_id: str) -> dict[str, Any]:
    """Detail satu job berdasarkan id numerik atau nama unik."""
    now = datetime.now(UTC)
    with session_scope() as s:
        job = None
        if job_id.isdigit():
            job = s.get(Job, int(job_id))
        if job is None:
            job = s.scalar(select(Job).where(Job.name == job_id))
        if job is None:
            raise HTTPException(status_code=404, detail=f"job '{job_id}' tidak ditemukan")
        return {"sumber": "lokal:jobs", "job": _job(job, now)}


@router.get("/executions")
def cron_executions(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    """Riwayat `job.ran` terakhir, terbaru lebih dulu."""
    with session_scope() as s:
        rows = s.execute(
            select(Event)
            .where(Event.type == "job.ran")
            .order_by(Event.id.desc())
            .limit(limit)
        ).scalars()
        eksekusi = []
        for e in rows:
            payload = e.payload_json or {}
            eksekusi.append(
                {
                    "id": e.id,
                    "job": payload.get("job"),
                    "status": payload.get("status"),
                    "detail": payload.get("detail", ""),
                    "at": _iso(e.created_at),
                }
            )
    return {"sumber": "lokal:events", "jumlah": len(eksekusi), "eksekusi": eksekusi}
