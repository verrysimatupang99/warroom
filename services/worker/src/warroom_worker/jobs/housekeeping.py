"""Handler job housekeeping: retensi."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as SASession
from warroom_core import retention
from warroom_core.db import Job

log = logging.getLogger("warroom_worker.jobs")


def handler_retensi(s: SASession, job: Job) -> str:
    """Retensi data terjadwal (P5): batasi pertumbuhan `facts` tanpa menghapus yang dipakai.

    Simpan `keep_versi` versi terbaru per (kind,key). Default TIDAK menghapus `events`
    (jejak audit) — operator bisa menyalakannya lewat payload hapus_events=true.
    """

    hasil = retention.jalankan(
        s,
        keep_versi=int(job.payload_json.get("keep_versi", retention.KEEP_VERSI_DEFAULT)),
        events_hari=int(job.payload_json.get("events_hari", retention.EVENTS_HARI_DEFAULT)),
        hapus_events=bool(job.payload_json.get("hapus_events", False)),
        noisy_events_hari=int(job.payload_json.get("noisy_events_hari", retention.NOISY_EVENTS_HARI_DEFAULT)),
    )
    d = hasil["dihapus"]
    return (
        f"facts_dihapus={d['facts']} events_dihapus={d['events']} "
        f"noisy_dihapus={d.get('noisy_events', 0)} "
        f"sessions_dihapus={d.get('sessions', 0)} "
        f"(simpan {hasil['rencana']['keep_versi']} versi/kunci)"
    )


