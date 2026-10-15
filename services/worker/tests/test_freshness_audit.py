"""Tes audit kesegaran per sumber di job `freshness`.

Yang diuji:
- ringkasan per sumber (fakta, basi, ttl, umur maksimal) ikut tercatat di event;
- peringkat "paling sering basi" dihitung dari riwayat alert (bukan satu momen);
- job detail menyebut sumber paling sering basi supaya terbaca di journald.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from warroom_core.db import Alert, Event, Fact, Job, session_scope
from warroom_worker import schedule
from warroom_worker.jobs import register_handlers


@pytest.fixture(autouse=True)
def _bersihkan(db):
    from sqlalchemy import delete as sa_delete
    from warroom_core.db import Strategy

    with session_scope() as s:
        for model in (Fact, Event, Alert, Job, Strategy):
            s.execute(sa_delete(model))
    register_handlers()
    yield


def _fakta(kind: str, key: str, umur_s: int, ttl_s: int = 600, source: str = "uji") -> Fact:
    return Fact(
        kind=kind,
        key=key,
        value_json={"x": 1},
        source=source,
        observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
        ttl_s=ttl_s,
        hash="h",
    )


def _jalankan_freshness() -> tuple[str, str]:
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "freshness"))
        return schedule.run_one(s, job)


def test_audit_per_sumber_tercatat_di_event(db) -> None:
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", umur_s=7200, ttl_s=600, source="state/snapshot.json"))
        s.add(_fakta("gmgn", "radar", umur_s=3600, ttl_s=600, source="radar_state.json"))
        s.add(_fakta("snapshot", "equity", umur_s=10, ttl_s=600, source="state/snapshot.json"))
    status, detail = _jalankan_freshness()
    assert status == "ok"
    with session_scope() as s:
        ev = s.scalars(
            select(Event).where(Event.type == "freshness.checked").order_by(Event.id.desc())
        ).first()
    audit = ev.payload_json["audit_sumber"]
    snap = audit["per_sumber"]["state/snapshot.json"]
    assert snap["fakta"] == 2 and snap["basi"] == 1
    assert snap["ttl_s"] == [600]
    assert snap["umur_maks_mnt"] > 100
    radar = audit["per_sumber"]["radar_state.json"]
    assert radar["fakta"] == 1 and radar["basi"] == 1


def test_audit_kejadian_basi_dari_riwayat_alert(db) -> None:
    """Peringkat dihitung dari alert 'data basi' pada jendela — bukan hanya basi sesaat."""
    with session_scope() as s:
        for i in range(3):
            s.add(
                Alert(
                    severity="warning",
                    subject="snapshot/sejarah",
                    message=f"data basi: snapshot/sejarah umur {i} mnt",
                    created_at=datetime.now(UTC) - timedelta(days=i),
                )
            )
        # di luar jendela 7 hari → tidak boleh dihitung
        s.add(
            Alert(
                severity="warning",
                subject="snapshot/tua-sekali",
                message="data basi: snapshot/tua-sekali umur lama",
                created_at=datetime.now(UTC) - timedelta(days=30),
            )
        )
        # alert non-kesegaran tidak ikut
        s.add(Alert(severity="info", subject="ops/disk-80", message="pemakaian disk 81%"))
    status, _ = _jalankan_freshness()
    assert status == "ok"
    with session_scope() as s:
        ev = s.scalars(
            select(Event).where(Event.type == "freshness.checked").order_by(Event.id.desc())
        ).first()
    audit = ev.payload_json["audit_sumber"]
    assert audit["kejadian_basi"] == {"snapshot/sejarah": 3}
    assert audit["jendela_hari"] == 7


def test_job_detail_menyebut_sumber_paling_sering_basi(db) -> None:
    with session_scope() as s:
        for i in range(2):
            s.add(
                Alert(
                    severity="warning",
                    subject="gmgn/radar",
                    message="data basi: gmgn/radar",
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
    _, detail = _jalankan_freshness()
    assert "paling_sering_basi=gmgn/radar" in detail


def test_jendela_kejadian_bisa_ditimpa_lewat_payload(db) -> None:
    with session_scope() as s:
        s.add(
            Alert(
                severity="warning",
                subject="snapshot/kemarin",
                message="data basi: snapshot/kemarin",
                created_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "freshness"))
        job.payload_json = {**job.payload_json, "audit_jendela_hari": 1}
        status, _ = schedule.run_one(s, job)
    assert status == "ok"
    with session_scope() as s:
        ev = s.scalars(
            select(Event).where(Event.type == "freshness.checked").order_by(Event.id.desc())
        ).first()
    assert ev.payload_json["audit_sumber"]["kejadian_basi"] == {}
