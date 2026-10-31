"""Tes panel cron lokal: membaca `jobs` dan `events`, bukan proxy Tencent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from warroom_api import auth
from warroom_core.db import Event, Job, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def _bersihkan() -> None:
    with session_scope() as s:
        s.execute(delete(Event).where(Event.actor == "uji-cron"))
        s.execute(delete(Job).where(Job.name.like("uji-cron-%")))


def _siapkan() -> tuple[int, int]:
    now = datetime.now(UTC)
    with session_scope() as s:
        ok = Job(
            name="uji-cron-ok",
            interval_s=300,
            enabled=True,
            payload_json={"x": 1},
            note="job uji",
            last_run_at=now - timedelta(seconds=60),
            last_status="ok",
            last_detail="selesai",
        )
        gagal = Job(
            name="uji-cron-gagal",
            interval_s=3600,
            enabled=False,
            payload_json={},
            note="job gagal",
            last_run_at=now - timedelta(seconds=30),
            last_status="gagal",
            last_detail="RuntimeError: jaringan",
        )
        s.add_all([ok, gagal])
        s.flush()
        s.add_all(
            [
                Event(
                    type="job.ran",
                    actor="uji-cron",
                    payload_json={"job": "uji-cron-ok", "status": "ok", "detail": "selesai"},
                ),
                Event(
                    type="job.ran",
                    actor="uji-cron",
                    payload_json={
                        "job": "uji-cron-gagal",
                        "status": "gagal",
                        "detail": "RuntimeError: jaringan",
                    },
                    severity="warning",
                ),
            ]
        )
        return ok.id, gagal.id


def test_cron_lokal_membaca_jobs_dan_events(client, make_user) -> None:
    _, sid = make_user("cron-view", role="viewer")
    try:
        ok_id, gagal_id = _siapkan()

        r = client.get("/api/v1/cron/jobs", headers=_cookie(sid))
        assert r.status_code == 200
        data = r.json()
        assert data["sumber"] == "lokal:jobs"
        per_nama = {j["name"]: j for j in data["jobs"]}
        assert per_nama["uji-cron-ok"]["last_status"] == "ok"
        assert per_nama["uji-cron-ok"]["enabled"] is True
        assert per_nama["uji-cron-ok"]["umur_detik"] >= 0
        assert per_nama["uji-cron-gagal"]["last_status"] == "gagal"

        r = client.get("/api/v1/cron/jobs/uji-cron-gagal", headers=_cookie(sid))
        assert r.status_code == 200
        assert r.json()["job"]["id"] == gagal_id
        r = client.get(f"/api/v1/cron/jobs/{ok_id}", headers=_cookie(sid))
        assert r.status_code == 200
        assert r.json()["job"]["name"] == "uji-cron-ok"

        r = client.get("/api/v1/cron/summary", headers=_cookie(sid))
        assert r.status_code == 200
        ringkas = r.json()
        assert ringkas["sumber"] == "lokal:jobs"
        assert ringkas["status_terakhir"]["ok"] >= 1
        assert ringkas["status_terakhir"]["gagal"] >= 1
        assert ringkas["terakhir_gagal"]["job"] == "uji-cron-gagal"

        r = client.get("/api/v1/cron/executions?limit=2", headers=_cookie(sid))
        assert r.status_code == 200
        eksekusi = r.json()["eksekusi"]
        assert eksekusi[0]["job"] == "uji-cron-gagal"
        assert eksekusi[0]["status"] == "gagal"
        assert eksekusi[0]["at"] is not None

        r = client.get("/api/v1/cron/jobs/tidak-ada", headers=_cookie(sid))
        assert r.status_code == 404
    finally:
        _bersihkan()
