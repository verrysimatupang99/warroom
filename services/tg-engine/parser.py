"""
Laya Sentinel Signal Extractor & Quantitative Parser
Mengekstrak sinyal mentah Telegram (XAUUSD & NASDAQ/USTEC) menjadi objek siap validasi
dengan aturan lot baku (Hard Command: 0.10 lot).
"""

import re
from typing import Any

FIXED_LOT = 0.10


def parse_forex_signal(text: str, channel_name: str = "") -> dict[str, Any] | None:
    if not text:
        return None

    clean_text = text.replace(",", ".")

    # 1. Deteksi Simbol (XAUUSD / Gold vs NASDAQ / USTEC)
    symbol = None
    if re.search(r"\b(XAUUSD|GOLD|XAU)\b", clean_text, re.I):
        symbol = "XAUUSD"
    elif re.search(r"\b(USTEC|NAS100|NASDAQ|US100|NDX)\b", clean_text, re.I):
        symbol = "USTEC"
    elif re.search(r"\b(EURUSD|GBPUSD|USDJPY)\b", clean_text, re.I):
        m = re.search(r"\b(EURUSD|GBPUSD|USDJPY)\b", clean_text, re.I)
        symbol = m.group(1).upper()
    else:
        # Jika channel adalah channel Forex/Gold spesifik (misal Callisto / FXM), default ke XAUUSD jika ada setup Buy/Sell
        if any(k in channel_name.lower() for k in ["callisto", "gold", "fxm"]):
            if re.search(r"\b(BUY|SELL)\b", clean_text, re.I):
                symbol = "XAUUSD"

    if not symbol:
        return None

    # 2. Deteksi Aksi
    action = None
    if re.search(r"\bBUY\s*LIMIT\b", clean_text, re.I):
        action = "BUY LIMIT"
    elif re.search(r"\bSELL\s*LIMIT\b", clean_text, re.I):
        action = "SELL LIMIT"
    elif re.search(r"\bBUY\s*STOP\b", clean_text, re.I):
        action = "BUY STOP"
    elif re.search(r"\bSELL\s*STOP\b", clean_text, re.I):
        action = "SELL STOP"
    elif re.search(r"\bBUY(?:\s*NOW)?\b", clean_text, re.I):
        action = "BUY"
    elif re.search(r"\bSELL(?:\s*NOW)?\b", clean_text, re.I):
        action = "SELL"

    if not action:
        return None

    # 3. Deteksi Entry (Bisa berupa single level atau Range Zona)
    entry_low = None
    entry_high = None
    entry_match = re.search(
        r"(?:entry\s*price|entry|zone|zona|zona entry|at|@|limit|stop)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)(?:\s*[-–/]\s*([0-9]{3,6}(?:\.[0-9]+)?))?",
        clean_text,
        re.I,
    )
    if entry_match and entry_match.group(1):
        entry_low = float(entry_match.group(1))
        entry_high = float(entry_match.group(2)) if entry_match.group(2) else entry_low

    # 4. Deteksi Stop Loss (SL)
    sl = None
    sl_match = re.search(r"(?:sl|stop\s*loss)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)", clean_text, re.I)
    if sl_match:
        sl = float(sl_match.group(1))

    # 5. Deteksi Take Profit (TP / TP1 / TP2 / TP3)
    tp1 = None
    tp2 = None
    tp3 = None

    tp1_m = re.search(r"(?:tp\s*1?|take\s*profit\s*1?)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)", clean_text, re.I)
    if tp1_m:
        tp1 = float(tp1_m.group(1))

    tp2_m = re.search(r"(?:tp\s*2|take\s*profit\s*2)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)", clean_text, re.I)
    if tp2_m:
        tp2 = float(tp2_m.group(1))

    tp3_m = re.search(r"(?:tp\s*3|take\s*profit\s*3)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)", clean_text, re.I)
    if tp3_m:
        tp3 = float(tp3_m.group(1))

    # Fallback TP jika format berjejer "TP: 4025.00 / 4019.00 / 4005.00"
    if not tp1:
        tp_multi = re.findall(
            r"[0-9]{3,6}(?:\.[0-9]+)?",
            clean_text[clean_text.upper().find("TP") : clean_text.upper().find("TP") + 50]
            if "TP" in clean_text.upper()
            else "",
        )
        if tp_multi:
            tp1 = float(tp_multi[0])
            if len(tp_multi) > 1:
                tp2 = float(tp_multi[1])
            if len(tp_multi) > 2:
                tp3 = float(tp_multi[2])

    return {
        "symbol": symbol,
        "action": action,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "lot": FIXED_LOT,
        "source_channel": channel_name,
        "raw_text": text,
    }
