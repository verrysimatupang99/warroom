# Runbook Operasional Sistem — War Room 24/7

Dokumen ini merupakan panduan operasional resmi bagi tim SRE (Site Reliability Engineering), DevOps, dan System Operator untuk pemeliharaan, pemantauan, dan penanganan insiden pada platform **War Room**.

---

## 1. Topologi Infrastruktur & Batasan Host

Sistem War Room beroperasi pada infrastruktur terdistribusi yang terdiri atas dua host aktif. Sesuai direktif Product Owner per 12 November 2026, host warisan Azure VM2 telah dinonaktifkan secara permanen.

```
+-----------------------------------------------------------------------------------+
|                              ARSITEKTUR HOST AKTIF                                |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Host 1: Webdock Cloud ]                                                        |
|  Hostname : polywarroom.vps.webdock.cloud                                         |
|  Akses    : ssh admin@polywarroom.vps.webdock.cloud (atau ~/bin/ssh-poly)           |
|  Fungsi   : Core Production Services & Web Dashboard                              |
|  Layanan  : - Nginx Reverse Proxy (TLS 443 / HTTP 80)                             |
|             - warroom-web.service (SvelteKit SSR, Port :3100)                     |
|             - warroom-api.service (FastAPI REST & SSE, Port :8800)                |
|             - trading-engine.service (Telegram Signals, Port :8088)               |
|             - warroom-worker.service (Scheduled Ingestion & Freshness)            |
|             - postgresql@16-main.service (PostgreSQL 16, Port :5432)              |
|                                                                                   |
|                                    ^                                              |
|                                    | HTTPS Telemetri (Port 443)                   |
|                                    | Header: X-Warroom-Token                      |
|                                    | Interval: 5 Detik                            |
|                                    v                                              |
|                                                                                   |
|  [ Host 2: Instabox VM ]                                                          |
|  ID Host  : box-2aacb3                                                            |
|  Akses    : boxd ssh box-2aacb3 (atau SSH via Instabox gateway)                   |
|  Fungsi   : MT5 Real Cent Runner (Akun 452009427 @ Exness-MT5Real48)              |
|  Layanan  : - mt5-reaper.service (Wine MetaTrader 5 + EA GOLD_Reaper_Hexa)        |
|             - Skrip Pemulihan: /data/home/warroom-telemetry-ensure.sh             |
|                                                                                   |
+-----------------------------------------------------------------------------------+
|  [ HOST NONAKTIF / DECOMMISSIONED ]                                               |
|  Host     : Azure VM2 (Akun lama 36525553)                                        |
|  Status   : DECOMMISSIONED & DIISOLASI TOTAL                                      |
|  Aturan   : DILARANG KERAS dinyalakan, di-restart, atau dihubungkan kembali.          |
|             Backend War Room secara otomatis memblokir dispatch ke host ini.      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Inventaris Layanan Systemd & Alokasi Port

### 2.1. Webdock Cloud Services (`polywarroom`)

| Nama Service Unit | Deskripsi Layanan | Port Internal | Working Directory | Perintah Utama |
|---|---|---|---|---|
| `warroom-web.service` | UI SvelteKit (Node.js SSR) | `127.0.0.1:3100` | `/home/admin/warroom/apps/web` | `node build/index.js` |
| `warroom-api.service` | Backend Core & SSE Engine | `127.0.0.1:8800` | `/home/admin/warroom` | `uvicorn warroom_api.app:app` |
| `trading-engine.service` | Telegram Listener & API | `127.0.0.1:8088` | `/home/admin/tg-trading-engine` | `uvicorn api:app` & `engine.py` |
| `warroom-worker.service` | Worker kalkulasi latar belakang | - | `/home/admin/warroom` | `python -m warroom_worker.run --every 30` |
| `postgresql@16-main.service` | Database Utama PostgreSQL 16 | `127.0.0.1:5432` | `/var/lib/postgresql/16/main` | Postgres daemon |
| `nginx.service` | Edge TLS Proxy & Static Router | `:80, :443` | `/etc/nginx` | Nginx master process |

### 2.2. Instabox VM Services (`box-2aacb3`)

| Nama Service / Komponen | Deskripsi Layanan | Target Akun / Path | Parameter Runtime |
|---|---|---|---|
| `mt5-reaper.service` | Wine MT5 Cent Execution Engine | Exness `452009427` (USC) | EA `GOLD_Reaper_Hexa.ex5` |
| `warroom-telemetry-ensure.sh` | Health check & WebRequest allowlist guard | `/data/home/warroom-telemetry-ensure.sh` | Loop via cron / startup guard |
| `MQL5/Files/warroom_debug.txt` | File log status pengiriman telemetri | Instabox MT5 sandbox | Mencatat status HTTP 200 / error |

---

## 3. Kebijakan Kredensial & Pengelolaan Rahasia (Zero Secrets Policy)

Dilarang keras menyimpan token, kata sandi, API key, atau kredensial apa pun di dalam repositori kode git atau dokumen publik.

### 3.1. Lokasi Berkas Environment di Server

Seluruh kredensial tersimpan dalam direktori `/etc/warroom/` di Webdock Cloud dengan hak akses ketat:

```bash
# Struktur direktori rahasia pada Webdock Cloud
-rw------- 1 root  root   /etc/warroom/db.env             # URL PostgreSQL (WARROOM_DB_URL)
-rw------- 1 root  root   /etc/warroom/llm.env            # Kunci AI/LLM & Flag WARROOM_LAYA_INFERENSI
-rw------- 1 root  root   /etc/warroom/notifier.env       # Token Notifier Telegram Bot
-rw------- 1 root  root   /etc/warroom/service_token.env  # X-Warroom-Token untuk autentikasi MT5
-rw-r----- 1 root  admin  /etc/warroom/tg-engine.env       # TG_API_ID dan TG_API_HASH
```

### 3.2. Token Telemetri di Instabox VM

Pada Instabox VM (`box-2aacb3`), modul telemetri MT5 membaca token dari berkas lokal yang diisolasi:
- **Lokasi**: `/data/home/.../MQL5/Files/warroom_token.txt`
- **Izin Berkas**: `chmod 600 warroom_token.txt` (Hanya terbaca oleh akun runner Wine)

---

## 4. Prosedur Rutinitas Harian Operator

### 4.1. Morning Health Check (07:00 WIB / 00:00 UTC)

1. **Pemeriksaan Status Layanan Webdock**:
   ```bash
   ssh admin@polywarroom.vps.webdock.cloud
   systemctl is-active warroom-web warroom-api warroom-worker trading-engine postgresql@16-main nginx
   ```
   *Ekspektasi*: Semua unit mengembalikan output `active`.

2. **Verifikasi Aliran Telemetri SSE**:
   ```bash
   curl -s -N -H "Accept: text/event-stream" "http://127.0.0.1:8800/api/v1/tencent/forex/stream?account=452009427" | head -n 5
   ```
   *Ekspektasi*: Menerima baris `retry: 3000` dan snapshot data JSON akun `452009427` dengan `connected: true`.

3. **Verifikasi Keberhasilan Backup Harian**:
   ```bash
   ls -lt /var/backups/postgresql/warroom-*.dump | head -n 3
   systemctl status warroom-backup-postgres.timer
   ```
   *Ekspektasi*: Terdapat file dump terbaru dari jadwal 00:40 UTC beserta checksum `.sha256`.

### 4.2. Log Inspection & Troubleshooting Commands

- **Melihat log API secara real-time**:
  ```bash
  journalctl -u warroom-api.service -f -n 100 --no-pager
  ```
- **Melihat log UI SvelteKit**:
  ```bash
  journalctl -u warroom-web.service -f -n 50 --no-pager
  ```
- **Melihat log Telegram Signal Engine**:
  ```bash
  journalctl -u trading-engine.service -f -n 100 --no-pager
  ```
- **Melihat log akses Nginx untuk endpoint telemetri**:
  ```bash
  tail -f /var/www/logs/access.log | grep "/api/v1/tencent"
  ```
- **Pemeriksaan log telemetri MT5 di Instabox**:
  ```bash
  ssh box-2aacb3
  tail -n 20 /data/home/.../MQL5/Files/warroom_debug.txt
  # Output normal: "push: OK http=200 ok#1284" tiap 5 detik
  ```

---

## 5. Prosedur Restart & Siklus Hidup Layanan

Jika diperlukan restart layanan (misalnya pasca pembaruan kode atau konfigurasi), ikuti urutan dependensi yang benar:

### 5.1. Urutan Restart Graceful

```bash
# 1. Pastikan database PostgreSQL dalam kondisi sehat
sudo systemctl status postgresql@16-main

# 2. Restart backend API (akan menjalankan skrip ExecStartPre check-db-head.py --upgrade)
sudo systemctl restart warroom-api

# 3. Restart worker latar belakang
sudo systemctl restart warroom-worker

# 4. Restart web frontend SvelteKit
sudo systemctl restart warroom-web

# 5. Restart trading signal engine (jika diperlukan)
sudo systemctl restart trading-engine
```

### 5.2. Pre-start Schema Guard

Layanan `warroom-api.service` dikonfigurasi dengan:
```ini
Environment=CHECK_DB_HEAD_REQUIRED=1
ExecStartPre=/home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/check-db-head.py --upgrade
```
Ini memastikan bahwa proses API tidak akan menyala apabila migrasi Alembic database belum mencapai versi revisi `head` terkini.

---

## 6. Prosedur Backup & Verifikasi Checksum Harian

### 6.1. Timer & Skrip Backup

Backup otomatis dikelola oleh systemd timer `warroom-backup-postgres.timer` yang berjalan setiap hari pukul **00:40:00 UTC**.

- **Unit Service**: `warroom-backup-postgres.service`
- **Eksekutor**: `/home/admin/warroom/ops/backup-postgres.sh`
- **Direktori Output**: `/var/backups/postgresql/` (atau `/home/admin/backups/postgres/`)
- **Kebijakan Retensi**: Menyimpan 14 dump terakhir; dump lama dan berkas `.part` yang gagal dibersihkan secara otomatis.

### 6.2. Verifikasi Integritas SHA-256

Setiap file `.dump` disertai dengan file pasangan `.sha256` dengan path relatif. Untuk memverifikasi keutuhan dump sebelum dipindahkan atau digunakan untuk restore:

```bash
cd /var/backups/postgresql/
# Verifikasi dump terbaru
LATEST_DUMP=$(ls -1t warroom-*.dump | head -n 1)
sha256sum -c "${LATEST_DUMP}.sha256"
```
*Output yang diharapkan*: `warroom-20261112-004000.dump: OK`

---

## 7. Matriks Penanganan Insiden (Incident Response Matrix)

### Kasus 1: Telemetri Instabox MT5 Terputus (`connected: false` / Stale > 15s)

| Gejala | Dashboard Forex Cockpit menampilkan status "TERPUTUS" atau harga tidak bergerak > 15 detik. |
|---|---|
| **Akar Masalah Potensial** | 1. MT5 Wine crash di Instabox.<br>2. MT5 menghapus allowlist URL WebRequest pasca restart (Error 4014).<br>3. Token kadaluarsa atau koneksi internet Instabox terganggu. |
| **Langkah Diagnosa** | 1. Cek log Nginx di Webdock: `grep "/api/v1/tencent/mt5/telemetry" /var/www/logs/access.log | tail -n 10`<br>2. SSH ke Instabox: `tail -n 20 MQL5/Files/warroom_debug.txt` |
| **Langkah Pemulihan** | 1. Di Instabox, jalankan skrip pemulihan otomatis:<br>`/data/home/warroom-telemetry-ensure.sh`<br>Skrip ini akan menyalakan MT5 (bila mati) dan menginjeksikan kembali allowlist WebRequest URL via xdotool.<br>2. Verifikasi status:<br>`/data/home/warroom-telemetry-ensure.sh --check`<br>3. Pantau log telemetri di Webdock kembali menerima respons HTTP 200. |

---

### Kasus 2: SSE Stream Terputus / Reconnection Loop pada Browser

| Gejala | Browser terus-menerus melakukan re-handshake SSE atau indikator Forex Cockpit berkedip setiap 3 detik. |
|---|---|
| **Akar Masalah Potensial** | 1. Nginx proxy buffering memotong koneksi chunked.<br>2. Sesi login admin (`wr_session`) berakhir.<br>3. Endpoint stream API mengalami unhandled exception. |
| **Langkah Diagnosa** | 1. Cek curl langsung ke port internal API:<br>`curl -i -N "http://127.0.0.1:8800/api/v1/tencent/forex/stream?account=452009427"`<br>2. Cek apakah terdapat log error pada API: `journalctl -u warroom-api -n 50` |
| **Langkah Pemulihan** | 1. Pastikan Nginx memiliki konfigurasi SSE berikut:<br>`proxy_buffering off;`<br>`proxy_cache off;`<br>`proxy_read_timeout 3600s;`<br>`proxy_set_header Connection '';`<br>2. Pastikan API mengembalikan header `retry: 3000\n\n` dan heartbeat `: ping\n\n` setiap 15 detik.<br>3. Restart layanan web dan API jika socket hang: `sudo systemctl restart warroom-api warroom-web`. |

---

### Kasus 3: Sinyal Telegram Mengalami Drop atau Parser Macet

| Gejala | Pesan sinyal baru muncul di channel Telegram target tetapi kartu sinyal pada dashboard War Room tidak bertambah. |
|---|---|
| **Akar Masalah Potensial** | 1. Sesi Telethon invalid atau disconnect.<br>2. Lock database SQLite `trading_signals.db` oleh proses konkuren.<br>3. Format sinyal mengandung keyword baru yang tidak dikenali parser. |
| **Langkah Diagnosa** | 1. Periksa unit `trading-engine.service`: `journalctl -u trading-engine -n 100`<br>2. Periksa apakah session file terbaca: `ls -la /home/admin/tg-trading-engine/trading_session.session`<br>3. Cek database SQLite: `sqlite3 /home/admin/tg-trading-engine/trading_signals.db "SELECT count(*), max(timestamp) FROM signals;"` |
| **Langkah Pemulihan** | 1. Jika Telethon disconnect: `sudo systemctl restart trading-engine`.<br>2. Jika terdapat keyword baru: verifikasi penambahan di `services/tg-engine/parser.py` (`FOREX_KEYWORDS`, regex GOLD BUY/SELL tanpa prefiks).<br>3. Pastikan environment `/etc/warroom/tg-engine.env` memuat `TG_API_ID` dan `TG_API_HASH` yang valid. |

---

### Kasus 4: Kegagalan Inferensi AI / LLM Timeout

| Gejala | Sinyal masuk tetapi tertahan pada status antrean analisis atau log menunjukkan timeout ke penyedia LLM eksternal. |
|---|---|
| **Akar Masalah Potensial** | Layanan eksternal AI mengalami latensi tinggi, pemadaman, atau kehabisan kuota API. |
| **Langkah Mitigasi** | **Fallback ke Pure Technical Mode**:<br>1. War Room secara arsitektural menetapkan baseline operasional pada mode teknis murni (`WARROOM_LAYA_INFERENSI=0`).<br>2. Dalam mode ini, strategi `MultiSessionLayaScalperStrategy` secara otomatis mengevaluasi aturan jendela sesi teknis, rasio Risk-Reward (RRR $\ge 1.6$), dan batasan Stop Loss tanpa memblokir sinyal karena ketiadaan verdict AI.<br>3. Untuk mematikan inferensi AI manual: ubah `WARROOM_LAYA_INFERENSI=0` di `/etc/warroom/llm.env` lalu reload service: `sudo systemctl restart warroom-worker warroom-api`. |

---

## 8. Kontak Eskalasi & Roster SRE On-Call

| Peran | Kontak / Kanal Eskalasi | Tanggung Jawab Utama |
|---|---|---|
| **SRE Lead / On-Call Primary** | Telegram War Room Ops / PagerDuty | Insiden down host Webdock, Nginx, Database restore |
| **Backend / Trading Lead** | Kanal Dev Internal | Logika deal MT5, Cent conversion, Engine parser |
| **Instabox / EA Specialist** | Kanal Instabox Ops | Status Wine MT5 `box-2aacb3`, koneksi Exness broker |
| **Product Owner** | Telepon Darurat / Escalation Group | Keputusan Go/No-Go rilis, keputusan rollback total |
