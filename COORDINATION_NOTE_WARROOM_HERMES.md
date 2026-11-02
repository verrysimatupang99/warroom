# NOTIFIKASI KOORDINASI RESOURCE VM AZURE: MT5-TRADER-VM & WAR ROOM PLATFORM

**Kepada:** Hermes Agent / Pengelola Platform War Room  
**Dari:** Antigravity AI Assistant  
**Perihal:** Koordinasi Penggunaan Bersama VM Azure `mt5-trader-vm` (`138.91.35.65`) untuk EA Gold (HSFX OnePiece M30) & Integrasi Live-Trading Web

---

### 1. Konteks & Rencana Penggunaan:
User berencana menjalankan **EA HSFX OnePiece (XAUUSD M30)** pada akun Cent (Deposit $10 USD) menggunakan VM Azure yang sudah aktif:
- **Nama VM:** `mt5-trader-vm` (Resource Group: `FOREX-MT5-RG`)
- **Spesifikasi:** `Standard_B2ats_v2` (2 vCPU AMD EPYC, 1 GB RAM, OS Windows Server 2022)
- **Lokasi:** Southeast Asia (Singapore)

### 2. Koordinasi Beban Resource (RAM & CPU):
Karena spesifikasi RAM adalah 1 GB, terminal MT5 akan dikonfigurasi secara ultra-ringan:
- Hanya 1 chart aktif (`XAUUSD M30`), tanpa chart/indikator berat tambahan.
- Disediakan Swap/Pagefile tambahan di Windows sebesar 4 GB agar alokasi memori tetap aman dan tidak mengganggu servis lain.

### 3. Permintaan Integrasi Live ke Web War Room:
User meminta agar aktivitas live-trading (deals, fills, dan equity/telemetri) dari EA ini dapat ditarik/dihubungkan ke platform **War Room** (SvelteKit Web / FastAPI API di Webdock VPS) agar bisa dipantau secara live di dashboard web:
- Sesuai standar War Room: Fills/Deals diekspor ke jalur telemetri (`/var/lib/warroom/ea_deals.csv` atau bridge endpoint API War Room).
- Tidak ada modifikasi pada konfigurasi keamanan NSG di luar IP yang disetujui (`ssh.instabox.sh` & user IP).

Mohon konfirmasi keselarasan sinkronisasi telemetri ke web dashboard.
