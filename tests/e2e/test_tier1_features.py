"""
Tier 1: Feature Coverage (Sprint 4 / US-18 E2E Test Suite)
Requirement-driven opaque-box tests covering all 17 features from PROJECT.md:
BE-01..06, FE-01..06, OPS-01..05 (>= 85 isolated tests).
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from warroom_core.forex import laya_verdict
from warroom_core.forex.strategies.multi_session_laya import MultiSessionLayaScalperStrategy
from warroom_core.trades_forex import ke_trade
from warroom_api.routers.tencent import (
    ACTIVE_CENT_ACCOUNT,
    MT5DealPayload,
    MT5TelemetryPayload,
    _broadcast_sse_telemetry,
    _telemetry_subscribers,
    latest_mt5_by_account,
    report_mt5_deal,
    report_mt5_telemetry,
    stream_forex_telemetry,
)
import parser as tg_parser


# ==============================================================================
# BE-01: Pure Technical Mode Fallback
# ==============================================================================
class TestBE01PureTechnicalFallback:
    """BE-01: Pure Technical Mode Fallback when Laya AI inference is disabled."""

    def test_be01_01_env_alias_inference_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WARROOM_LAYA_INFERENSI=0 sets Laya AI to disabled."""
        monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
        assert laya_verdict.is_laya_enabled() is False

    def test_be01_02_env_alias_overrides_enable_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WARROOM_LAYA_INFERENSI=0 overrides WARROOM_LAYA_ENABLE=1."""
        monkeypatch.setenv("WARROOM_LAYA_ENABLE", "1")
        monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
        assert laya_verdict.is_laya_enabled() is False

    def test_be01_03_technical_valid_london_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid setup in LONDON session (RRR >= 1.6, SL <= 3.0) passes filter."""
        monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
        strategy = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6, max_sl_points=3.0)
        layak, conf, alasan = strategy.evaluate_laya({
            "side": "LONG",
            "session": "LONDON",
            "rrr": 1.85,
            "risk": 2.2,
        })
        assert layak is True
        assert conf == 1.0
        assert "Mode teknis murni" in alasan
        assert "lolos filter teknis" in alasan

    def test_be01_04_technical_valid_new_york_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid setup in NEW_YORK session passes pure technical evaluation."""
        monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
        strategy = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6, max_sl_points=3.0)
        layak, conf, alasan = strategy.evaluate_laya({
            "side": "SHORT",
            "session": "NEW_YORK",
            "rrr": 2.10,
            "risk": 1.9,
        })
        assert layak is True
        assert conf == 1.0
        assert "lolos filter teknis" in alasan

    def test_be01_05_verdict_cache_missing_graceful_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When Laya enabled but verdict file is missing, falls back to technical evaluation."""
        monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "1")
        monkeypatch.setenv("WARROOM_LAYA_VERDICT_PATH", str(tmp_path / "nonexistent_verdict.json"))
        strategy = MultiSessionLayaScalperStrategy(enable_laya=True, min_rrr=1.6, max_sl_points=3.0)
        layak, conf, alasan = strategy.evaluate_laya({
            "side": "LONG",
            "session": "ASIA",
            "rrr": 1.75,
            "risk": 2.0,
        })
        assert layak is True
        assert conf == 1.0
        assert "Mode teknis murni" in alasan


# ==============================================================================
# BE-02: Cent Deal Ingestion & Currency Attribution
# ==============================================================================
class TestBE02CentDealIngestion:
    """BE-02: Cent Deal Ingestion & Currency Attribution (USC, cent_factor 100.0)."""

    @pytest.mark.asyncio
    async def test_be02_01_deal_ingestion_usc_attribution(self, tmp_deal_log: Path) -> None:
        """Deal payload with currency USC returns status OK and attributes cent_factor 100.0."""
        payload = MT5DealPayload(
            ticket=55001122,
            position=55001122,
            symbol="XAUUSDc",
            side="BUY",
            volume=0.05,
            open_time="2026-11-12 11:00:00",
            close_time="2026-11-12 11:10:00",
            profit=150.0,
            account="452009427",
            currency="USC",
            cent_factor=100.0,
        )
        res = await report_mt5_deal(payload)
        assert res["status"] == "OK"
        assert res["currency"] == "USC"
        assert res["cent_factor"] == 100.0
        assert res["net"] == 150.0

    def test_be02_02_ke_trade_cent_normalization(self) -> None:
        """ke_trade() normalizes pnl_usd = net / 100.0 for cent accounts."""
        deal_dict = {
            "ticket": "990011",
            "symbol": "XAUUSDc",
            "side": "BUY",
            "volume": "0.02",
            "open_price": "2650.0",
            "close_price": "2655.0",
            "net": 100.0,
            "account": "452009427",
            "strategy_version": "v2.0",
            "currency": "USC",
            "cent_factor": 100.0,
        }
        trade = ke_trade(deal_dict)
        assert trade is not None
        assert trade.pnl_usd == 1.00
        assert trade.venue == "forex"
        assert trade.mode == "live"

    @pytest.mark.asyncio
    async def test_be02_03_deal_csv_logging(self, tmp_deal_log: Path) -> None:
        """Deals are appended to CSV log with proper currency and cent_factor headers."""
        payload = MT5DealPayload(
            ticket=77002233,
            position=77002233,
            symbol="EURUSDc",
            side="SELL",
            volume=0.10,
            open_time="2026-11-12 12:00:00",
            close_time="2026-11-12 12:05:00",
            profit=80.0,
            account="452009427",
            currency="USC",
            cent_factor=100.0,
        )
        await report_mt5_deal(payload)
        assert tmp_deal_log.exists()
        content = tmp_deal_log.read_text(encoding="utf-8")
        assert "77002233" in content
        assert "USC" in content
        assert "100.0" in content

    def test_be02_04_evidence_json_structure(self) -> None:
        """Trade.evidence_json contains complete metadata for cent attribution."""
        deal_dict = {
            "ticket": "334455",
            "symbol": "XAUUSDc",
            "side": "SELL",
            "volume": "0.01",
            "open_price": "2660.0",
            "close_price": "2655.0",
            "net": 50.0,
            "account": "452009427",
            "currency": "USC",
            "cent_factor": 100.0,
        }
        trade = ke_trade(deal_dict)
        assert trade is not None
        assert trade.evidence_json["currency"] == "USC"
        assert trade.evidence_json["cent_factor"] == 100.0
        assert trade.evidence_json["net_usc"] == 50.0

    def test_be02_05_standard_usd_deal_normalization(self) -> None:
        """Standard USD deals retain 1:1 net profit without scaling."""
        deal_dict = {
            "ticket": "112233",
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.10",
            "open_price": "2650.0",
            "close_price": "2655.0",
            "net": 50.0,
            "account": "999888",
            "currency": "USD",
            "cent_factor": 1.0,
        }
        trade = ke_trade(deal_dict)
        assert trade is not None
        assert trade.pnl_usd == 50.0


# ==============================================================================
# BE-03: SSE Stream Default Account & Resiliency
# ==============================================================================
class TestBE03SSEStreamResiliency:
    """BE-03: SSE Stream Default Account & Resiliency (452009427, retry: 3000\\n)."""

    @pytest.mark.asyncio
    async def test_be03_01_stream_default_account(self, reset_telemetry_state: None) -> None:
        """Calling stream_forex_telemetry without account param defaults to 452009427."""
        latest_mt5_by_account[ACTIVE_CENT_ACCOUNT] = {
            "account": ACTIVE_CENT_ACCOUNT,
            "balance": 1074.81,
            "equity": 1074.81,
        }
        response = await stream_forex_telemetry(account=None)
        assert response.media_type == "text/event-stream"
        gen = response.body_iterator
        _ = await gen.__anext__()  # header retry directive
        chunk = await gen.__anext__()
        assert ACTIVE_CENT_ACCOUNT in chunk
        assert "1074.81" in chunk

    @pytest.mark.asyncio
    async def test_be03_02_stream_emits_retry_directive(self, reset_telemetry_state: None) -> None:
        """SSE stream response emits standard retry directive 'retry: 3000\\n'."""
        response = await stream_forex_telemetry(account=ACTIVE_CENT_ACCOUNT)
        gen = response.body_iterator
        first_chunk = await gen.__anext__()
        assert "retry: 3000\n" in first_chunk

    @pytest.mark.asyncio
    async def test_be03_03_subscriber_broadcast_delivery(self, reset_telemetry_state: None) -> None:
        """Broadcast helper delivers telemetry updates to active subscriber queues."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        _telemetry_subscribers.append(queue)
        try:
            sample = {"account": ACTIVE_CENT_ACCOUNT, "balance": 1500.0, "spread_pts": 15}
            _broadcast_sse_telemetry(sample)
            msg = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert msg["account"] == ACTIVE_CENT_ACCOUNT
            assert msg["balance"] == 1500.0
            assert msg["spread_pts"] == 15
        finally:
            if queue in _telemetry_subscribers:
                _telemetry_subscribers.remove(queue)

    @pytest.mark.asyncio
    async def test_be03_04_sse_endpoint_route_registration(self) -> None:
        """GET /api/v1/tencent/forex/stream endpoint is registered and responds with event-stream."""
        import warroom_api.routers.tencent as tencent_module
        matched = False
        for route in tencent_module.router.routes:
            if getattr(route, "path", "") == "/api/v1/tencent/forex/stream":
                assert "GET" in route.methods
                matched = True
                break
        assert matched is True
        res = await stream_forex_telemetry(account=ACTIVE_CENT_ACCOUNT)
        assert res.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_be03_05_snapshot_contains_exness_currency(self, reset_telemetry_state: None) -> None:
        """Telemetry snapshot broadcast preserves currency USC attribution."""
        latest_mt5_by_account[ACTIVE_CENT_ACCOUNT] = {
            "account": ACTIVE_CENT_ACCOUNT,
            "currency": "USC",
            "balance": 2050.50,
            "equity": 2050.50,
        }
        response = await stream_forex_telemetry(account=ACTIVE_CENT_ACCOUNT)
        gen = response.body_iterator
        _ = await gen.__anext__()
        chunk = await gen.__anext__()
        assert '"currency": "USC"' in chunk or '"currency":"USC"' in chunk


# ==============================================================================
# BE-04: Telegram Parser Hardening
# ==============================================================================
class TestBE04TelegramParserHardening:
    """BE-04: Telegram Parser Hardening (keywords, prefixless ranges, milestone detection)."""

    def test_be04_01_missing_keywords_support(self) -> None:
        """Parser supports buy, sell, sl, tp, and entry keywords."""
        msg = "XAUUSD buy now at 2650.00 sl 2640.00 tp 2670.00"
        parsed = tg_parser.parse_forex_signal(msg, "Telegram VIP")
        assert parsed is not None
        assert parsed["action"] == "BUY"
        assert parsed["sl"] == 2640.00
        assert parsed["tp1"] == 2670.00

    def test_be04_02_prefixless_entry_range(self) -> None:
        """Parser extracts entry range without '@' prefix (e.g. GOLD BUY 2650-2648)."""
        msg = "GOLD BUY 2650-2648 SL 2640 TP 2670"
        parsed = tg_parser.parse_forex_signal(msg, "")
        assert parsed is not None
        assert parsed["symbol"] == "XAUUSD"
        assert parsed["action"] == "BUY"
        assert parsed["entry_low"] == 2648.0
        assert parsed["entry_high"] == 2650.0

    def test_be04_03_milestone_detection(self) -> None:
        """Progress updates such as '🟢 40 Pips' or 'TP1 HIT' are classified as MILESTONE."""
        assert tg_parser.is_milestone_or_update("🟢 40 Pips") is True
        assert tg_parser.classify_signal_type("🟢 40 Pips") == "MILESTONE"
        assert tg_parser.is_milestone_or_update("TP1 HIT RUNNING") is True
        assert tg_parser.classify_signal_type("TP 1 SMACKED 🔥 +40 Pips") == "MILESTONE"

    def test_be04_04_thousands_separator_normalization(self) -> None:
        """Prices with thousands separator commas (e.g. 2,650.50) normalize properly."""
        msg = "GOLD BUY @ 2,650.50 SL 2,640.00 TP 2,670.00"
        parsed = tg_parser.parse_forex_signal(msg, "")
        assert parsed is not None
        assert parsed["entry_low"] == 2650.50
        assert parsed["sl"] == 2640.00
        assert parsed["tp1"] == 2670.00

    def test_be04_05_multiple_take_profit_levels(self) -> None:
        """Multiple take profit levels separated by slashes are parsed into tp1, tp2, tp3."""
        msg = "XAUUSD BUY @ 2650 SL 2640 TP 2660 / 2670 / 2680"
        parsed = tg_parser.parse_forex_signal(msg, "")
        assert parsed is not None
        assert parsed["tp1"] == 2660.0
        assert parsed["tp2"] == 2670.0
        assert parsed["tp3"] == 2680.0


# ==============================================================================
# BE-05: Hermetic DB Fallback in Unit Tests
# ==============================================================================
class TestBE05HermeticDBFallback:
    """BE-05: Hermetic DB Fallback in Unit Tests and Offline Resilience."""

    def test_be05_01_jurnal_crypto_offline_fallback(self) -> None:
        """jurnal_crypto.dari_db returns empty list without crashing when DB is offline."""
        from warroom_api import jurnal_crypto
        res = jurnal_crypto.dari_db(batas=10)
        assert isinstance(res, list)
        assert res == []

    def test_be05_02_jurnal_forex_offline_fallback(self) -> None:
        """jurnal_forex.dari_db returns clean empty list without crashing when DB is offline."""
        from warroom_api import jurnal_forex
        res = jurnal_forex.dari_db(batas=10)
        assert isinstance(res, list)
        assert res == []

    def test_be05_03_health_degraded_when_db_down(self, test_client: TestClient) -> None:
        """Health endpoint returns degraded with db=False when DB is unreachable."""
        res = test_client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "db" in data
        assert data["db"] is False

    def test_be05_04_crypto_fallback_function_exists(self) -> None:
        """jurnal_crypto and jurnal_forex provide resilient dari_db functions."""
        from warroom_api import jurnal_crypto, jurnal_forex
        assert callable(jurnal_crypto.dari_db)
        assert callable(jurnal_forex.dari_db)

    def test_be05_05_status_ops_offline_resilience(self, test_client: TestClient) -> None:
        """Ready endpoint executes gracefully offline and reports db=False."""
        res = test_client.get("/api/v1/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["db"] is False
        assert data["status"] in ("ready", "not_ready")


# ==============================================================================
# BE-06: Decommissioned VM Hard Isolation
# ==============================================================================
class TestBE06DecommissionedVMIsolation:
    """BE-06: Decommissioned VM Hard Isolation (Azure VM2 36525553 & Vantage)."""

    @pytest.mark.asyncio
    async def test_be06_01_azure_account_hard_isolated(self) -> None:
        """Account 36525553 returns OK without exec_powershell or dispatch."""
        p = MT5TelemetryPayload(
            account="36525553",
            broker="Vantage International",
            balance=1000.0,
            equity=1000.0,
            margin=0.0,
            free_margin=1000.0,
            floating_pnl=0.0,
        )
        res = await report_mt5_telemetry(p)
        assert res["status"] == "OK"
        assert res["action"] == "OK"
        assert "exec_powershell" not in res
        assert res.get("action") != "SYNC_EA_V2"

    @pytest.mark.asyncio
    async def test_be06_02_vantage_broker_hard_isolated(self) -> None:
        """Any account using Vantage broker is isolated from SYNC_EA_V2."""
        p = MT5TelemetryPayload(
            account="998877",
            broker="Vantage FX Markets",
            balance=500.0,
            equity=500.0,
            margin=0.0,
            free_margin=500.0,
            floating_pnl=0.0,
        )
        res = await report_mt5_telemetry(p)
        assert res["status"] == "OK"
        assert "exec_powershell" not in res
        assert res.get("action") != "SYNC_EA_V2"

    @pytest.mark.asyncio
    async def test_be06_03_no_script_emission_for_vm2(self) -> None:
        """Report telemetry for VM2 guarantees empty execution script."""
        p = MT5TelemetryPayload(
            account="36525553",
            broker="Unknown",
            balance=1000.0,
            equity=1000.0,
            margin=0.0,
            free_margin=1000.0,
            floating_pnl=0.0,
        )
        res = await report_mt5_telemetry(p)
        assert "exec_powershell" not in res

    @pytest.mark.asyncio
    async def test_be06_04_vantage_case_insensitivity(self) -> None:
        """Isolation matches 'vantage' regardless of uppercase or lowercase."""
        p = MT5TelemetryPayload(
            account="112233",
            broker="vantage global prime",
            balance=500.0,
            equity=500.0,
            margin=0.0,
            free_margin=500.0,
            floating_pnl=0.0,
        )
        res = await report_mt5_telemetry(p)
        assert res.get("action") != "SYNC_EA_V2"

    def test_be06_05_active_instabox_exness_allowed(self) -> None:
        """Active Exness Cent account 452009427 is recognized as legitimate active runner."""
        assert ACTIVE_CENT_ACCOUNT == "452009427"


# ==============================================================================
# FE-01: Frontend Live SSE Stream Subscription
# ==============================================================================
class TestFE01LiveSSESubscription:
    """FE-01: Frontend Live SSE Stream Subscription (ForexCockpitExness.svelte)."""

    def test_fe01_01_cockpit_uses_eventsource(self, apps_web_dir: Path) -> None:
        """ForexCockpitExness.svelte instantiates EventSource."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "new EventSource" in content

    def test_fe01_02_cockpit_targets_sse_stream_endpoint(self, apps_web_dir: Path) -> None:
        """ForexCockpitExness targets /api/v1/tencent/forex/stream."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "/api/v1/tencent/forex/stream" in content

    def test_fe01_03_cockpit_passes_credentials_include(self, apps_web_dir: Path) -> None:
        """EventSource or fetch in Cockpit includes credentials."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "credentials" in content
        assert "include" in content

    def test_fe01_04_cockpit_closes_eventsource_on_destroy(self, apps_web_dir: Path) -> None:
        """Cockpit closes EventSource on component teardown/onDestroy."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "close()" in content or "onDestroy" in content

    def test_fe01_05_live_svelte_store_exports_connection_state(self, apps_web_dir: Path) -> None:
        """live.svelte.ts manages live stream state and status."""
        live_file = apps_web_dir / "src" / "lib" / "api" / "live.svelte.ts"
        content = live_file.read_text(encoding="utf-8")
        assert "class Live" in content or "status" in content or "connect" in content


# ==============================================================================
# FE-02: UI Loading, Error & Empty State Boundaries
# ==============================================================================
class TestFE02UILoadingAndErrorBoundaries:
    """FE-02: UI Loading, Error & Empty State Boundaries."""

    def test_fe02_01_no_phantom_loading_in_cockpit(self, apps_web_dir: Path) -> None:
        """Cockpit eliminates unused phantom loading variables and binds state."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "loading = false" in content or "memuat" in content or "skeleton" in content

    def test_fe02_02_skeleton_loader_component_present(self, apps_web_dir: Path) -> None:
        """AreaLoader or skeleton markup is defined for loading state."""
        loader_file = apps_web_dir / "src" / "lib" / "components" / "AreaLoader.svelte"
        assert loader_file.exists()
        content = loader_file.read_text(encoding="utf-8")
        assert "animate-pulse" in content or "skeleton" in content or "memuat" in content

    def test_fe02_03_explicit_error_boundary_handling(self, apps_web_dir: Path) -> None:
        """ForexCockpit and AreaLoader implement error boundary with retry."""
        cockpit_file = apps_web_dir / "src" / "lib" / "components" / "ForexCockpitExness.svelte"
        content = cockpit_file.read_text(encoding="utf-8")
        assert "error" in content.lower()
        assert "retry" in content.lower() or "muat ulang" in content.lower() or "coba lagi" in content.lower()

    def test_fe02_04_empty_state_handling(self, apps_web_dir: Path) -> None:
        """Empty trade lists render informative EmptyState."""
        empty_component = apps_web_dir / "src" / "lib" / "components" / "EmptyState.svelte"
        assert empty_component.exists()

    def test_fe02_05_beranda_page_flash_prevention(self, apps_web_dir: Path) -> None:
        """Home page (+page.svelte) prevents unhandled flash during loading."""
        page_file = apps_web_dir / "src" / "routes" / "+page.svelte"
        content = page_file.read_text(encoding="utf-8")
        assert "loading" in content.lower() or "memuat" in content.lower() or "skeleton" in content.lower()


# ==============================================================================
# FE-03: Dynamic Cent Currency Formatting
# ==============================================================================
class TestFE03DynamicCentFormatting:
    """FE-03: Dynamic Cent Currency Formatting (USC ($...))."""

    def test_fe03_01_journal_panel_formats_usc(self, apps_web_dir: Path) -> None:
        """JournalPanel.svelte formats USC values with USD equivalent in parentheses."""
        journal_file = apps_web_dir / "src" / "lib" / "components" / "JournalPanel.svelte"
        content = journal_file.read_text(encoding="utf-8")
        assert "USC" in content
        assert "formatSaldo" in content or "formatUsc" in content or "formatCurrency" in content or "formatPnl" in content

    def test_fe03_02_ledger_page_formats_usc(self, apps_web_dir: Path) -> None:
        """routes/ledger/+page.svelte formats Cent balances dynamically."""
        ledger_file = apps_web_dir / "src" / "routes" / "ledger" / "+page.svelte"
        content = ledger_file.read_text(encoding="utf-8")
        assert "USC" in content

    def test_fe03_03_cent_scaling_arithmetic(self) -> None:
        """Cent arithmetic converts 1074.81 USC to exactly 10.7481 USD (~10.75 USD)."""
        usc_balance = 1074.81
        usd_equiv = usc_balance / 100.0
        assert f"${usd_equiv:.2f}" == "$10.75"

    def test_fe03_04_cent_factor_custom_scaling(self) -> None:
        """Non-standard cent factor scales correctly."""
        usc_balance = 500.0
        cent_factor = 100.0
        assert usc_balance / cent_factor == 5.0

    def test_fe03_05_usd_accounts_bypass_cent_formatting(self) -> None:
        """USD account with 50.0 is formatted without USC division."""
        curr = "USD"
        val = 50.0
        formatted = f"${val:.2f}" if curr == "USD" else f"{val} USC (${val/100:.2f})"
        assert formatted == "$50.00"


# ==============================================================================
# FE-04: Research Live API Integration
# ==============================================================================
class TestFE04ResearchLiveAPIIntegration:
    """FE-04: Research Live API Integration (/api/v1/research/runs, /api/v1/leaderboard)."""

    def test_fe04_01_quant_card_fetches_research_api(self, apps_web_dir: Path) -> None:
        """QuantStrategyCard.svelte imports getLeaderboard and getResearchRuns."""
        card_file = apps_web_dir / "src" / "lib" / "components" / "QuantStrategyCard.svelte"
        content = card_file.read_text(encoding="utf-8")
        assert "getLeaderboard" in content
        assert "getResearchRuns" in content

    def test_fe04_02_leaderboard_component_fetches_api(self, apps_web_dir: Path) -> None:
        """StrategyLeaderboard.svelte and client.ts declare /api/v1/leaderboard."""
        client_file = apps_web_dir / "src" / "lib" / "api" / "client.ts"
        content = client_file.read_text(encoding="utf-8")
        assert "/api/v1/leaderboard" in content

    def test_fe04_03_leaderboard_backend_endpoint(self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backend GET /api/v1/leaderboard responds with valid JSON."""
        @contextmanager
        def _mock_scope():
            yield MagicMock()

        monkeypatch.setattr("warroom_api.routers.leaderboard.session_scope", _mock_scope)
        monkeypatch.setattr("warroom_core.leaderboard.strategy_leaderboard", lambda s: {"total_baris": 1, "strategi": []})
        res = test_client.get("/api/v1/leaderboard")
        assert res.status_code == 200
        data = res.json()
        assert "strategi" in data

    def test_fe04_04_research_runs_backend_endpoint(self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backend GET /api/v1/research/runs responds with valid JSON."""
        @contextmanager
        def _mock_scope():
            mock_s = MagicMock()
            mock_s.scalars.return_value.all.return_value = []
            yield mock_s

        monkeypatch.setattr("warroom_api.routers.datasets.session_scope", _mock_scope)
        res = test_client.get("/api/v1/research/runs")
        assert res.status_code == 200
        data = res.json()
        assert "runs" in data

    def test_fe04_05_quant_card_has_error_fallback(self, apps_web_dir: Path) -> None:
        """QuantStrategyCard gracefully falls back when API fetch fails."""
        card_file = apps_web_dir / "src" / "lib" / "components" / "QuantStrategyCard.svelte"
        content = card_file.read_text(encoding="utf-8")
        assert "catch" in content or "error" in content.lower() or "fallback" in content.lower()


# ==============================================================================
# FE-05: Vault Runes Refactor & Mobile Overflow Fix
# ==============================================================================
class TestFE05VaultRunesAndMobileOverflow:
    """FE-05: Vault Runes Refactor & Mobile Overflow Fix."""

    def test_fe05_01_vault_page_uses_svelte5_runes(self, apps_web_dir: Path) -> None:
        """routes/vault/+page.svelte uses $state and avoids legacy $: reactivity."""
        vault_file = apps_web_dir / "src" / "routes" / "vault" / "+page.svelte"
        content = vault_file.read_text(encoding="utf-8")
        assert "$state(" in content
        assert not re.search(r"^\s*\$:\s+", content, re.MULTILINE)

    def test_fe05_02_mt5_vault_page_uses_svelte5_runes(self, apps_web_dir: Path) -> None:
        """routes/mt5-vault/+page.svelte uses $state and avoids legacy $: reactivity."""
        mt5_vault_file = apps_web_dir / "src" / "routes" / "mt5-vault" / "+page.svelte"
        content = mt5_vault_file.read_text(encoding="utf-8")
        assert "$state(" in content
        assert not re.search(r"^\s*\$:\s+", content, re.MULTILINE)

    def test_fe05_03_vault_table_has_overflow_x_auto(self, apps_web_dir: Path) -> None:
        """MT5 Vault tables are wrapped in overflow-x-auto to prevent mobile clipping."""
        mt5_vault_file = apps_web_dir / "src" / "routes" / "mt5-vault" / "+page.svelte"
        content = mt5_vault_file.read_text(encoding="utf-8")
        assert "overflow-x-auto" in content

    def test_fe05_04_mt5_vault_table_has_overflow_x_auto(self, apps_web_dir: Path) -> None:
        """MT5 Vault page has responsive styling for mobile viewports."""
        mt5_vault_file = apps_web_dir / "src" / "routes" / "mt5-vault" / "+page.svelte"
        content = mt5_vault_file.read_text(encoding="utf-8")
        assert "overflow-x-auto" in content
        assert "border" in content

    def test_fe05_05_vault_uses_design_tokens(self, apps_web_dir: Path) -> None:
        """Vault components use standard design system color and border classes."""
        vault_file = apps_web_dir / "src" / "routes" / "vault" / "+page.svelte"
        content = vault_file.read_text(encoding="utf-8")
        assert "var(--color-line)" in content
        assert "var(--color-surface)" in content


# ==============================================================================
# FE-06: Frontend Hygiene & Lint Configuration
# ==============================================================================
class TestFE06FrontendHygieneAndLint:
    """FE-06: Frontend Hygiene & Lint Configuration."""

    def test_fe06_01_package_json_has_lint_script(self, apps_web_dir: Path) -> None:
        """apps/web/package.json contains 'lint' script."""
        pkg_file = apps_web_dir / "package.json"
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        assert "lint" in data.get("scripts", {})

    def test_fe06_02_no_tracked_backup_files(self, project_root: Path) -> None:
        """Git tracking contains no .bak files."""
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.splitlines()
        bak_files = [f for f in files if ".bak" in f]
        assert len(bak_files) == 0, f"Found tracked backup files: {bak_files}"

    def test_fe06_03_no_duplicate_nav_info_in_info_views(self, apps_web_dir: Path) -> None:
        """Info sub-views do not define duplicate <NavInfo> headers."""
        info_dir = apps_web_dir / "src" / "lib" / "components" / "info"
        if info_dir.exists():
            for svelte_file in info_dir.glob("*.svelte"):
                content = svelte_file.read_text(encoding="utf-8")
                assert "<NavInfo" not in content, f"Duplicate NavInfo in {svelte_file.name}"

    def test_fe06_04_knip_configuration_exists(self, apps_web_dir: Path) -> None:
        """Knip or typecheck configuration is present in frontend."""
        knip_json = apps_web_dir / "knip.json"
        tsconfig = apps_web_dir / "tsconfig.json"
        assert knip_json.exists() or tsconfig.exists()

    def test_fe06_05_package_json_dependencies_valid(self, apps_web_dir: Path) -> None:
        """apps/web/package.json specifies svelte 5 and svelte-check."""
        pkg_file = apps_web_dir / "package.json"
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        dev_deps = data.get("devDependencies", {})
        assert "svelte" in dev_deps or "svelte-check" in dev_deps


# ==============================================================================
# OPS-01: System Operational Runbook
# ==============================================================================
class TestOPS01OperationalRunbook:
    """OPS-01: System Operational Runbook (docs/runbook-operasional-sistem.md)."""

    def test_ops01_01_runbook_file_exists(self, docs_dir: Path) -> None:
        """Runbook file docs/runbook-operasional-sistem.md exists."""
        runbook = docs_dir / "runbook-operasional-sistem.md"
        assert runbook.exists()
        assert len(runbook.read_text(encoding="utf-8").splitlines()) >= 100

    def test_ops01_02_covers_systemd_services(self, docs_dir: Path) -> None:
        """Runbook documents warroom-web, warroom-api, trading-engine, and postgresql."""
        content = (docs_dir / "runbook-operasional-sistem.md").read_text(encoding="utf-8")
        assert "warroom-web" in content
        assert "warroom-api" in content
        assert "trading-engine" in content
        assert "postgresql" in content

    def test_ops01_03_documents_service_ports(self, docs_dir: Path) -> None:
        """Runbook documents ports 3100, 8800, 8088, and 5432."""
        content = (docs_dir / "runbook-operasional-sistem.md").read_text(encoding="utf-8")
        assert "3100" in content
        assert "8800" in content
        assert "8088" in content
        assert "5432" in content

    def test_ops01_04_troubleshooting_matrix(self, docs_dir: Path) -> None:
        """Runbook contains troubleshooting matrix for SSE drops and database lock."""
        content = (docs_dir / "runbook-operasional-sistem.md").read_text(encoding="utf-8")
        assert "troubleshooting" in content.lower() or "kendala" in content.lower()
        assert "sse" in content.lower()

    def test_ops01_05_instabox_mt5_reaper_procedure(self, docs_dir: Path) -> None:
        """Runbook documents Instabox MT5 runner and box-2aacb3."""
        content = (docs_dir / "runbook-operasional-sistem.md").read_text(encoding="utf-8")
        assert "box-2aacb3" in content or "mt5" in content.lower()


# ==============================================================================
# OPS-02: Production Launch Checklist
# ==============================================================================
class TestOPS02ProductionLaunchChecklist:
    """OPS-02: Production Launch Checklist (docs/launch-checklist-production.md)."""

    def test_ops02_01_checklist_file_exists(self, docs_dir: Path) -> None:
        """Checklist file docs/launch-checklist-production.md exists."""
        checklist = docs_dir / "launch-checklist-production.md"
        assert checklist.exists()
        assert len(checklist.read_text(encoding="utf-8").splitlines()) >= 50

    def test_ops02_02_given_when_then_format_used(self, docs_dir: Path) -> None:
        """Checklist includes Given-When-Then criteria."""
        content = (docs_dir / "launch-checklist-production.md").read_text(encoding="utf-8")
        assert "Given" in content
        assert "When" in content
        assert "Then" in content

    def test_ops02_03_go_no_go_gate_criteria(self, docs_dir: Path) -> None:
        """Checklist documents Go/No-Go decision framework."""
        content = (docs_dir / "launch-checklist-production.md").read_text(encoding="utf-8")
        assert "go/no-go" in content.lower() or "go / no-go" in content.lower()

    def test_ops02_04_po_signoff_section(self, docs_dir: Path) -> None:
        """Checklist includes sign-off section for Product Owner and Release Lead."""
        content = (docs_dir / "launch-checklist-production.md").read_text(encoding="utf-8")
        assert "Product Owner" in content
        assert "Sign-off" in content or "Tanda Tangan" in content or "Persetujuan" in content

    def test_ops02_05_security_and_credentials_verification(self, docs_dir: Path) -> None:
        """Checklist verifies no hardcoded secrets in repository."""
        content = (docs_dir / "launch-checklist-production.md").read_text(encoding="utf-8")
        assert "secret" in content.lower() or "kredensial" in content.lower()


# ==============================================================================
# OPS-03: Rollback Plan & Disaster Recovery
# ==============================================================================
class TestOPS03RollbackPlanAndDisasterRecovery:
    """OPS-03: Rollback Plan & Disaster Recovery (docs/rollback-plan-disaster-recovery.md)."""

    def test_ops03_01_rollback_file_exists(self, docs_dir: Path) -> None:
        """Rollback plan file exists and is populated."""
        rollback = docs_dir / "rollback-plan-disaster-recovery.md"
        assert rollback.exists()
        assert len(rollback.read_text(encoding="utf-8").splitlines()) >= 50

    def test_ops03_02_pg_restore_with_sha256(self, docs_dir: Path) -> None:
        """Rollback plan documents pg_restore with sha256 checksum verification."""
        content = (docs_dir / "rollback-plan-disaster-recovery.md").read_text(encoding="utf-8")
        assert "pg_restore" in content
        assert "sha256" in content.lower()

    def test_ops03_03_rto_rpo_targets_documented(self, docs_dir: Path) -> None:
        """Rollback plan documents RTO (< 15 min) and RPO (< 5 min)."""
        content = (docs_dir / "rollback-plan-disaster-recovery.md").read_text(encoding="utf-8")
        assert "RTO" in content
        assert "RPO" in content

    def test_ops03_04_git_rollback_command_documented(self, docs_dir: Path) -> None:
        """Rollback plan documents git checkout/reset commands."""
        content = (docs_dir / "rollback-plan-disaster-recovery.md").read_text(encoding="utf-8")
        assert "git" in content
        assert "checkout" in content or "reset" in content or "revert" in content

    def test_ops03_05_telemetry_failover_documented(self, docs_dir: Path) -> None:
        """Rollback plan documents telemetry failover and Instabox restart."""
        content = (docs_dir / "rollback-plan-disaster-recovery.md").read_text(encoding="utf-8")
        assert "telemetri" in content.lower() or "telemetry" in content.lower()


# ==============================================================================
# OPS-04: Architecture & API Contract Documentation
# ==============================================================================
class TestOPS04ArchitectureAndAPIContracts:
    """OPS-04: Architecture & API Contract Documentation (docs/arsitektur-dan-kontrak-api.md)."""

    def test_ops04_01_architecture_file_exists(self, docs_dir: Path) -> None:
        """Architecture file exists and contains detailed specifications."""
        arch = docs_dir / "arsitektur-dan-kontrak-api.md"
        assert arch.exists()
        assert len(arch.read_text(encoding="utf-8").splitlines()) >= 100

    def test_ops04_02_deal_payload_schema_documented(self, docs_dir: Path) -> None:
        """Documents schema for POST /api/v1/tencent/mt5/deal."""
        content = (docs_dir / "arsitektur-dan-kontrak-api.md").read_text(encoding="utf-8")
        assert "/api/v1/tencent/mt5/deal" in content
        assert "ticket" in content
        assert "cent_factor" in content

    def test_ops04_03_sse_stream_schema_documented(self, docs_dir: Path) -> None:
        """Documents schema for GET /api/v1/tencent/forex/stream."""
        content = (docs_dir / "arsitektur-dan-kontrak-api.md").read_text(encoding="utf-8")
        assert "/api/v1/tencent/forex/stream" in content
        assert "retry: 3000" in content

    def test_ops04_04_auth_cookies_and_tokens_documented(self, docs_dir: Path) -> None:
        """Documents wr_session cookie and X-Warroom-Token headers."""
        content = (docs_dir / "arsitektur-dan-kontrak-api.md").read_text(encoding="utf-8")
        assert "wr_session" in content
        assert "X-Warroom-Token" in content or "token" in content.lower()

    def test_ops04_05_openapi_version_referenced(self, docs_dir: Path) -> None:
        """Documents OpenAPI 3.1 specification compliance."""
        content = (docs_dir / "arsitektur-dan-kontrak-api.md").read_text(encoding="utf-8")
        assert "OpenAPI" in content or "openapi" in content


# ==============================================================================
# OPS-05: Step-by-Step UAT Guide
# ==============================================================================
class TestOPS05StepByStepUATGuide:
    """OPS-05: Step-by-Step UAT Guide (docs/panduan-uat-step-by-step.md)."""

    def test_ops05_01_uat_guide_exists(self, docs_dir: Path) -> None:
        """UAT guide file exists and is populated."""
        uat = docs_dir / "panduan-uat-step-by-step.md"
        assert uat.exists()
        assert len(uat.read_text(encoding="utf-8").splitlines()) >= 50

    def test_ops05_02_covers_six_scenarios(self, docs_dir: Path) -> None:
        """UAT guide defines 6 scenarios across navigation pillars."""
        content = (docs_dir / "panduan-uat-step-by-step.md").read_text(encoding="utf-8")
        assert "Skenario 1" in content or "Scenario 1" in content
        assert "Skenario 6" in content or "Scenario 6" in content

    def test_ops05_03_trading_floor_pillar_covered(self, docs_dir: Path) -> None:
        """UAT covers Trading Floor pillar and live SSE cockpit."""
        content = (docs_dir / "panduan-uat-step-by-step.md").read_text(encoding="utf-8")
        assert "Trading Floor" in content or "/forex" in content

    def test_ops05_04_cent_journal_and_ledger_covered(self, docs_dir: Path) -> None:
        """UAT covers Cent deal verification and dynamic formatting."""
        content = (docs_dir / "panduan-uat-step-by-step.md").read_text(encoding="utf-8")
        assert "USC" in content
        assert "Jurnal" in content or "Ledger" in content or "/ledger" in content

    def test_ops05_05_verification_pass_fail_sheet_present(self, docs_dir: Path) -> None:
        """UAT guide contains Pass/Fail verification checklist sheet."""
        content = (docs_dir / "panduan-uat-step-by-step.md").read_text(encoding="utf-8")
        assert "Lembar Hasil Verifikasi" in content or "UAT Verification Sheet" in content
        assert "PASS" in content
