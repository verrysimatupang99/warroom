"""Tes kebijakan telemetri pensiun: fakta arsip tidak boleh dihitung basi."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from warroom_api import auth
from warroom_core.db import Fact, Heartbeat, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def _bersihkan() -> None:
    with session_scope() as s:
        s.execute(delete(Fact))
        s.execute(delete(Heartbeat))


def test_freshness_dan_readiness_mengabaikan_fakta_pensiun(client, make_user) -> None:
    _, sid = make_user("retired-view", role="viewer")
    now = datetime.now(UTC)
    try:
        with session_scope() as s:
            s.execute(delete(Fact))
            s.execute(delete(Heartbeat))
            s.add(Fact(
                kind="mt5_snapshot", key="ringkas", value_json={}, source="EA telemetry",
                observed_at=now - timedelta(hours=12), ttl_s=300, hash="h1",
            ))
            s.add(Fact(
                kind="signal", key="BTCUSDT", value_json={}, source="ledger",
                observed_at=now - timedelta(hours=20), ttl_s=21600, hash="h2",
            ))
        r = client.get("/api/v1/freshness", headers=_cookie(sid))
        assert r.status_code == 200
        data = r.json()
        kinds = {(f["kind"], f["key"]) for f in data["facts"]}
        assert ("mt5_snapshot", "ringkas") not in kinds
        assert ("signal", "BTCUSDT") in kinds

        r = client.get("/api/v1/ready", headers=_cookie(sid))
        body = r.json()
        assert body["status"] == "ready"
        assert body["freshness"]["count"] == 1
    finally:
        _bersihkan()
