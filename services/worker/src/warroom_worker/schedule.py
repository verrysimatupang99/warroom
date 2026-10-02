"""Jadwal deklaratif (P1-T4).

Satu tabel `jobs`, satu fungsi `run_due()`. Tidak ada cron tersembunyi: apa yang akan jalan
bisa dibaca dari DB, lengkap dengan hasil terakhirnya.

Job yang **tidak** dinyalakan di P1 diberi alasan eksplisit di `note` — bukan didiamkan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Job

__all__ = ["DEFAULT_JOBS", "JobSpec", "due_jobs", "ensure_jobs", "run_due", "run_one"]


@dataclass(frozen=True)
class JobSpec:
    name: str
    interval_s: int
    enabled: bool = True
    payload: dict[str, Any] = field(default_factory=dict)
    note: str = ""


DEFAULT_JOBS: tuple[JobSpec, ...] = (
    JobSpec(
        name="publish-facts",
        interval_s=300,
        enabled=True,
        # TTL 1800 s = 2× jarak tulis snapshot (timer domain 15 mnt) dan sama dengan ambang
        # watchdog domain (`SNAPSHOT_MAX_AGE=1800`). Memakai 600 s (nilai badge dashboard)
        # membuat fakta "basi" di antara dua tulisan dan memunculkan alert palsu — sudah
        # terjadi sekali; lihat docs/p1-progress.md.
        payload={"path": "state/snapshot.json", "ttl_s": 1800},
        note="baca snapshot domain → facts + event (murah, tanpa kuota).",
    ),
    JobSpec(
        name="freshness",
        interval_s=300,
        enabled=True,
        payload={"alert_on_basi": True},
        note="hitung umur fakta vs ttl; basi → alert (dedupe per subjek).",
    ),
    JobSpec(
        name="notify",
        interval_s=300,
        enabled=True,
        payload={"limit": 10},
        note=(
            "kirim alert terbuka lewat transport; default tanpa transport → alert tetap di DB "
            "dan dicatat gagal (tidak pernah diklaim terkirim)."
        ),
    ),
    JobSpec(
        name="snapshot",
        interval_s=900,
        enabled=False,
        payload={},
        note=(
            "NONAKTIF: `live-trading-snapshot.timer` masih penulis tunggal snapshot. "
            "Menyalakan ini = dua penulis untuk berkas yang sama. Cutover menunggu keputusan owner."
        ),
    ),
    JobSpec(
        name="collect",
        interval_s=1800,
        enabled=False,
        payload={},
        note=(
            "NONAKTIF: `live-trading-collect.timer` masih jalan dan `lt scan` memakai kuota Arjum. "
            "Dua penulis = kuota dobel. Cutover menunggu keputusan owner."
        ),
    ),
    JobSpec(
        name="backup",
        interval_s=21600,
        enabled=False,
        payload={},
        note=(
            "NONAKTIF: `live-trading-backup.timer` (6 jam, rotasi 14) sudah berjalan dan "
            "langkah restore-nya sudah teruji — tidak perlu penulis kedua."
        ),
    ),
)

# Nama job → fungsi. Diisi oleh `warroom_worker.jobs` saat impor untuk menghindari impor melingkar.
HANDLERS: dict[str, Any] = {}


def ensure_jobs(s: SASession, specs: tuple[JobSpec, ...] = DEFAULT_JOBS) -> list[str]:
    """Daftarkan job yang belum ada. Tidak menimpa `enabled` yang sudah diubah manusia."""
    ada = {j.name: j for j in s.scalars(select(Job)).all()}
    dibuat: list[str] = []
    for spec in specs:
        if spec.name in ada:
            continue
        s.add(
            Job(
                name=spec.name,
                interval_s=spec.interval_s,
                enabled=spec.enabled,
                payload_json=spec.payload,
                note=spec.note,
                next_run_at=datetime.now(UTC),
            )
        )
        dibuat.append(spec.name)
    s.flush()
    return dibuat


def due_jobs(s: SASession, now: datetime | None = None) -> list[Job]:
    """Job aktif yang sudah waktunya. Urut paling telat lebih dulu."""
    t = now or datetime.now(UTC)
    rows = s.scalars(
        select(Job)
        .where(Job.enabled.is_(True))
        .where((Job.next_run_at.is_(None)) | (Job.next_run_at <= t))
        .order_by(Job.next_run_at.asc().nulls_first())
    ).all()
    return list(rows)


def run_one(s: SASession, job: Job, now: datetime | None = None) -> tuple[str, str]:
    """Jalankan satu job. Status: ok | dilewati | gagal. Tidak pernah melempar ke pemanggil."""
    t = now or datetime.now(UTC)
    handler = HANDLERS.get(job.name)
    if handler is None:
        status, detail = "dilewati", f"tidak ada handler untuk job '{job.name}'"
    else:
        try:
            detail = handler(s, job) or ""
            status = "ok"
        except Exception as exc:  # noqa: BLE001 — kegagalan job harus tercatat, bukan mematikan loop
            status, detail = "gagal", f"{type(exc).__name__}: {exc}"

    job.last_run_at = t
    job.last_status = status
    job.last_detail = detail[:500]
    job.next_run_at = t + timedelta(seconds=max(1, job.interval_s))
    s.add(
        Event(
            type="job.ran",
            actor="worker",
            payload_json={"job": job.name, "status": status, "detail": job.last_detail},
            fact_ids=[],
            severity="info" if status == "ok" else "warning",
        )
    )
    s.flush()
    return status, detail


def run_due(s: SASession, now: datetime | None = None, limit: int = 10) -> list[dict[str, str]]:
    """Jalankan semua job yang jatuh tempo (maks `limit` per siklus)."""
    hasil: list[dict[str, str]] = []
    for job in due_jobs(s, now)[:limit]:
        status, detail = run_one(s, job, now)
        hasil.append({"job": job.name, "status": status, "detail": detail})
    return hasil