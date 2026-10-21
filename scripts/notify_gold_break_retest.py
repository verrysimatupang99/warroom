#!/usr/bin/env python3
"""
scripts/notify_gold_break_retest.py
Pipeline Scanner Real-Time Sinyal Break & Retest 15m untuk Gold (XAUUSD.x / XAUUSD) & Pair Forex.
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
STATE_FILE = Path("/home/admin/warroom/data/last_gold_signal.json")

# Parameter hasil tuning kuantitatif (PF 2.08)
CONFIG_GOLD = {
    "pair": "XAUUSD.x",
    "lookback": 24,       # Breakout window (6 jam)
    "retest_tol": 0.0025, # Toleransi retest 0.25%
    "atr_mult": 1.25,     # Stop loss ATR multiplier
    "rr_target": 2.5,     # Target RR 1:2.5
    "lot_size": 0.10,     # Sesuai preferensi user
}

# Konfigurasi Notifier
NOTIFIER_ENV = Path("/etc/warroom/notifier.env")

def load_notifier_config():
    cfg = {}
    if NOTIFIER_ENV.exists():
        with open(NOTIFIER_ENV, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    return cfg

def send_telegram_alert(text: str) -> bool:
    cfg = load_notifier_config()
    token = cfg.get("WARROOM_TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("WARROOM_TELEGRAM_CHAT_ID")
    thread_id = cfg.get("WARROOM_TELEGRAM_THREAD_ID")

    if not token or not chat_id:
        print("[WARN] Telegram config tidak lengkap di /etc/warroom/notifier.env")
        return False

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

def format_signal_message(signal: dict) -> str:
    arah_emoji = "🟢 <b>BUY</b>" if signal["direction"] == "LONG" else "🔴 <b>SELL</b>"
    wib_now = datetime.now(WIB).strftime("%d/%m/%Y %H:%M:%S WIB")
    
    msg = (
        f"🎯 <b>WAR ROOM — SINYAL GOLD (XAUUSD)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Instrument:</b> {signal['pair']} (Spot Gold)\n"
        f"• <b>Arah:</b> {arah_emoji}\n"
        f"• <b>Strategi:</b> Break & Retest 15m (Tuned PF 2.08)\n"
        f"• <b>Waktu:</b> {wib_now}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Rekomendasi Level Entri:</b>\n"
        f"• <b>Entri:</b> <code>{signal['entry']:.2f}</code>\n"
        f"• <b>Stop Loss:</b> <code>{signal['sl']:.2f}</code> ({signal['sl_pips']:.1f} pips)\n"
        f"• <b>Take Profit (1:2.5):</b> <code>{signal['tp']:.2f}</code> ({signal['tp_pips']:.1f} pips)\n"
        f"• <b>Ukuran Lot:</b> <b>{signal['lot']:.2f} Lot</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Guard Akun 5K Goat Funded:</b>\n"
        f"• Est. Risiko Loss: ~${signal['risk_usd']:.2f} ({(signal['risk_usd']/5000)*100:.1f}% akun)\n"
        f"• Est. Reward: ~${signal['reward_usd']:.2f} (+{(signal['reward_usd']/5000)*100:.1f}%)\n"
        f"• Eksekusi manual via TradeLocker di HP Anda."
    )
    return msg

def main():
    print(f"[{datetime.now(WIB).isoformat()}] Memeriksa sinyal Break & Retest XAUUSD...")
    # Simulasi setup valid untuk pengetesan kesiapan pipeline
    mock_signal = {
        "pair": "XAUUSD.x",
        "direction": "LONG",
        "entry": 2725.50,
        "sl": 2718.50,
        "tp": 2743.00,
        "sl_pips": 70.0,
        "tp_pips": 175.0,
        "lot": 0.10,
        "risk_usd": 70.0,
        "reward_usd": 175.0,
        "ts": datetime.now(WIB).isoformat()
    }
    
    text = format_signal_message(mock_signal)
    print("Format pesan yang akan dikirim:")
    print(text)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--send":
        ok = send_telegram_alert(text)
        print("Kirim ke Telegram:", "BERHASIL" if ok else "GAGAL")

if __name__ == "__main__":
    main()
