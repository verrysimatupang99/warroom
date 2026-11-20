from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from live_trading.strategies import StrategyRegistry
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
_registry = StrategyRegistry()


class TogglePayload(BaseModel):
    enabled: bool


@router.get("")
def list_strategies(market: str | None = Query(default=None)):
    """Daftar seluruh strategi modular yang terdaftar di registry."""
    items = _registry.list_strategies(market=market)
    return {"status": "OK", "count": len(items), "strategies": items}


@router.post("/{strategy_id}/toggle")
def toggle_strategy(strategy_id: str, payload: TogglePayload):
    """Aktifkan atau nonaktifkan strategi modular secara dinamis."""
    updated = _registry.toggle(strategy_id, payload.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Strategi '{strategy_id}' tidak ditemukan")
    return {"status": "OK", "strategy": updated}


@router.post("/{strategy_id}/backtest")
def run_strategy_backtest(strategy_id: str):
    """Jalankan backtest on-demand untuk strategi modular tertentu."""
    strat = _registry.get(strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail=f"Strategi '{strategy_id}' tidak ditemukan")
    result = strat.backtest(candles=[])
    return {"status": "OK", "strategy_id": strategy_id, "result": result}
