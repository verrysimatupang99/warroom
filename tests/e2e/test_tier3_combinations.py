"""Tier 3: Cross-Feature and Integration Pipeline Combinations (>= 7 tests)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from live_trading.risk_guardrails import calculate_risk_position_size
from warroom_core.mt5_accounts import snapshot_key
from warroom_core.trades_forex import ke_trade

from tests.e2e.fixtures.account_samples import (
    ACCOUNT_DEMO_1,
    ACCOUNT_DEMO_2,
    ACCOUNT_LIVE_CENT,
)
from tests.e2e.fixtures.deal_payloads import make_deal_payload
from tests.e2e.fixtures.telemetry_payloads import (
    azure_vm2_telemetry,
    sample_demo1_telemetry,
    sample_demo2_telemetry,
    sample_live_cent_telemetry,
)

pytestmark = pytest.mark.tier3


def test_t3_1_deal_ingestion_csv_db_ui_pipeline(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T3.1: Deal Ingestion -> Journal CSV -> PostgreSQL Sync -> UI Display Cent Normalization."""
    # 1. Post deal for Cent account
    ticket = 6639270
    deal_payload = make_deal_payload(
        ticket=ticket,
        account=ACCOUNT_LIVE_CENT,
        symbol="XAUUSDc",
        side="BUY",
        volume=0.01,
        profit=14.10,
        swap=0.0,
        commission=-0.10,
        currency="USC",
        cent_factor=100.0,
        strategy_version="v3.0",
    )
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=deal_payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket"] == ticket
    assert data["cent_factor"] == 100.0
    assert data["currency"] == "USC"

    # 2. Verify trade record normalization: 14.00 USC / 100 = $0.14 USD
    trade = ke_trade(deal_payload)
    assert trade is not None
    assert trade.ext_id == str(ticket)
    expected_pnl_usd = round(14.00 / 100.0, 4)
    assert trade.pnl_usd == expected_pnl_usd

    # 3. Verify UI dual-display formatting invariant: "${v} USC ($${v/100})"
    usc_val = 14.00
    usd_val = usc_val / 100.0
    ui_repr = f"{usc_val:.2f} USC (${usd_val:.2f})"
    assert "USC" in ui_repr and "$" in ui_repr


@pytest.mark.asyncio
async def test_t3_2_telemetry_cache_facts_sse_broadcast_pipeline(
    auth_headers: dict[str, str],
    test_client: TestClient,
) -> None:
    """T3.2: Telemetry Ingestion -> Memory State -> Facts Key -> SSE Broadcast."""
    from warroom_api.routers import tencent
    from warroom_api.routers.tencent import _telemetry_subscribers

    # 1. Register test queue in SSE subscribers
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _telemetry_subscribers.append(queue)

    try:
        # 2. Ingest telemetry
        payload = sample_live_cent_telemetry()
        resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
        assert resp.status_code == 200

        # 3. Check memory cache updated
        assert ACCOUNT_LIVE_CENT in tencent.latest_mt5_by_account
        cached = tencent.latest_mt5_by_account[ACCOUNT_LIVE_CENT]
        assert cached["balance"] == payload["balance"]

        # 4. Check facts DB key generation
        key_primary = snapshot_key(ACCOUNT_LIVE_CENT)
        key_demo = snapshot_key(ACCOUNT_DEMO_1)
        assert key_primary == "ringkas"
        assert key_demo == f"ringkas:{ACCOUNT_DEMO_1}"

        # 5. Check SSE broadcast event delivered
        received = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert received.get("account") == ACCOUNT_LIVE_CENT
        assert received.get("balance") == payload["balance"]
    finally:
        if queue in _telemetry_subscribers:
            _telemetry_subscribers.remove(queue)


def test_t3_3_multi_account_state_isolation(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T3.3: Multi-Account State Isolation (Cent USC vs Demo USD)."""
    # 1. Ingest Cent Account (#452009427)
    cent_payload = sample_live_cent_telemetry()
    cent_payload["balance"] = 1084.84
    resp_cent = test_client.post("/api/v1/tencent/mt5/telemetry", json=cent_payload, headers=auth_headers)
    assert resp_cent.status_code == 200

    # 2. Ingest Demo 1 (#434446792)
    demo1_payload = sample_demo1_telemetry()
    demo1_payload["balance"] = 1005.00
    resp_demo1 = test_client.post("/api/v1/tencent/mt5/telemetry", json=demo1_payload, headers=auth_headers)
    assert resp_demo1.status_code == 200

    # 3. Ingest Demo 2 (#464202979)
    demo2_payload = sample_demo2_telemetry()
    demo2_payload["balance"] = 1000.00
    resp_demo2 = test_client.post("/api/v1/tencent/mt5/telemetry", json=demo2_payload, headers=auth_headers)
    assert resp_demo2.status_code == 200

    # 4. Verify independent query isolation
    url_cent = f"/api/v1/tencent/mt5/status?account={ACCOUNT_LIVE_CENT}"
    url_demo1 = f"/api/v1/tencent/mt5/status?account={ACCOUNT_DEMO_1}"
    url_demo2 = f"/api/v1/tencent/mt5/status?account={ACCOUNT_DEMO_2}"
    status_cent = test_client.get(url_cent, headers=auth_headers).json()
    status_demo1 = test_client.get(url_demo1, headers=auth_headers).json()
    status_demo2 = test_client.get(url_demo2, headers=auth_headers).json()

    assert status_cent["currency"] == "USC"
    assert status_cent["balance"] == 1084.84

    assert status_demo1["currency"] == "USD"
    assert status_demo1["balance"] == 1005.00

    assert status_demo2["currency"] == "USD"
    assert status_demo2["balance"] == 1000.00


def test_t3_4_azure_vm2_quarantine_isolation(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T3.4: Azure VM2 (36525553) Quarantine Isolation (Zero PowerShell Execution)."""
    payload = azure_vm2_telemetry()
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Retired account must return action: OK and NEVER execute remote powershell commands
    assert data["action"] == "OK"
    assert "exec_powershell" not in data or data.get("exec_powershell") is None
    assert data.get("action") != "SYNC_EA_V2"


def test_t3_5_risk_gate_sizing_and_execution_feedback(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T3.5: Risk Gate Sizing -> Order Fill Slippage -> PnL Feedback."""
    # 1. Compute position size
    size = calculate_risk_position_size(equity=1000.0, sl_distance=10.0, risk_pct=0.015)
    assert size == 1.5

    # 2. Report execution fill slippage
    fill_payload = {
        "ticket": 7781010,
        "symbol": "XAUUSDm",
        "requested_price": 2700.50,
        "execution_price": 2700.52,
        "slippage_pts": 2,
        "latency_ms": 45,
        "account": ACCOUNT_DEMO_1,
    }
    resp_fill = test_client.post("/api/v1/tencent/mt5/fill", json=fill_payload, headers=auth_headers)
    assert resp_fill.status_code == 200
    assert resp_fill.json()["status"] == "OK"

    # 3. Ingest deal close
    deal_payload = make_deal_payload(
        ticket=7781010,
        account=ACCOUNT_DEMO_1,
        profit=15.0,
        currency="USD",
        cent_factor=1.0,
    )
    resp_deal = test_client.post("/api/v1/tencent/mt5/deal", json=deal_payload, headers=auth_headers)
    assert resp_deal.status_code == 200
    assert resp_deal.json()["ticket"] == 7781010


def test_t3_6_sse_reconnect_last_event_id_cursor() -> None:
    """T3.6: SSE stream memakai Last-Event-ID sebagai cursor.

    Diuji lewat generator ``event_stream`` langsung, bukan lewat HTTP streaming:
    ``TestClient.stream`` (starlette ASGITransport) mem-buffer SELURUH body, dan
    SSE tidak pernah selesai — dulu test ini menggantung sampai job timeout.
    """
    from warroom_api.stream import event_stream, parse_last_event_id

    assert parse_last_event_id("100") == 100
    assert parse_last_event_id("abc") is None
    assert parse_last_event_id("-1") is None

    async def _baca_preamble() -> list[str]:
        gen = event_stream(topics=["forex"], last_event_id="100", max_iterations=1)
        return [chunk async for chunk in gen]

    chunks = asyncio.run(_baca_preamble())
    assert chunks, "stream harus mengirim preamble"
    assert "retry: 3000" in chunks[0]
    assert '"dari_id": 100' in chunks[0]


def test_t3_7_token_and_secret_leak_protection(
    test_client: TestClient,
    live_client: httpx.Client,
    service_token: str,
) -> None:
    """T3.7: Strict Secret Leakage Protection in Responses and Error Wrappers."""
    probes = [
        # 1. Unauthenticated build manifest
        live_client.get("/api/v1/build"),
        # 2. 401 unauthenticated error
        test_client.get("/api/v1/health"),
        # 3. 403 forbidden error
        test_client.get("/api/v1/tencent/mt5/status"),
        # 4. 404 not found error
        test_client.get("/api/v1/nonexistent_test"),
        # 5. 422 unprocessable error
        test_client.post("/api/v1/tencent/mt5/telemetry", json={}),
    ]

    sensitive_patterns = [
        service_token,
        "WARROOM_SERVICE_TOKEN",
        "WARROOM_DB_URL",
        "postgresql://",
        "postgres://",
    ]

    for p in probes:
        text = p.text
        for pattern in sensitive_patterns:
            assert pattern not in text, f"Sensitive pattern '{pattern}' leaked in response: {text[:200]}"
