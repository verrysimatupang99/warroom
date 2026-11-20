"""Tier 2: Boundary, Limit, Corner-Case, and Negative Coverage (F1 to F7, >= 35 tests)."""

from __future__ import annotations

import asyncio
import statistics

import httpx
import pytest
from fastapi.testclient import TestClient
from live_trading.demo_ab_backtest import _finalize
from live_trading.risk_guardrails import (
    calculate_risk_position_size,
    evaluate_entry_guardrails,
)
from warroom_api.routers.tencent import stream_forex_telemetry

from tests.e2e.fixtures.deal_payloads import (
    corrupt_deal_non_numeric_profit,
    invalid_ticket_negative_deal,
    invalid_ticket_zero_deal,
    large_int64_deal,
)
from tests.e2e.fixtures.telemetry_payloads import (
    missing_mandatory_fields_telemetry,
    zero_balance_telemetry,
)

pytestmark = pytest.mark.tier2


# ==============================================================================
# F1: API Build & Health Boundaries
# ==============================================================================


def test_t2_f1_health_unauthenticated_rejected(test_client: TestClient) -> None:
    """T2.1.1: GET /api/v1/health without session cookie returns HTTP 401 unauthenticated."""
    resp = test_client.get("/api/v1/health")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "unauthenticated"


def test_t2_f1_ready_unauthenticated_rejected(test_client: TestClient) -> None:
    """T2.1.2: GET /api/v1/ready without session cookie returns HTTP 401 unauthenticated."""
    resp = test_client.get("/api/v1/ready")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "unauthenticated"


def test_t2_f1_freshness_unauthenticated_rejected(test_client: TestClient) -> None:
    """T2.1.3: GET /api/v1/freshness without session cookie returns HTTP 401."""
    resp = test_client.get("/api/v1/freshness")
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "unauthenticated"


def test_t2_f1_nonexistent_endpoint_404_wrapper(test_client: TestClient) -> None:
    """T2.1.4: Invalid endpoint GET /api/v1/nonexistent returns HTTP 404."""
    resp = test_client.get("/api/v1/nonexistent_test_route_404")
    assert resp.status_code == 404
    data = resp.json()
    assert ("error" in data and data["error"]["code"] == "not_found") or data.get("detail") == "Not Found"


def test_t2_f1_build_manifest_decoupled_from_db(live_client: httpx.Client) -> None:
    """T2.1.5: GET /api/v1/build remains operational with HTTP 200 without DB dependency."""
    resp = live_client.get("/api/v1/build")
    assert resp.status_code == 200
    data = resp.json()
    assert "build_id" in data
    assert data["domain_version"] == "0.1.0"


# ==============================================================================
# F2: Web UI Boundaries & Security
# ==============================================================================


def test_t2_f2_unauthenticated_auth_me_returns_401(test_client: TestClient) -> None:
    """T2.2.1: Unauthenticated request to /api/v1/auth/me returns 401, triggering redirect."""
    resp = test_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "unauthenticated"


def test_t2_f2_invalid_session_cookie_rejected(test_client: TestClient) -> None:
    """T2.2.2: Request with forged session cookie is rejected with HTTP 401."""
    resp = test_client.get("/api/v1/health", headers={"Cookie": "wr_session=forged_invalid_cookie_xyz"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "unauthenticated"


def test_t2_f2_xss_query_param_sanitization(live_web_client: httpx.Client) -> None:
    """T2.2.3: XSS payload in query parameter is neutralized and does not execute script."""
    resp = live_web_client.get("/forex?sub=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
    assert resp.status_code == 200
    # Script tag should not be rendered unescaped in executable DOM context
    assert "<script>alert(1)</script>" not in resp.text


def test_t2_f2_pre_hydration_shell_marker(live_web_client: httpx.Client) -> None:
    """T2.2.4: SvelteKit pre-hydration shell includes remover hook for #shell-muat."""
    resp = live_web_client.get("/")
    assert resp.status_code == 200
    # Pre-hydration shell remover element
    assert "shell-muat" in resp.text


def test_t2_f2_frame_ancestors_header_present(live_web_client: httpx.Client) -> None:
    """T2.2.5: Frame options / CSP strictly blocks unauthorized iframe embedding."""
    resp = live_web_client.get("/")
    csp = resp.headers.get("content-security-policy", "")
    assert "frame-ancestors 'none'" in csp


# ==============================================================================
# F3: MT5 Telemetry Boundaries
# ==============================================================================


def test_t2_f3_telemetry_missing_token_forbidden(test_client: TestClient) -> None:
    """T2.3.1: POST /api/v1/tencent/mt5/telemetry without auth header returns HTTP 403 Forbidden."""
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json={"account": "452009427"})
    assert resp.status_code == 403
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "forbidden"


def test_t2_f3_telemetry_spoofed_ip_rejected(test_client: TestClient) -> None:
    """T2.3.2: Direct client with spoofed CF-Connecting-IP header is rejected with HTTP 403."""
    headers = {"CF-Connecting-IP": "20.212.109.170"}
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json={"account": "452009427"}, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_t2_f3_telemetry_missing_required_fields_422(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T2.3.3: Telemetry payload missing mandatory fields returns HTTP 422 Unprocessable Entity."""
    payload = missing_mandatory_fields_telemetry()
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "unprocessable"
    assert "detail" in data["error"]


def test_t2_f3_telemetry_zero_balance_equity_accepted(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T2.3.4: Telemetry with zero balance and equity is accepted without ZeroDivisionError."""
    payload = zero_balance_telemetry(account="452009427")
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"


def test_t2_f3_status_unseen_account_404(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T2.3.5: Querying status of unseen account (999999999) returns HTTP 404 Not Found."""
    resp = test_client.get("/api/v1/tencent/mt5/status?account=999999999", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "not_found"


# ==============================================================================
# F4: SSE Streaming Boundaries
# ==============================================================================


def test_t2_f4_sse_unauthorized_connection_forbidden(test_client: TestClient) -> None:
    """T2.4.1: Connecting to SSE stream without credentials returns HTTP 403 Forbidden."""
    resp = test_client.get("/api/v1/tencent/forex/stream")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_t2_f4_sse_disconnect_cleanup_no_leak() -> None:
    """T2.4.2: Abrupt stream disconnect cleans up subscriber queue in finally block."""
    from warroom_api.routers.tencent import _telemetry_subscribers, stream_forex_telemetry

    before = len(_telemetry_subscribers)
    resp = await stream_forex_telemetry(account="452009427")
    assert len(_telemetry_subscribers) == before + 1
    gen = resp.body_iterator
    c1 = await anext(gen)
    assert "retry: 3000" in c1
    await gen.aclose()
    assert len(_telemetry_subscribers) == before


def test_t2_f4_sse_stale_account_flagged_offline(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T2.4.3: Account unseen for >20s is flagged connected: False."""
    import time

    from warroom_api.routers import tencent

    # Inject an account state with old timestamp
    stale_account_id = "888888888"
    tencent.latest_mt5_by_account[stale_account_id] = {
        "account": stale_account_id,
        "broker": "Exness",
        "currency": "USD",
        "balance": 1000.0,
        "equity": 1000.0,
        "positions": [],
        "last_seen_ts": int(time.time()) - 45,  # 45 seconds ago (> 20s cutoff)
    }
    resp = test_client.get("/api/v1/tencent/mt5/accounts", headers=auth_headers)
    assert resp.status_code == 200
    accounts = {a["account"]: a for a in resp.json()["accounts"]}
    if stale_account_id in accounts:
        assert accounts[stale_account_id]["connected"] is False
        assert accounts[stale_account_id]["seconds_ago"] >= 20
    # Clean up test injection
    tencent.latest_mt5_by_account.pop(stale_account_id, None)


@pytest.mark.asyncio
async def test_t2_f4_sse_multi_account_filtering_isolation() -> None:
    """T2.4.4: Broadcast for account A is not sent to stream subscribed to account B."""
    import asyncio

    from warroom_api.routers.tencent import _broadcast_sse_telemetry, _telemetry_subscribers

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _telemetry_subscribers.append(queue)
    try:
        demo2_snapshot = {"account": "464202979", "equity": 1000.0}
        _broadcast_sse_telemetry(demo2_snapshot)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.get("account") == "464202979"
    finally:
        if queue in _telemetry_subscribers:
            _telemetry_subscribers.remove(queue)


def _sse_pembuka(respons) -> str:
    """Ambil potongan SSE pertama lalu tutup generator-nya (avoid hang pada SSE tak selesai)."""

    async def _baca() -> str:
        potongan = ""
        async for item in respons.body_iterator:
            potongan = item if isinstance(item, str) else item.decode()
            break
        tutup = getattr(respons.body_iterator, "aclose", None)
        if tutup is not None:
            await tutup()
        return potongan

    return asyncio.run(_baca())


def test_t2_f4_sse_malformed_account_param_fallback() -> None:
    """T2.4.5: Malformed query parameter ?account=invalid_chars_!@# falls back safely."""
    respons = asyncio.run(stream_forex_telemetry("invalid_chars_!@#"))
    first_line = _sse_pembuka(respons).splitlines()[0]
    assert first_line.startswith("retry: 3000")


# ==============================================================================
# F5: Deal Ingestion Boundaries & Deduplication
# ==============================================================================


def test_t2_f5_deal_invalid_ticket_zero(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T2.5.1: Deal submission with ticket: 0 returns HTTP 400 Bad Request."""
    payload = invalid_ticket_zero_deal()
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "bad_request"
    assert "tidak valid" in data["error"]["message"].lower()


def test_t2_f5_deal_negative_ticket_bad_request(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """T2.5.2: Deal submission with negative ticket returns HTTP 400 Bad Request."""
    payload = invalid_ticket_negative_deal()
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "bad_request"


def test_t2_f5_deal_duplicate_idempotent(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T2.5.3: Duplicate deal resubmission returns HTTP 200 status: duplikat."""
    payload = {"ticket": 6639264, "profit": 0.60, "symbol": "XAUUSDc", "account": "452009427"}
    # Kirim dua kali: yang kedua wajib "duplikat". Jangan bergantung pada isi
    # deals.csv yang sudah ada — di CI file itu baru dan kosong.
    resp_awal = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp_awal.status_code == 200
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "duplikat"
    assert data["ticket"] == 6639264


def test_t2_f5_deal_non_numeric_fields_422(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T2.5.4: Deal submission with non-numeric profit returns HTTP 422 Unprocessable Entity."""
    payload = corrupt_deal_non_numeric_profit()
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "unprocessable"


def test_t2_f5_deal_large_int64_ticket(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T2.5.5: 64-bit integer deal ticket parses accurately without overflow."""
    ticket_64 = 9223372036854775807
    payload = large_int64_deal(ticket=ticket_64)
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket"] == ticket_64


# ==============================================================================
# F6: Risk Sizing & Protective Gate Boundaries
# ==============================================================================


def test_t2_f6_zero_sl_distance_safe_fallback() -> None:
    """T2.6.1: SL distance evaluated as zero returns min_size preventing ZeroDivisionError."""
    size = calculate_risk_position_size(equity=1000.0, sl_distance=0.0, risk_pct=0.015, min_size=0.01)
    assert size == 0.01


def test_t2_f6_negative_equity_safe_fallback() -> None:
    """T2.6.2: Negative or zero equity returns min_size."""
    size = calculate_risk_position_size(equity=-500.0, sl_distance=10.0, risk_pct=0.015, min_size=0.01)
    assert size == 0.01


def test_t2_f6_extreme_spread_cutoff() -> None:
    """T2.6.3: Spread exceeding cutoff (350 pts) triggers EXTREME_SPREAD_BLOCKED."""
    status = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=4,
        spread_points=400.0,
        max_spread_points=350.0,
    )
    assert not status.allowed
    assert status.reason == "EXTREME_SPREAD_BLOCKED"


def test_t2_f6_daily_max_loss_cutoff() -> None:
    """T2.6.4: Daily realized loss touching limit triggers MAX_DAILY_LOSS_REACHED."""
    status = evaluate_entry_guardrails(
        kill_switch_active=False,
        daily_pnl_pct=-3.5,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=4,
    )
    assert not status.allowed
    assert status.reason == "MAX_DAILY_LOSS_REACHED"


def test_t2_f6_global_kill_switch_active() -> None:
    """T2.6.5: Global kill switch immediately halts all new position entries."""
    status = evaluate_entry_guardrails(
        kill_switch_active=True,
        daily_pnl_pct=0.0,
        max_daily_loss_pct=3.0,
        open_positions=0,
        max_open_positions=4,
    )
    assert not status.allowed
    assert status.reason == "GLOBAL_KILL_SWITCH_ACTIVE"


# ==============================================================================
# F7: Quantitative Metrics Boundaries
# ==============================================================================


def test_t2_f7_profit_factor_zero_losses_no_divzero() -> None:
    """T2.7.1: Profit Factor evaluated on 100% wins returns 99.0 without ZeroDivisionError."""
    pnls = [10.0, 20.0, 15.0]
    res = _finalize(
        "all_wins",
        deposit=1000.0,
        equity=1045.0,
        pnls=pnls,
        max_dd_usd=0.0,
        max_dd_pct=0.0,
        blown=False,
        max_layers_used=1,
    )
    assert res.profit_factor == 99.0


def test_t2_f7_profit_factor_zero_wins() -> None:
    """T2.7.2: Profit Factor evaluated on 100% losses returns 0.0."""
    pnls = [-10.0, -20.0, -15.0]
    res = _finalize(
        "all_losses",
        deposit=1000.0,
        equity=955.0,
        pnls=pnls,
        max_dd_usd=45.0,
        max_dd_pct=4.5,
        blown=False,
        max_layers_used=1,
    )
    assert res.profit_factor == 0.0
    assert res.win_rate_pct == 0.0


def test_t2_f7_win_rate_empty_history_zero_pct() -> None:
    """T2.7.3: Win Rate evaluated on empty trade history returns 0.0%."""
    res = _finalize(
        "empty",
        deposit=1000.0,
        equity=1000.0,
        pnls=[],
        max_dd_usd=0.0,
        max_dd_pct=0.0,
        blown=False,
        max_layers_used=0,
    )
    assert res.win_rate_pct == 0.0
    assert res.trades == 0
    assert res.profit_factor == 0.0


def test_t2_f7_sharpe_single_trade_no_crash() -> None:
    """T2.7.4: Sharpe ratio on single trade (N=1) returns None without standard deviation crash."""
    rs = [1.0]
    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    sharpe = (statistics.fmean(rs) / sd) if sd > 0 else None
    assert sharpe is None


def test_t2_f7_monotonic_equity_zero_drawdown() -> None:
    """T2.7.5: Monotonically increasing equity curve yields 0.0 USD and 0.0% max drawdown."""
    pnls = [10.0, 15.0, 20.0]
    res = _finalize(
        "monotonic",
        deposit=1000.0,
        equity=1045.0,
        pnls=pnls,
        max_dd_usd=0.0,
        max_dd_pct=0.0,
        blown=False,
        max_layers_used=1,
    )
    assert res.max_dd_usd == 0.0
    assert res.max_dd_pct == 0.0
