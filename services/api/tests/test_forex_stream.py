"""
Tes endpoint SSE streaming telemetri MT5.
"""

from __future__ import annotations

import asyncio

import pytest
from warroom_api.routers.tencent import (
    _broadcast_sse_telemetry,
    _telemetry_subscribers,
)


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
