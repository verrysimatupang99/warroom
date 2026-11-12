"""
Tes unit untuk parser sinyal Telegram dan pendeteksi milestone / status update.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser import classify_signal_type, is_milestone_or_update, parse_forex_signal


class TestParserMilestone:
    def test_milestone_pips_hijau(self):
        text = "🟢 40 Pips"
        assert is_milestone_or_update(text) is True
        assert classify_signal_type(text) == "MILESTONE"
        parsed = parse_forex_signal(text, "Callisto FX")
        assert parsed is not None
        assert parsed["symbol"] == "XAUUSD"
        assert parsed["is_milestone"] is True
        assert parsed["action"] is None

    def test_milestone_tp_hit_running(self):
        text = "XAUUSD BUY RUNNING 30 PIPS TP1 HIT"
        assert is_milestone_or_update(text) is True
        assert classify_signal_type(text) == "MILESTONE"
        parsed = parse_forex_signal(text, "")
        assert parsed is not None
        assert parsed["symbol"] == "XAUUSD"
        assert parsed["is_milestone"] is True
        assert parsed["action"] is None  # Tidak boleh diartikan order BUY baru

    def test_milestone_tp_smacked(self):
        text = "TP 1 SMACKED 🔥 +40 Pips"
        assert is_milestone_or_update(text) is True
        assert classify_signal_type(text) == "MILESTONE"

    def test_milestone_running_profit_variations(self):
        assert is_milestone_or_update("Running +50 pips secure half") is True
        assert is_milestone_or_update("TP2 hit 80 pips running") is True
        assert is_milestone_or_update("SL hit -25 pips") is True
        assert is_milestone_or_update("closed +35 pips banked") is True
        assert is_milestone_or_update("🔥 60 Pips") is True

    def test_update_bep(self):
        text = "Move SL to BEP / Entry now!"
        assert is_milestone_or_update(text) is True
        assert classify_signal_type(text) == "UPDATE_BEP"

    def test_sinyal_entry_valid_bukan_milestone(self):
        text = "GOLD BUY NOW @ 2650.50 SL: 2640.00 TP1: 2665.00 TP2: 2680.00"
        assert is_milestone_or_update(text) is False
        assert classify_signal_type(text) == "ENTRY"
        parsed = parse_forex_signal(text, "")
        assert parsed is not None
        assert parsed["symbol"] == "XAUUSD"
        assert parsed["action"] == "BUY"
        assert parsed["signal_type"] == "ENTRY"
        assert parsed["is_milestone"] is False
        assert parsed["entry_low"] == 2650.50
        assert parsed["sl"] == 2640.00
        assert parsed["tp1"] == 2665.00
        assert parsed["tp2"] == 2680.00

    def test_multiple_tp_slashes(self):
        text = "XAUUSD BUY @ 2650 SL: 2640 TP: 2660 / 2670 / 2680"
        assert is_milestone_or_update(text) is False
        parsed = parse_forex_signal(text, "")
        assert parsed is not None
        assert parsed["tp1"] == 2660.0
        assert parsed["tp2"] == 2670.0
        assert parsed["tp3"] == 2680.0

    def test_nasdaq_pending_order(self):
        text = "USTEC SELL LIMIT @ 18500 - 18520 SL 18560 TP 18400"
        assert is_milestone_or_update(text) is False
        assert classify_signal_type(text) == "ENTRY"
        parsed = parse_forex_signal(text, "")
        assert parsed is not None
        assert parsed["symbol"] == "USTEC"
        assert parsed["action"] == "SELL LIMIT"
        assert parsed["entry_low"] == 18500.0
        assert parsed["entry_high"] == 18520.0
        assert parsed["sl"] == 18560.0
        assert parsed["tp1"] == 18400.0

    def test_obrolan_kosong_atau_general(self):
        assert parse_forex_signal("", "") is None
        assert parse_forex_signal("Selamat pagi rekan trader, jangan lupa ngopi", "") is None
