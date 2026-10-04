"""Uji penjaga belanja + circuit breaker (pola llm-trading-agent-security)."""

import pytest

from live_trading.guards import (
    SpendLimitError,
    SpendLimitGuard,
    TradingCircuitBreaker,
)


def test_tx_lewat_batas_ditolak():
    g = SpendLimitGuard()
    with pytest.raises(SpendLimitError):
        g.check_and_record(501.0)


def test_harian_akumulasi():
    g = SpendLimitGuard(max_single=1000.0, max_daily=1000.0)
    g.check_and_record(600.0)
    with pytest.raises(SpendLimitError):
        g.check_and_record(500.0)


def test_halt_tiga_rugi_beruntun():
    b = TradingCircuitBreaker()
    b.catat_hasil(-1.0)
    b.catat_hasil(-2.0)
    assert b.boleh_jalan() is True
    b.catat_hasil(-0.5)
    assert b.boleh_jalan() is False
    assert "beruntun" in b.alasan().lower()


def test_menang_reset_beruntun():
    b = TradingCircuitBreaker()
    b.catat_hasil(-1.0)
    b.catat_hasil(-1.0)
    b.catat_hasil(5.0)
    assert b.boleh_jalan() is True
