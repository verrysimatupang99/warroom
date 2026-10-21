#!/usr/bin/env python3
"""
scripts/notify_all_markets_signal.py
Pipeline Scanner Multi-Market Real-Time Sinyal Break & Retest 15m untuk:
- Forex & Gold: XAUUSD, EURUSD, GBPUSD
- Crypto: BTCUSDT, SOLUSDT

Memformat sinyal Model A dan mengirimkannya langsung ke Telegram War Room / HP Anda.
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

WIB = timezone(timedelta(hours=7))

# Path data & state
HIST_DIR = Path("/home/admin/warroom/data/hist")
STATE_FILE = Path("/home/admin/warroom/data/last_multi_market_signals.json")

# Parameter hasil tuning kuantitatif Break & Retest 15m
MARKETS_CONFIG = {
    "XAUUSD": {
        "market": "forex",
        "label": "Gold Spot (XAUUSD.x)",
        "lookback": 24,
        "retest_tol": 0.0025,
        "atr_mult": 1.25,
        "rr_target": 2.5,
        "lot_size": 0.10,
        "pip_mult": 10.0,
        "pf": 2.08,
        "est_risk": 70.0,
    },
    "BTCUSDT": {
        "market": "crypto",
        "label": "Bitcoin (BTC/USDT)",
        "lookback": 24,
        "retest_tol": 0.0025,
        "atr_mult": 1.50,
        "rr_target": 2.5,
        "lot_size": 0.01,
        "pip_mult": 1.0,
        "pf": 1.83,
        "est_risk": 35.0,
    },
    "SOLUSDT": {
        "market": "crypto",
        "label": "Solana (SOL/USDT)",
        "lookback": 36,
        "retest_tol": 0.0050,
        "atr_mult": 1.50,
        "rr_target": 2.0,
        "lot_size": 1.0,
        "pip_mult": 1.0,
        "pf": 1.70,
        "est_risk": 25.0,
    },
    "EURUSD": {
        "market": "forex",
        "label": "Euro / US Dollar (EUR/USD)",
        "lookback": 24,
        "retest_tol": 0.0015,
        "atr_mult": 1.25,
        "rr_target": 2.0,
        "lot_size": 0.20,
        "pip_mult": 10000.0,
        "pf": 1.58,
        "est_risk": 40.0,
    },
    "GBPUSD": {
        "market": "forex",
        "label": "British Pound / USD (GBP/USD)",
        "lookback": 36,
        "retest_tol": 0.0020,
        "atr_mult": 1.50,
        "rr_target": 2.0,
        "lot_size": 0.15,
        "pip_mult": 10000.0,
        "pf": 1.30,
        "est_risk": 45.0,
    }
}

NOTIFIER_ENV = Path("/etc/warroom/notifier.env")

def load_notifier_config():
    cfg = {}
    if NOTIFIER_ENV.exists():
        try:
            with open(NOTIFIER_ENV, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
        except PermissionError:
            pass
    return cfg

def send_telegram_alert(text: str) -> bool:
    cfg = load_notifier_config()
    token = cfg.get("WARROOM_TELEGRAM_BOT_TOKEN", "REDACTED_TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("WARROOM_TELEGRAM_CHAT_ID", "-1004383844873")
    thread_id = cfg.get("WARROOM_TELEGRAM_THREAD_ID", 237)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[ERR] Gagal kirim Telegram: {e}")
        return False

def format_signal_message(sig: dict) -> str:
    cfg = MARKETS_CONFIG.get(sig["symbol"], {})
    arah_emoji = "🟢 <b>BUY / LONG</b>" if sig["direction"] == "LONG" else "🔴 <b>SELL / SHORT</b>"
    wib_now = datetime.now(WIB).strftime("%d/%m/%Y %H:%M:%S WIB")
    pasar_tag = "FOREX & KOMODITAS" if cfg.get("market") == "forex" else "CRYPTO DERIVATIVES"

    dp = 2 if sig["symbol"] in ("XAUUSD", "BTCUSDT", "SOLUSDT") else 5

    msg = (
        f"🎯 <b>WAR ROOM — SINYAL {pasar_tag}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Instrument:</b> {cfg.get('label', sig['symbol'])}\n"
        f"• <b>Arah:</b> {arah_emoji}\n"
        f"• <b>Strategi:</b> Break & Retest 15m (Tuned PF {cfg.get('pf', 1.8):.2f})\n"
        f"• <b>Waktu:</b> {wib_now}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Rekomendasi Level Entri:</b>\n"
        f"• <b>Entri:</b> <code>{sig['entry']:.{dp}f}</code>\n"
        f"• <b>Stop Loss:</b> <code>{sig['sl']:.{dp}f}</code> ({sig['sl_dist']:.1f} pts)\n"
        f"• <b>Take Profit:</b> <code>{sig['tp']:.{dp}f}</code> ({sig['tp_dist']:.1f} pts)\n"
        f"• <b>Ukuran Order:</b> <b>{cfg.get('lot_size')} { 'Lot' if cfg.get('market') == 'forex' else 'Unit' }</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Risk Guard & Sizing:</b>\n"
        f"• Est. Toleransi Risiko: ~${cfg.get('est_risk', 50):.2f}\n"
        f"• Status Eksekusi: Eksekusi manual via Mobile App (TradeLocker / Exchange)."
    )
    return msg

def main():
    print(f"[{datetime.now(WIB).isoformat()}] Menjalankan multi-market scanner sinyal...")
    
    # Contoh simulasi pengiriman sinyal gabungan multi-market
    demo_signals = [
        {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry": 67450.00,
            "sl": 66950.00,
            "tp": 68700.00,
            "sl_dist": 500.0,
            "tp_dist": 1250.0
        },
        {
            "symbol": "EURUSD",
            "direction": "SHORT",
            "entry": 1.08250,
            "sl": 1.08450,
            "tp": 1.07850,
            "sl_dist": 20.0,
            "tp_dist": 40.0
        }
    ]

    for sig in demo_signals:
        txt = format_signal_message(sig)
        print("\n--- FORMAT PESAN ---")
        print(txt)
        if len(sys.argv) > 1 and sys.argv[1] == "--send":
            ok = send_telegram_alert(txt)
            print(f"Kirim {sig['symbol']} ke Telegram:", "BERHASIL" if ok else "GAGAL")

if __name__ == "__main__":
    main()
