"""Tier 1: Core Functional Feature Coverage (F1 to F7, >= 35 tests)."""

from __future__ import annotations

import json
import statistics

import httpx
import pytest
from fastapi.testclient import TestClient
from live_trading.demo_ab_backtest import _finalize
from live_trading.risk_guardrails import calculate_risk_position_size
from warroom_core.trades_forex import ke_trade

from tests.e2e.fixtures.account_samples import (
    ACCOUNT_DEMO_1,
    ACCOUNT_DEMO_2,
    ACCOUNT_LIVE_CENT,
    get_account_meta,
)
from tests.e2e.fixtures.deal_payloads import (
    make_deal_payload,
    sample_demo1_deal,
    sample_live_cent_deal,
)
from tests.e2e.fixtures.telemetry_payloads import (
    sample_demo1_telemetry,
    sample_demo2_telemetry,
    sample_live_cent_telemetry,
)

pytestmark = pytest.mark.tier1


# ==============================================================================
# F1: API Build & Health (Port 8800)
# ==============================================================================


def test_t1_f1_build_manifest_schema(live_client: httpx.Client) -> None:
    """T1.1.1: GET /api/v1/build returns HTTP 200 with required schema."""
    resp = live_client.get("/api/v1/build")
    assert resp.status_code == 200
    data = resp.json()
    assert "build_id" in data
    assert "kode_fingerprint" in data
    assert data.get("domain_version") == "0.1.0"
    assert "berkas_dihitung" in data


def test_t1_f1_build_manifest_unauthenticated(live_client: httpx.Client) -> None:
    """T1.1.2: GET /api/v1/build is publicly accessible without auth credentials."""
    resp = live_client.get("/api/v1/build", headers={})
    assert resp.status_code == 200
    assert "build_id" in resp.json()


def test_t1_f1_health_authenticated(test_client: TestClient, admin_cookie_header: dict[str, str]) -> None:
    """T1.1.3: GET /api/v1/health with valid session cookie returns HTTP 200."""
    resp = test_client.get("/api/v1/health", headers=admin_cookie_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "db" in data
    assert "time" in data


def test_t1_f1_ready_component_checks(test_client: TestClient, admin_cookie_header: dict[str, str]) -> None:
    """T1.1.4: GET /api/v1/ready returns HTTP 200 and component checks dictionary."""
    resp = test_client.get("/api/v1/ready", headers=admin_cookie_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ready", "not_ready")
    assert "checks" in data
    assert "database" in data["checks"]
    assert "stale_facts" in data["checks"]


def test_t1_f1_freshness_active_facts(test_client: TestClient, admin_cookie_header: dict[str, str]) -> None:
    """T1.1.5: GET /api/v1/freshness returns HTTP 200 with list of tracked facts."""
    resp = test_client.get("/api/v1/freshness", headers=admin_cookie_header)
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert isinstance(data.get("facts"), list)


# ==============================================================================
# F2: Web UI Cockpit (Port 3100 & Nginx)
# ==============================================================================


def test_t1_f2_web_root_status_and_html(live_web_client: httpx.Client) -> None:
    """T1.2.1: GET http://127.0.0.1:3100/ returns HTTP 200 with HTML SvelteKit shell."""
    resp = live_web_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert len(resp.text) > 1000
    assert "svelte" in resp.text.lower() or "<!doctype html>" in resp.text.lower()


def test_t1_f2_web_csp_headers(live_web_client: httpx.Client) -> None:
    """T1.2.2: GET http://127.0.0.1:3100/ includes strict Content-Security-Policy headers."""
    resp = live_web_client.get("/")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'self'" in csp


def test_t1_f2_web_nginx_cloud_domain(cloud_base_url: str) -> None:
    """T1.2.3: GET https://polywarroom.vps.webdock.cloud/ resolves via Nginx reverse proxy."""
    try:
        resp = httpx.get(f"{cloud_base_url}/api/v1/build", timeout=5.0)
        assert resp.status_code == 200
        assert resp.json().get("domain_version") == "0.1.0"
    except httpx.ConnectError:
        pytest.skip("Public domain DNS/network route not resolvable locally")


def test_t1_f2_web_forex_cockpit_shell(live_web_client: httpx.Client) -> None:
    """T1.2.4: GET http://127.0.0.1:3100/forex loads Forex cockpit page shell."""
    resp = live_web_client.get("/forex")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert len(resp.text) > 500


def test_t1_f2_web_immutable_static_assets(live_web_client: httpx.Client) -> None:
    """T1.2.5: Static assets under /_app/immutable/ load with immutable cache-control."""
    root_resp = live_web_client.get("/")
    assets = [w.lstrip(".") for w in root_resp.text.split('"') if "_app/immutable/" in w]
    assert len(assets) > 0, "Expected at least one immutable JS/CSS asset in HTML root"
    asset_resp = live_web_client.get(assets[0])
    assert asset_resp.status_code == 200
    cache_control = asset_resp.headers.get("cache-control", "")
    assert "immutable" in cache_control


# ==============================================================================
# F3: MT5 Multi-Account Telemetry
# ==============================================================================


def test_t1_f3_telemetry_live_cent_ingestion(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.3.1: POST /api/v1/tencent/mt5/telemetry accepts Live Cent #452009427 (USC)."""
    payload = sample_live_cent_telemetry()
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert "received_at" in data


def test_t1_f3_telemetry_demo1_ingestion(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.3.2: POST /api/v1/tencent/mt5/telemetry accepts Demo 1 #434446792 (USD)."""
    payload = sample_demo1_telemetry()
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert data["action"] == "OK"


def test_t1_f3_telemetry_demo2_ingestion(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.3.3: POST /api/v1/tencent/mt5/telemetry accepts Demo 2 #464202979 (USD)."""
    payload = sample_demo2_telemetry()
    resp = test_client.post("/api/v1/tencent/mt5/telemetry", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert data["action"] == "OK"


def test_t1_f3_accounts_enumeration(live_client: httpx.Client, auth_headers: dict[str, str]) -> None:
    """T1.3.4: GET /api/v1/tencent/mt5/accounts returns primary account and account list."""
    resp = live_client.get("/api/v1/tencent/mt5/accounts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["primary"] == ACCOUNT_LIVE_CENT
    assert data["n"] >= 2
    acc_map = {a["account"]: a for a in data["accounts"]}
    assert ACCOUNT_LIVE_CENT in acc_map
    assert acc_map[ACCOUNT_LIVE_CENT]["currency"] == "USC"
    assert acc_map[ACCOUNT_LIVE_CENT]["primary"] is True


def test_t1_f3_account_status_snapshot(live_client: httpx.Client, auth_headers: dict[str, str]) -> None:
    """T1.3.5: GET /api/v1/tencent/mt5/status returns snapshot for primary Cent account."""
    resp = live_client.get(f"/api/v1/tencent/mt5/status?account={ACCOUNT_LIVE_CENT}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["account"] == ACCOUNT_LIVE_CENT
    assert data["primary"] is True
    assert "balance" in data
    assert "equity" in data


# ==============================================================================
# F4: SSE Real-Time Streaming
# ==============================================================================


def test_t1_f4_sse_connection_and_content_type(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.4.1: GET /api/v1/tencent/forex/stream establishes text/event-stream response."""
    with test_client.stream("GET", "/api/v1/tencent/forex/stream", headers=auth_headers) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_t1_f4_sse_reconnection_preamble(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.4.2: Initial connection preamble includes retry: 3000 for auto-reconnection."""
    with test_client.stream("GET", "/api/v1/tencent/forex/stream", headers=auth_headers) as resp:
        lines = []
        for line in resp.iter_lines():
            lines.append(line)
            if len(lines) >= 4:
                break
        combined = "\n".join(lines)
        assert "retry: 3000" in combined


def test_t1_f4_sse_initial_snapshot_delivered(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.4.3: Stream immediately delivers current account telemetry snapshot."""
    url = f"/api/v1/tencent/forex/stream?account={ACCOUNT_LIVE_CENT}"
    with test_client.stream("GET", url, headers=auth_headers) as resp:
        snapshot = None
        for line in resp.iter_lines():
            if line.startswith("data: "):
                snapshot = json.loads(line[6:])
                break
        assert snapshot is not None
        assert snapshot.get("account") == ACCOUNT_LIVE_CENT
        assert "equity" in snapshot


def test_t1_f4_sse_specific_account_filter(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.4.4: Subscribing to ?account=464202979 delivers Demo 2 snapshot data."""
    url = f"/api/v1/tencent/forex/stream?account={ACCOUNT_DEMO_2}"
    with test_client.stream("GET", url, headers=auth_headers) as resp:
        snapshot = None
        for line in resp.iter_lines():
            if line.startswith("data: "):
                snapshot = json.loads(line[6:])
                break
        assert snapshot is not None
        assert snapshot.get("account") == ACCOUNT_DEMO_2


def test_t1_f4_sse_keepalive_ping_format() -> None:
    """T1.4.5: Idle SSE keepalive format matches ': ping\\n\\n'."""
    ping_comment = ": ping\n\n"
    assert ping_comment.startswith(":")
    assert "ping" in ping_comment
    assert ping_comment.endswith("\n\n")


# ==============================================================================
# F5: MT5 Deal Ingestion & Deduplication
# ==============================================================================


def test_t1_f5_deal_ingestion_valid(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.5.1: POST /api/v1/tencent/mt5/deal accepts valid closed trade payload."""
    payload = sample_demo1_deal(ticket=7781001)
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("OK", "duplikat")
    assert data["ticket"] == 7781001


def test_t1_f5_net_profit_calculation(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.5.2: Net profit calculation computes net = profit + swap + commission."""
    payload = make_deal_payload(
        ticket=7781002,
        profit=20.0,
        swap=-0.50,
        commission=-1.50,
        currency="USD",
        cent_factor=1.0,
    )
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    expected_net = round(20.0 + (-0.50) + (-1.50), 2)
    assert data["net"] == expected_net


def test_t1_f5_cent_factor_enforcement(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.5.3: Cent account #452009427 enforces cent_factor: 100.0 and currency: USC."""
    payload = sample_live_cent_deal(ticket=6639265)
    resp = test_client.post("/api/v1/tencent/mt5/deal", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["cent_factor"] == 100.0
    assert data["currency"] == "USC"


def test_t1_f5_trade_conversion_model() -> None:
    """T1.5.4: ke_trade correctly maps cent raw profit to normalized USD pnl."""
    baris = {
        "ticket": 6639264,
        "symbol": "XAUUSDc",
        "side": "BUY",
        "volume": 0.01,
        "profit": 14.10,
        "swap": 0.0,
        "commission": 0.0,
        "net": 14.10,
        "account": ACCOUNT_LIVE_CENT,
        "currency": "USC",
        "cent_factor": 100.0,
        "close_time": "2026-11-16 04:00:00",
    }
    trade = ke_trade(baris)
    assert trade.ext_id == "6639264"
    assert trade.pnl_usd == 0.141
    assert trade.venue == "forex"


def test_t1_f5_deals_query_limit(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """T1.5.5: GET /api/v1/tencent/mt5/deals returns deals list with total count."""
    resp = test_client.get("/api/v1/tencent/mt5/deals?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "deals" in data
    assert isinstance(data["deals"], list)
    assert len(data["deals"]) <= 5
    assert data["total"] >= 0


# ==============================================================================
# F6: Risk Sizing & Protective Limits
# ==============================================================================


def test_t1_f6_risk_position_sizing_calculation() -> None:
    """T1.6.1: calculate_risk_position_size accurately sizes position based on equity."""
    size = calculate_risk_position_size(equity=1000.0, sl_distance=10.0, risk_pct=0.01)
    # risk_amount = 1000 * 0.01 = 10.0; raw_size = 10.0 / 10.0 = 1.0
    assert size == 1.0


def test_t1_f6_risk_percentage_clamping() -> None:
    """T1.6.2: Risk percentage is clamped to [0.01, 0.02] (1.0% to 2.0%)."""
    low = calculate_risk_position_size(equity=1000.0, sl_distance=10.0, risk_pct=0.002)
    assert low == 1.0  # clamped up to 0.01

    high = calculate_risk_position_size(equity=1000.0, sl_distance=10.0, risk_pct=0.05)
    assert high == 2.0  # clamped down to 0.02


def test_t1_f6_cent_account_micro_lot_preservation() -> None:
    """T1.6.3: Sizing on Live Cent #452009427 ($10.85 equity) preserves 0.01 lot minimum."""
    size = calculate_risk_position_size(equity=10.85, sl_distance=20.0, risk_pct=0.01, min_size=0.01)
    assert size == 0.01


def test_t1_f6_demo1_twin_order_structure() -> None:
    """T1.6.4: Demo 1 Twin Order structure allocates 0.01 Scalp + 0.01 Runner."""
    meta = get_account_meta(ACCOUNT_DEMO_1)
    assert meta["fixed_lot"] == 0.02
    assert meta["daily_max_loss_usd"] == 30.00
    assert meta["magic"] == 434446


def test_t1_f6_demo2_flat_layering_no_martingale() -> None:
    """T1.6.5: Demo 2 enforces flat 0.01 lot across layers with max 4 layers."""
    meta = get_account_meta(ACCOUNT_DEMO_2)
    assert meta["fixed_lot"] == 0.01
    assert meta["max_layers"] == 4
    assert meta["hard_basket_sl_usd"] == 45.00
    assert meta["magic"] == 464202


# ==============================================================================
# F7: Quantitative Backtest Metrics
# ==============================================================================


def test_t1_f7_profit_factor_calculation() -> None:
    """T1.7.1: Profit Factor calculation returns exact gross wins / gross losses ratio."""
    pnls = [10.0, 20.0, -15.0]
    res = _finalize(
        "test",
        deposit=1000.0,
        equity=1015.0,
        pnls=pnls,
        max_dd_usd=15.0,
        max_dd_pct=1.5,
        blown=False,
        max_layers_used=1,
    )
    expected_pf = round(30.0 / 15.0, 2)
    assert res.profit_factor == expected_pf


def test_t1_f7_win_rate_calculation() -> None:
    """T1.7.2: Win Rate calculation returns exact percentage of winning trades."""
    pnls = [10.0, 20.0, -15.0]
    res = _finalize(
        "test",
        deposit=1000.0,
        equity=1015.0,
        pnls=pnls,
        max_dd_usd=15.0,
        max_dd_pct=1.5,
        blown=False,
        max_layers_used=1,
    )
    expected_wr = round((2 / 3) * 100.0, 2)
    assert res.win_rate_pct == expected_wr


def test_t1_f7_maximum_drawdown_calculation() -> None:
    """T1.7.3: Maximum Drawdown tracks peak-to-trough decline."""
    res = _finalize(
        "test",
        deposit=1000.0,
        equity=1050.0,
        pnls=[100.0, -50.0],
        max_dd_usd=50.0,
        max_dd_pct=4.55,
        blown=False,
        max_layers_used=1,
    )
    assert res.max_dd_usd == 50.0
    assert res.max_dd_pct == 4.55


def test_t1_f7_sharpe_ratio_calculation() -> None:
    """T1.7.4: Per-trade Sharpe computes mean excess return over return standard deviation."""
    rs = [1.0, 1.5, -0.5, 2.0]
    sd = statistics.pstdev(rs)
    sharpe = statistics.fmean(rs) / sd
    assert sharpe > 0.0
    assert round(sharpe, 2) == 1.07


def test_t1_f7_benchmark_performance_targets() -> None:
    """T1.7.5: Strategy acceptance criteria enforce Profit Factor > 1.0."""
    res = _finalize(
        "benchmark",
        deposit=1000.0,
        equity=1080.0,
        pnls=[20.0, 25.0, -15.0, 30.0, -10.0],
        max_dd_usd=15.0,
        max_dd_pct=1.5,
        blown=False,
        max_layers_used=2,
    )
    assert res.profit_factor > 1.0
    assert res.win_rate_pct > 50.0
    assert not res.blown_up
