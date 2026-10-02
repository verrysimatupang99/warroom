"""Implementasi job worker (P1-T4) + notifikasi alert (P1-T8).

Setiap handler menerima `(session, job)` dan mengembalikan string detail untuk `jobs.last_detail`.
Handler **tidak boleh** menelan kegagalan diam-diam: `schedule.run_one` yang menangkap dan mencatat.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event, Fact, Job
from warroom_notifier.dispatch import kirim_tertunda

from warroom_worker import schedule
from warroom_worker.facts_publish import publish_snapshot

__all__ = ["handler_freshness", "handler_publish_facts", "register_handlers", "root_dir"]

# Berapa lama alert basi yang sama tidak diulang.
ALERT_DEDUPE = timedelta(hours=1)


def root_dir() -> Path:
    """Direktori domain (live-trading). Bisa ditimpa lewat env `WARROOM_DOMAIN_HOME`."""
    import os

    return Path(os.environ.get("WARROOM_DOMAIN_HOME", str(Path.home() / "live-trading")))


def handler_publish_facts(s: SASession, job: Job) -> str:
    """Terbitkan `state/snapshot.json` → facts + event."""
    rel = str(job.payload_json.get("path", "state/snapshot.json"))
    ttl = int(job.payload_json.get("ttl_s", 600))
    path = root_dir() / rel
    rep = publish_snapshot(s, path, ttl_s=ttl, actor="worker")
    return f"status={rep.status} fakta={rep.facts} observed_at={rep.observed_at or '-'}"


def handler_freshness(s: SASession, job: Job) -> str:
    """Hitung umur fakta terbaru vs TTL; yang basi → Alert (dedupe) + event."""
    now = datetime.now(UTC)
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

    basi: list[Fact] = []
    for f in rows:
        umur = (now - f.observed_at).total_seconds()
        if umur > f.ttl_s:
            basi.append(f)

    dibuat = 0
    if job.payload_json.get("alert_on_basi", True):
        for f in basi:
            subjek = f"{f.kind}/{f.key}"
            sudah = s.scalar(
                select(Alert.id)
                .where(Alert.subject == subjek)
                .where(Alert.ack_at.is_(None))
                .where(Alert.created_at >= now - ALERT_DEDUPE)
                .limit(1)
            )
            if sudah is not None:
                continue
            umur_mnt = round((now - f.observed_at).total_seconds() / 60, 1)
            s.add(
                Alert(
                    severity="warning",
                    subject=subjek,
                    message=f"data basi: {subjek} umur {umur_mnt} mnt > ttl {f.ttl_s} s",
                    suggested_action=(
                        f"periksa sumber '{f.source}' (job yang menulisnya), lalu jalankan ulang job terkait"
                    ),
                    fact_ids=[f.id],
                )
            )
            dibuat += 1

    s.add(
        Event(
            type="freshness.checked",
            actor="worker",
            payload_json={"diperiksa": len(rows), "basi": len(basi), "alert_baru": dibuat},
            fact_ids=[f.id for f in basi],
            severity="warning" if basi else "info",
        )
    )
    return f"diperiksa={len(rows)} basi={len(basi)} alert_baru={dibuat}"


def handler_notify(s: SASession, job: Job) -> str:
    """Kirim alert terbuka lewat transport terkonfigurasi (P1-T8).

    Tanpa transport (default), alert tetap di DB dan dicatat `ok=false` — tidak pernah
    diklaim terkirim.
    """
    limit = int(job.payload_json.get("limit", 10))
    hasil = kirim_tertunda(s, limit=limit)
    if not hasil:
        return "tidak ada alert terbuka"
    ok = sum(1 for h in hasil if h["ok"])
    return f"dicoba={len(hasil)} terkirim={ok} gagal={len(hasil) - ok}"


def register_handlers() -> dict[str, Any]:
    """Daftarkan handler ke `schedule.HANDLERS` (dipanggil sekali saat worker start)."""
    schedule.HANDLERS.update(
        {
            "publish-facts": handler_publish_facts,
            "freshness": handler_freshness,
            "notify": handler_notify,
        }
    )
    return schedule.HANDLERS