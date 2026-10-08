import pytest
from warroom_core.signal import Decision, MarketData, Signal
from warroom_core.strategy import Strategy


class DemoStrategy(Strategy):
    name = "demo"

    def scan(self, market_data: MarketData) -> list[Signal]:
        return []

    def validate(self, signal: Signal, context: dict[str, object]) -> Decision:
        return Decision(True, "demo")


def test_strategy_protocol_requires_scan_and_validate():
    assert DemoStrategy().name == "demo"
    assert set(Strategy.__abstractmethods__) == {"scan", "validate"}


def test_strategy_cannot_be_instantiated_without_methods():
    with pytest.raises(TypeError):
        Strategy()
