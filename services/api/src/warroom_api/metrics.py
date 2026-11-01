"""Metrik Prometheus + log JSON (P1-T8).

Sumber semua angka adalah DB — tidak ada penghitung di memori yang bisa berbeda antar
proses. Format teks Prometheus ditulis tangan (tanpa dependensi tambahan).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event, Fact, Heartbeat, Job
from warroom_core.telemetry_policy import is_retired

__all__ = ["collect_metrics", "collect_readiness", "render_prometheus", "setup_json_logging"]

_START = time.time()
MAX_LABEL_VALUES = 50
MAX_STALE_FACTS = 100
DEFAULT_HEARTBEAT_STALE_S = 300


def _heartbeat_stale_after() -> int:
    try:
        return max(1, int(os.environ.get("WARROOM_HEARTBEAT_STALE_S", DEFAULT_HEARTBEAT_STALE_S)))
    except ValueError:
        return DEFAULT_HEARTBEAT_STALE_S


def collect_readiness(s: SASession, now: datetime | None = None) -> dict[str, Any]:
    """Return only states evidenced by DB rows; missing heartbeat data is unknown."""
    t = now or datetime.now(UTC)
    sub = (
        select(Heartbeat.host, Heartbeat.unit, func.max(Heartbeat.beat_at).label("beat"))
        .group_by(Heartbeat.host, Heartbeat.unit)
        .subquery()
    )
    beats = s.execute(
        select(Heartbeat).join(
            sub,
            (Heartbeat.host == sub.c.host)
            & (Heartbeat.unit == sub.c.unit)
            & (Heartbeat.beat_at == sub.c.beat),
        )
    ).scalars().all()
    stale_after = _heartbeat_stale_after()
    heartbeat_items = [
        {
            "host": h.host,
            "unit": h.unit,
            "beat_at": h.beat_at.isoformat(),
            "age_s": round(max(0.0, (t - h.beat_at).total_seconds()), 1),
            "status": "ok" if (t - h.beat_at).total_seconds() <= stale_after else "stale",
        }
        for h in beats
    ]
    heartbeat_status = (
        "unknown" if not heartbeat_items else
        "stale" if any(i["status"] == "stale" for i in heartbeat_items) else "ok"
    )

    latest = (
        select(Fact.kind, Fact.key, func.max(Fact.observed_at).label("obs"))
        .group_by(Fact.kind, Fact.key)
        .subquery()
    )
    facts = s.scalars(
        select(Fact).join(
            latest,
            (Fact.kind == latest.c.kind)
            & (Fact.key == latest.c.key)
            & (Fact.observed_at == latest.c.obs),
        )
    ).all()
    stale_facts = [
        {
            "kind": f.kind,
            "key": f.key,
            "source": f.source,
            "observed_at": f.observed_at.isoformat(),
            "age_s": round(max(0.0, (t - f.observed_at).total_seconds()), 1),
            "ttl_s": f.ttl_s,
        }
        for f in facts
        if (t - f.observed_at).total_seconds() > f.ttl_s and not is_retired(f.kind, f.key)
    ][:MAX_STALE_FACTS]
    return {
        "database": "ok",
        "worker_heartbeats": {
            "status": heartbeat_status,
            "count": len(heartbeat_items),
            "stale_after_s": stale_after,
            "items": heartbeat_items[:MAX_STALE_FACTS],
        },
        "stale_facts": {
            "status": "stale" if stale_facts else "ok",
            "count": len(stale_facts),
            "items": stale_facts,
        },
    }


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
    # Fakta terbaru per (kind, key) — kunci yang sama bisa dipakai lebih dari satu kind
    # (`radar`, `ringkas`), jadi grouping harus menyertakan kind atau hitungan basi salah.
    sub = (
        select(Fact.kind, Fact.key, func.max(Fact.observed_at).label("obs"))
        .group_by(Fact.kind, Fact.key)
        .subquery()
    )
    terbaru = s.scalars(
        select(Fact).join(
            sub,
            (Fact.kind == sub.c.kind)
            & (Fact.key == sub.c.key)
            & (Fact.observed_at == sub.c.obs),
        )
    ).all()
    terbaru = [f for f in terbaru if not is_retired(f.kind, f.key)]
    basi = sum(1 for f in terbaru if (t - f.observed_at).total_seconds() > f.ttl_s)

    per_tipe = dict(
        s.execute(select(Event.type, func.count()).group_by(Event.type)).all()  # type: ignore[arg-type]
    )
    alert_terbuka = (
        s.scalar(select(func.count()).select_from(Alert).where(Alert.ack_at.is_(None))) or 0
    )
    jobs = s.scalars(select(Job)).all()
    readiness = collect_readiness(s, t)

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
        "readiness": readiness,
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
    def label(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    events = sorted(m["events_per_tipe"].items())
    for tipe, n in events[:MAX_LABEL_VALUES]:
        L.append(f'warroom_events_total{{type="{label(tipe)}"}} {n}')
    if len(events) > MAX_LABEL_VALUES:
        L.append(f'warroom_events_total{{type="other"}} {sum(n for _, n in events[MAX_LABEL_VALUES:])}')
    L.append("# HELP warroom_job_last_run_seconds Umur sejak job terakhir jalan.")
    L.append("# TYPE warroom_job_last_run_seconds gauge")
    L.append("# HELP warroom_job_enabled 1 bila job aktif.")
    L.append("# TYPE warroom_job_enabled gauge")
    for j in m["jobs"][:MAX_LABEL_VALUES]:
        L.append(f'warroom_job_enabled{{job="{label(j["name"])}"}} {1 if j["enabled"] else 0}')
        if j["umur_detik"] is not None:
            L.append(f'warroom_job_last_run_seconds{{job="{label(j["name"])}"}} {j["umur_detik"]}')
    if len(m["jobs"]) > MAX_LABEL_VALUES:
        L.append("# HELP warroom_jobs_omitted Number of jobs omitted to bound label cardinality.")
        L.append("# TYPE warroom_jobs_omitted gauge")
        L.append(f"warroom_jobs_omitted {len(m['jobs']) - MAX_LABEL_VALUES}")
    readiness = m.get("readiness", {})
    L.append("# HELP warroom_readiness Whether an evidenced readiness check is healthy.")
    L.append("# TYPE warroom_readiness gauge")
    for check in ("database", "worker_heartbeats", "stale_facts"):
        state = readiness.get(check, "unknown")
        if isinstance(state, dict):
            state = state.get("status", "unknown")
        L.append(f'warroom_readiness{{check="{check}"}} {1 if state == "ok" else 0}')
    hb = readiness.get("worker_heartbeats", {})
    L.append("# HELP warroom_worker_heartbeats Number of latest worker heartbeat rows observed.")
    L.append("# TYPE warroom_worker_heartbeats gauge")
    L.append(f"warroom_worker_heartbeats {hb.get('count', 0) if isinstance(hb, dict) else 0}")
    return "\n".join(L) + "\n"