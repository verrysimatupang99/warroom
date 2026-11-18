from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any

from .base import BaseStrategy


class StrategyRegistry:
    """Registry dinamis untuk auto-discovery dan manajemen strategi modular."""

    def __init__(self, state_path: Path | None = None) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._state_path = state_path or Path("/var/lib/warroom/strategies_state.json")
        self._discover()
        self._load_state()

    def _discover(self) -> None:
        pkg_dir = Path(__file__).resolve().parent
        for mod_info in pkgutil.iter_modules([str(pkg_dir)]):
            if mod_info.name in ("base", "registry", "__init__"):
                continue
            module = importlib.import_module(f"{__package__}.{mod_info.name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseStrategy)
                    and attr is not BaseStrategy
                ):
                    instance = attr()
                    self._strategies[instance.id] = instance

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for sid, enabled in data.items():
                    if sid in self._strategies and isinstance(enabled, bool):
                        self._strategies[sid].enabled = enabled
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {sid: s.enabled for sid, s in self._strategies.items()}
            self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def list_strategies(self, market: str | None = None) -> list[dict[str, Any]]:
        items = list(self._strategies.values())
        if market and market != "all":
            items = [s for s in items if s.market == market]
        return [s.to_dict() for s in sorted(items, key=lambda x: (x.market, x.id))]

    def get(self, strategy_id: str) -> BaseStrategy | None:
        return self._strategies.get(strategy_id)

    def toggle(self, strategy_id: str, enabled: bool) -> dict[str, Any] | None:
        strat = self._strategies.get(strategy_id)
        if not strat:
            return None
        strat.enabled = enabled
        self._save_state()
        return strat.to_dict()
