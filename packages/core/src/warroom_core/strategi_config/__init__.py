"""Layer konfigurasi strategy War Room — strategy sebagai config, bukan kode.

Tujuan: strategy mudah dikonfigurasi (kayak variabel/formula screener Stockbit)
untuk semua market, terpisah dari codebase platform. Satu definisi strategy
dipakai tiga mode evaluasi: backtest (masa lalu), screener (hari ini),
paper bot (masa depan).

Modul:
- variabel  : indikator teknikal (EMA, RSI, ATR, ...)
- formula   : evaluator ekspresi aman (tanpa eval())
- config    : loader & validator config strategy YAML
- backtest  : engine backtest -> statistik
"""
from .backtest import BacktestResult, baca_candles, jalankan_backtest
from .config import ConfigError, StrategyConfig, muat_config
from .formula import FormulaError, evaluasi

__all__ = [
    "ConfigError", "StrategyConfig", "muat_config",
    "FormulaError", "evaluasi",
    "BacktestResult", "baca_candles", "jalankan_backtest",
]
