# 📌 PETUNJUK TEKNIS IMPLEMENTASI: TELEGRAM TRADING SIGNALS ENGINE 24/7
**Target:** AI Coding Agent / Engineer di Webdock Server (`polywarroom`)  
**Lokasi Project:** `/home/admin/tg-trading-engine`  
**Status Sesi Telegram:** ✅ **AUTHENTICATED & READY** (File sesi sudah terpasang)

---

## 1. 🔑 Kredensial & Autentikasi (PENTING)
Akun Telegram (`Sasc / +6285754257413`) sudah diautentikasi resmi. **DILARANG MENGHAPUS / OVERWRITE** file sesi yang ada di direktori ini!

* **Direktori:** `/home/admin/tg-trading-engine/`
* **File Sesi:** `trading_session.session` *(sudah ada dan valid)*
* **API ID:** `33505349`
* **API HASH:** `ea452b7e3d112a9c3f418d5bf6fb4d71`

---

## 2. 🎯 Tujuan & Scope Pekerjaan Agent di Webdock
Agent diinstruksikan untuk menyelesaikan 3 modul:

### A. Modul 1: Listener Real-Time 24/7 (`engine.py`)
* Menggunakan library `telethon`.
* Membaca event pesan baru (`@client.on(events.NewMessage)`).
* Memfilter pesan dari channel/grup target:
  - **Forex / Gold (XAUUSD):** Callisto FX (`@callistofx`), DIO Gold Hunter, Trader Ndeso, dll.
  - **Saham Indo (IHSG):** Stockbit, Creative Trader Channel, Bandarsub, Saham untuk Rakyat, IPOT, Ajaib Sekuritas.
  - **Crypto:** Timothy Ronald Akademi Crypto, Airdrop Detective, Messari, dll.
* Menyimpan setiap pesan baru secara otomatis ke database SQLite: `/home/admin/tg-trading-engine/trading_signals.db`.

### B. Modul 2: REST API & Web Dashboard (`api.py`)
* Menggunakan `FastAPI` + `uvicorn`.
* Endpoint API:
  - `GET /api/signals?limit=50&category=FOREX|SAHAM|CRYPTO`: Mengembalikan JSON sinyal terbaru.
  - `GET /`: Dashboard web responsive (Tailwind CSS) yang menampilkan kartu sinyal real-time dengan auto-refresh 15 detik.
* Port default yang disarankan: `:8088` atau `:8888` (hindari bentrok dengan port 9router `20128/20129/8801`).

### C. Modul 3: Systemd Daemon (`trading-engine.service`)
* Pasang service systemd agar engine berjalan otomatis di latar belakang dan restart jika server reboot.

---

## 3. 🛠️ Skema Database SQLite (`trading_signals.db`)
```sql
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT,
    channel_name TEXT,
    category TEXT,            -- 'FOREX', 'SAHAM', 'CRYPTO', 'GENERAL'
    message_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    views INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    raw_metadata TEXT
);
```

---

## 4. 🚀 Quickstart Command untuk Agent
```bash
cd /home/admin/tg-trading-engine

# 1. Setup Virtualenv & Dependencies
python3 -m venv venv
source venv/bin/activate
pip install telethon fastapi uvicorn pydantic

# 2. Verifikasi Koneksi Sesi (Tanpa Minta OTP)
python3 -c "
import asyncio
from telethon import TelegramClient

async def check():
    client = TelegramClient('trading_session', 33505349, 'ea452b7e3d112a9c3f418d5bf6fb4d71')
    await client.connect()
    me = await client.get_me()
    print('SESI VALID:', me.first_name, f'(@{me.username}) ID: {me.id}')
    await client.disconnect()

asyncio.run(check())
"
```

---

## 5. 🔔 Integrasi AI Signal Parser (Opsional / Tahap Lanjutan)
Jika diperlukan rangkuman otomatis atau pemisahan sinyal (*Entry, TP, SL*), agent dapat menghubungkan handler ke endpoint AI internal lokal di `http://127.0.0.1:20129/v1` (Model: `overchat/claude-haiku-4-5-landing`) yang sudah terpasang di server ini.
