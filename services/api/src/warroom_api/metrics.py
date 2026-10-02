"""Metrik Prometheus + log JSON (P1-T8).

Sumber semua angka adalah DB — tidak ada penghitung di memori yang bisa berbeda antar
proses. Format teks Prometheus ditulis tangan (tanpa dependensi tambahan).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event, Fact, Job

__all__ = ["collect_metrics", "render_prometheus", "setup_json_logging"]

_START = time.time()


def setup_json_logging(service: str, level: int = logging.INFO) -> None:
    """Log JSON satu baris ke stdout — journald membacanya tanpa parsing rapuh."""

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:  # noqa: A003
            payload: dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "svc": service,
                "level": record.levelname,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                payload["exc"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def collect_metrics(s: SASession, now: datetime | None = None) -> dict[str, Any]:
    """Hitungan mentah dari DB (dipakai untuk render maupun observasi)."""
    t = now or datetime.now(UTC)

    total = s.scalar(select(func.count()).select_from(Fact)) or 0
    sub = select(Fact.key, func.max(Fact.observed_at).label("obs")).group_by(Fact.key).subquery()
    terbaru = s.scalars(
        select(Fact).join(sub, (Fact.key == sub.c.key) & (Fact.observed_at == sub.c.obs))
    ).all()
    basi = sum(1 for f in terbaru if (t - f.observed_at).total_seconds() > f.ttl_s)

    per_tipe = dict(
        s.execute(select(Event.type, func.count()).group_by(Event.type)).all()  # type: ignore[arg-type]
    )
    alert_terbuka = (
        s.scalar(select(func.count()).select_from(Alert).where(Alert.ack_at.is_(None))) or 0
    )
    jobs = s.scalars(select(Job)).all()

    return {
        "facts_total": total,
        "facts_basi": basi,
        "facts_terbaru": len(terbaru),
        "events_per_tipe": per_tipe,
        "events_total": sum(per_tipe.values()),
        "alerts_terbuka": alert_terbuka,
        "jobs": [
            {
                "name": j.name,
                "enabled": j.enabled,
                "last_status": j.last_status or "belum-jalan",
                "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
                "umur_detik": round((t - j.last_run_at).total_seconds(), 1) if j.last_run_at else None,
            }
            for j in jobs
        ],
        "uptime_s": round(time.time() - _START, 1),
    }


def render_prometheus(m: dict[str, Any]) -> str:
    """Format teks eksposisi Prometheus (v0.0.4)."""
    L: list[str] = []
    L.append("# HELP warroom_up Proses API hidup (selalu 1 bila endpoint ini menjawab).")
    L.append("# TYPE warroom_up gauge")
    L.append("warroom_up 1")
    L.append("# HELP warroom_uptime_seconds Umur proses API.")
    L.append("# TYPE warroom_uptime_seconds gauge")
    L.append(f"warroom_uptime_seconds {m['uptime_s']}")
    L.append("# HELP warroom_facts_total Jumlah baris fakta tersimpan.")
    L.append("# TYPE warroom_facts_total gauge")
    L.append(f"warroom_facts_total {m['facts_total']}")
    L.append("# HELP warroom_facts_basi Fakta terbaru yang sudah melewati TTL-nya.")
    L.append("# TYPE warroom_facts_basi gauge")
    L.append(f"warroom_facts_basi {m['facts_basi']}")
    L.append("# HELP warroom_alerts_open Alert yang belum di-ack.")
    L.append("# TYPE warroom_alerts_open gauge")
    L.append(f"warroom_alerts_open {m['alerts_terbuka']}")
    L.append("# HELP warroom_events_total Jumlah event per tipe.")
    L.append("# TYPE warroom_events_total counter")
    for tipe, n in sorted(m["events_per_tipe"].items()):
        L.append(f'warroom_events_total{{type="{tipe}"}} {n}')
    L.append("# HELP warroom_job_last_run_seconds Umur sejak job terakhir jalan.")
    L.append("# TYPE warroom_job_last_run_seconds gauge")
    L.append("# HELP warroom_job_enabled 1 bila job aktif.")
    L.append("# TYPE warroom_job_enabled gauge")
    for j in m["jobs"]:
        L.append(f'warroom_job_enabled{{job="{j["name"]}"}} {1 if j["enabled"] else 0}')
        if j["umur_detik"] is not None:
            L.append(f'warroom_job_last_run_seconds{{job="{j["name"]}"}} {j["umur_detik"]}')
    return "\n".join(L) + "\n"