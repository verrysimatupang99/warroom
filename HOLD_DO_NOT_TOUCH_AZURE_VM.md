# ⚠️ PERHATIAN PENTING — JANGAN SENTUH VM AZURE TRADER ⚠️

**Tanggal Catatan:** 31 Oktober 2026, 23:05 WIB  
**Instruksi Dari:** Verry Simatupang

---

## 🚫 ATURAN UTAMA
**DILARANG MERESTART, MEMATIKAN, MERUBAH KONFIGURASI, ATAU MEMATIKAN PROSES MT5 DI VM AZURE WINDOWS (`mt5-trader-vm2` / IP: `20.212.109.170`).**

---

## 📌 STATUS AKTIF SAAT INI
1. **VM Target:** `mt5-trader-vm2` (Resource Group: `FOREX-MT5-RG`)
2. **Akun Trading Aktif:**
   - **Broker:** Vantage Markets Live 21
   - **Nomor Akun:** `36525553` (Cent ECN, modal 2,000 USC)
   - **Chart & Pair:** `BTCUSD.sc` pada Timeframe **H1**
3. **Robot / EA:**
   - **EA:** `Fomofx_Satrion_BTC_v1.00 36525553.ex5`
   - **Preset:** `Satrion BTC Fix lot.set` (Breakout & Pulsar 0.01 lot)
   - **Status Eksekusi:** **LIVE 24/7** dengan 5 pending order aktif (Breakout Trap).
   - **Algo Trading:** **ON / HIJAU**

---

## 🛑 LARANGAN TINDAKAN UNTUK AGENT / CRON / AUTOMATION DI WEBDOCK:
- Jangan jalankan Azure CLI (`az vm restart`, `az vm stop`, `az vm run-command`) yang menargetkan `mt5-trader-vm2`.
- Jangan utak-atik proses `terminal64.exe` di VM Windows tersebut.
- Jangan pasang atau timpa EA lain di chart `BTCUSD.sc`.
- Biarkan EA FomoFX Satrion BTC berjalan menguji pasar secara mandiri (*let it cook*).

---
*Catatan ini dibuat otomatis dan ditaruh di root home Webdock (`/home/admin`) agar semua agen, sub-agen, dan sesi otomatis memperhatikan instruksi ini.*
