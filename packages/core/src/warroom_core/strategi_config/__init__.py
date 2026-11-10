"""Layer konfigurasi strategy War Room — strategy sebagai config, bukan kode.

Tujuan: strategy mudah dikonfigurasi (kayak variabel/formula screener Stockbit)
untuk semua market, terpisah dari codebase platform. Satu definisi strategy
dipakai tiga mode evaluasi: backtest (masa lalu), screener (hari ini),
paper bot (masa depan).

Modul:
- variabel  : indikator teknikal (EMA, RSI, ATR, ...)
- formula   : evaluator ekspresi aman (tanpa eval())
- config    : loader & validator config strategy YAML
- provider  : sumber data candle per market (Binance crypto/memecoin)
- backtest  : engine backtest -> statistik
- screener  : scan setup live hari ini
- paper_bot : eksekusi kertas stateful (buka/tutup posisi, ledger)
"""
from .backtest import BacktestResult, baca_candles, jalankan_backtest
from .config import ConfigError, StrategyConfig, muat_config
from .formula import FormulaError, evaluasi
from .paper_bot import jalankan_paper_bot
from .provider import BinanceProvider, DataProvider, provider_untuk
from .screener import SetupScreener, scan_satu, scan_semua

__all__ = [
    "ConfigError", "StrategyConfig", "muat_config",
    "FormulaError", "evaluasi",
    "BacktestResult", "baca_candles", "jalankan_backtest",
    "DataProvider", "BinanceProvider", "provider_untuk",
    "SetupScreener", "scan_satu", "scan_semua",
    "jalankan_paper_bot",
]
