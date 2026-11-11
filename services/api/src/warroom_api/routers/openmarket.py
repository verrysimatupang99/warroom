"""Router OpenMarket — cakupan venue/tipe data/pasar (read-only, angka statis).

Kehadiran OPENMARKET_API_KEY menentukan `tersedia`: tanpa key, halaman tetap
tampil tapi jujur bilang belum aktif — bukan data kosong yang menyamar sehat.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from warroom_core.db import User

from warroom_api import auth

router = APIRouter(tags=["openmarket"])

# Venue utama yang disajikan OpenMarket (subset; total 21 venue di enum MCP).
VENUE = [
    "BINANCE_FUTURES",
    "BINANCE_SPOT",
    "BYBIT",
    "OKX",
    "HYPERLIQUID",
    "COINBASE",
    "DERIBIT",
    "BITFINEX",
    "CME",
    "BITMEX",
    "GATE_IO",
    "POLYMARKET",
    "POLYGON",
]

TIPE_DATA = [
    "candles",
    "trades",
    "order_book",
    "funding_rate",
    "open_interest",
    "liquidations",
    "volume_profile",
    "tpo",
    "implied_volatility",
    "skew",
    "block_book",
    "token_supply",
    "hyperliquid_liquidations",
]

INTERVAL = [
    "MINUTE",
    "FIVE_MINUTES",
    "FIFTEEN_MINUTES",
    "THIRTY_MINUTES",
    "HOUR",
    "FOUR_HOURS",
    "DAY",
    "WEEK",
]

PASAR = [
    {"nama": "Crypto", "cakupan": "4.000+ pair, 29 venue"},
    {"nama": "Saham US", "cakupan": "5.500+ saham & ETF (NYSE/Nasdaq)"},
    {"nama": "Futures", "cakupan": "CME index, rates, energy, metals"},
    {"nama": "Options", "cakupan": "7 venue crypto + CME, IV & skew"},
    {"nama": "Forex", "cakupan": "1.200+ pair + gold/silver"},
    {"nama": "Prediction markets", "cakupan": "odds rate/pemilu/event"},
    {"nama": "Economic data", "cakupan": "CPI/GDP/NFP, 5.600+ seri"},
]


@router.get("/api/v1/openmarket/cakupan")
def cakupan(user: Annotated[User, Depends(auth.current_user)]) -> dict:
    """Cakupan OpenMarket (statis) + status aktivasi (ada OPENMARKET_API_KEY)."""
    tersedia = bool(os.environ.get("OPENMARKET_API_KEY"))
    return {
        "tersedia": tersedia,
        "alasan": (
            None
            if tersedia
            else "OPENMARKET_API_KEY belum di-set (ambil di openmarket.xyz/api)"
        ),
        "venue": VENUE,
        "jumlah_venue": 21,
        "tipe_data": TIPE_DATA,
        "interval": INTERVAL,
        "pasar": PASAR,
        "catatan": (
            "OpenMarketProvider (packages/core) memakai endpoint "
            "api.kiyotaka.ai/v1/points untuk candle; strategi market: openmarket "
            "memakainya lewat backtest/screener/paper-bot."
        ),
        "sumber": "openmarket.xyz + enum OpenMarket MCP",
    }
