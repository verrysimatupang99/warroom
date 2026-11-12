"""
Laya Sentinel Signal Extractor & Quantitative Parser
Mengekstrak sinyal mentah Telegram (XAUUSD & NASDAQ/USTEC) menjadi objek siap validasi
dengan aturan lot baku (Hard Command: 0.10 lot).
"""

import re
from typing import Any

FIXED_LOT = 0.10

MILESTONE_PATTERNS = [
    r"\b(?:tp\s*[1-5]?|take\s*profit\s*[1-5]?)\s*(?:hit|done|reach(?:ed)?|smack(?:ed)?)\b",
    r"\b(?:hit|reached|smacked)\s+(?:tp\s*[1-5]?|take\s*profit\s*[1-5]?)\b",
    r"\b(?:sl|stop\s*loss)\s*(?:hit|touched)\b",
    r"\b(?:running|running\s*profit)\s*[:\+]?\s*\d+\s*(?:pips?|pts?|points?)\b",
    r"\b\d+\s*pips?\s*(?:running|done|profit|gain|booked|banked|secured?)\b",
    r"[🟢🔥✅🚀💰]+\s*\+?\d+\s*pips?",
    r"\+?\d+\s*pips?\s*[🟢🔥✅🚀💰]+",
    r"\b(?:set|move)\s*(?:sl\s*to\s*)?(?:bep|breakeven|entry)\b",
    r"\b(?:close\s*half|secure\s*(?:profit|some|half)|partial\s*close)\b",
    r"^\s*🟢?\s*\+?\d+\s*pips?\b",
]


def is_milestone_or_update(text: str) -> bool:
    """Deteksi apakah teks sinyal adalah update status running profit, milestone TP, hit SL, atau BEP."""
    if not text:
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in MILESTONE_PATTERNS)


def classify_signal_type(text: str) -> str:
    """Klasifikasi tipe pesan sinyal: ENTRY, MILESTONE, atau UPDATE_BEP."""
    if is_milestone_or_update(text):
        if re.search(r"\b(?:bep|breakeven|entry)\b", text, re.IGNORECASE):
            return "UPDATE_BEP"
        return "MILESTONE"
    return "ENTRY"


def parse_forex_signal(text: str, channel_name: str = "") -> dict[str, Any] | None:
    if not text:
        return None

    clean_text = text.replace(",", ".")
    is_milestone = is_milestone_or_update(clean_text)
    sig_type = classify_signal_type(clean_text)

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
        # Jika channel adalah channel Forex/Gold spesifik (misal Callisto / FXM),
        # default ke XAUUSD bila ada setup Buy/Sell atau milestone update.
        if any(k in channel_name.lower() for k in ["callisto", "gold", "fxm"]):
            if re.search(r"\b(BUY|SELL)\b", clean_text, re.I) or is_milestone:
                symbol = "XAUUSD"

    if not symbol:
        return None

    # 2. Deteksi Aksi (BUY / SELL / PENDING)
    action = None
    # Jika pesan adalah milestone/update status profit, jangan interpretasikan kata "BUY/SELL"
    # sebagai order entry baru kecuali ada parameter entry/sl eksplisit
    is_pure_milestone = is_milestone and not re.search(
        r"\b(?:entry|zone|zona|limit|stop)\b", clean_text, re.I
    )

    if not is_pure_milestone:
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

    if not action and not is_milestone:
        return None

    # 3. Deteksi Entry (Bisa berupa single level atau Range Zona)
    entry_low = None
    entry_high = None
    entry_match = re.search(
        r"(?:entry\s*price|entry|zone|zona|zona entry|at|@|limit|stop)[:\s]*"
        r"([0-9]{3,6}(?:\.[0-9]+)?)"
        r"(?:\s*[-–/]\s*([0-9]{3,6}(?:\.[0-9]+)?))?",
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

    tp1_m = re.search(
        r"(?:tp\s*1\b|take\s*profit\s*1\b|tp\b|take\s*profit\b)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)",
        clean_text,
        re.I,
    )
    if tp1_m:
        tp1 = float(tp1_m.group(1))

    tp2_m = re.search(
        r"(?:tp\s*2\b|take\s*profit\s*2\b)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)",
        clean_text,
        re.I,
    )
    if tp2_m:
        tp2 = float(tp2_m.group(1))

    tp3_m = re.search(
        r"(?:tp\s*3\b|take\s*profit\s*3\b)[:\s]*([0-9]{3,6}(?:\.[0-9]+)?)",
        clean_text,
        re.I,
    )
    if tp3_m:
        tp3 = float(tp3_m.group(1))

    # Deteksi TP jika berjejer "TP: 4025.00 / 4019.00 / 4005.00" atau "TP 2660 / 2670 / 2680"
    if (not tp2 or not tp1) and "TP" in clean_text.upper():
        tp_idx = clean_text.upper().find("TP")
        tp_snippet = clean_text[tp_idx : tp_idx + 80]
        if "/" in tp_snippet or " - " in tp_snippet:
            tp_multi = re.findall(r"[0-9]{3,6}(?:\.[0-9]+)?", tp_snippet)
            if len(tp_multi) > 1:
                tp1 = float(tp_multi[0])
                tp2 = float(tp_multi[1])
                if len(tp_multi) > 2:
                    tp3 = float(tp_multi[2])

    return {
        "symbol": symbol,
        "action": action,
        "signal_type": sig_type,
        "is_milestone": is_milestone,
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
