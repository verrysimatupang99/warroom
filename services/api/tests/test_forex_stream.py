"""
Tes endpoint SSE streaming telemetri MT5, isolasi dekomisioning VM2, dan atribusi Deal Cent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
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
from warroom_core.trades_forex import ke_trade


@pytest.mark.asyncio
async def test_sse_broadcast_subscriber():
    queue: asyncio.Queue = asyncio.Queue(maxsize=5)
    _telemetry_subscribers.append(queue)
    try:
        sample = {"account": "452009427", "balance": 1074.81, "equity": 1074.81}
        _broadcast_sse_telemetry(sample)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["account"] == "452009427"
        assert received["balance"] == 1074.81
    finally:
        if queue in _telemetry_subscribers:
            _telemetry_subscribers.remove(queue)


@pytest.mark.asyncio
async def test_stream_forex_telemetry_default_account_and_retry_header():
    """US-03: Stream default ke akun 452009427 dan menyertakan retry: 3000\\n."""
    latest_mt5_by_account[ACTIVE_CENT_ACCOUNT] = {
        "account": ACTIVE_CENT_ACCOUNT,
        "balance": 1074.81,
        "equity": 1074.81,
    }

    # Panggil tanpa account param
    response = await stream_forex_telemetry(account=None)
    gen = response.body_iterator

    # Chunk 1: Header SSE retry directive
    chunk1 = await gen.__anext__()
    assert "retry: 3000\n" in chunk1

    # Chunk 2: Initial snapshot dengan retry header
    chunk2 = await gen.__anext__()
    assert "retry: 3000\n" in chunk2
    assert "452009427" in chunk2
    assert "1074.81" in chunk2


@pytest.mark.asyncio
async def test_report_mt5_telemetry_hard_isolation_decommissioned_vm():
    """US-06: Akun 36525553 atau broker Vantage tidak boleh menerima SYNC_EA_V2 / exec_powershell."""
    # 1. Akun Azure VM2 (36525553)
    p_azure = MT5TelemetryPayload(
        account="36525553",
        broker="Vantage International",
        balance=500.0,
        equity=500.0,
        margin=0.0,
        free_margin=500.0,
        floating_pnl=0.0,
    )
    res_azure = await report_mt5_telemetry(p_azure)
    assert res_azure["status"] == "OK"
    assert res_azure["action"] == "OK"
    assert "exec_powershell" not in res_azure
    assert res_azure.get("action") != "SYNC_EA_V2"

    # 2. Broker Vantage dengan akun lain
    p_vantage = MT5TelemetryPayload(
        account="999999",
        broker="Vantage FX Ltd",
        balance=100.0,
        equity=100.0,
        margin=0.0,
        free_margin=100.0,
        floating_pnl=0.0,
    )
    res_vantage = await report_mt5_telemetry(p_vantage)
    assert res_vantage["status"] == "OK"
    assert res_vantage["action"] == "OK"
    assert "exec_powershell" not in res_vantage


@pytest.mark.asyncio
async def test_report_mt5_deal_cent_attribution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """US-02: Deal dari akun cent Exness mengatribusikan currency USC dan cent_factor 100."""
    deal_file = tmp_path / "deals.csv"
    monkeypatch.setattr("warroom_api.routers.tencent.DEAL_LOG", deal_file)

    payload = MT5DealPayload(
        ticket=12345678,
        position=12345678,
        symbol="XAUUSD",
        side="BUY",
        volume=0.10,
        open_time="2026-11-12 10:00:00",
        close_time="2026-11-12 10:05:00",
        profit=250.0,
        account="452009427",
        currency="USC",
        cent_factor=100.0,
    )
    res = await report_mt5_deal(payload)
    assert res["status"] == "OK"
    assert res["currency"] == "USC"
    assert res["cent_factor"] == 100.0
    assert res["net"] == 250.0


def test_ke_trade_cent_normalization():
    """US-02: Trade normalization pnl_usd = net / 100.0 untuk akun USC."""
    baris_deal = {
        "ticket": "887766",
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": "0.10",
        "open_price": "2650.0",
        "close_price": "2652.5",
        "net": 250.0,
        "account": "452009427",
        "strategy_version": "v2.0",
        "currency": "USC",
        "cent_factor": 100.0,
    }
    trade = ke_trade(baris_deal)
    assert trade is not None
    assert trade.pnl_usd == 2.50
    assert trade.evidence_json["currency"] == "USC"
    assert trade.evidence_json["cent_factor"] == 100.0
    assert trade.evidence_json["net_usc"] == 250.0
