# LP Agent (docs.lpagent.io): Riset Open API, Paket Lifetime, & Rencana Integrasi War Room

Tanggal: 2026-10-10  
Penulis: Antigravity (Pair Programming Agent)  
Ditujukan untuk: Owner & OpenClaw / Hermes (War Room Core Team)  
Status: **DOKUMEN RISET & REKOMENDASI ARSITEKTUR**

---

## 1. Ringkasan Eksekutif (Koreksi Temuan Sebelumnya)

Pada dokumen [docs/belajar/gelombang3-eksekusi-dan-lpagent-2026-10-10.md](file:///home/admin/warroom/docs/belajar/gelombang3-eksekusi-dan-lpagent-2026-10-10.md#L44-L61), tim sebelumnya mengamati aplikasi web LP Agent (`app.lpagent.io`) dan mencatat kesimpulan:
> *"API publik: Tidak ada yang terbuka (semua di balik app + Turnstile)... jadi tidak bisa dijadikan sumber data otomatis tanpa kerja sama mereka."*

**Koreksi:** Temuan tersebut belum mencakup portal developer mereka. Dokumentasi resmi di [docs.lpagent.io](https://docs.lpagent.io) dan portal API di [portal.lpagent.io](https://portal.lpagent.io) membuktikan bahwa **LP Agent memiliki Official Open API** lengkap dengan skema OpenAPI 3.0, spesifikasi machine-readable untuk AI agent (`llms.txt`), serta skema langganan API key resmi.

Owner memutuskan akan mengambil tier **Basic ($10 Lifetime)** untuk keperluan riset dan mencari peluang profit (*cuan*) dari likuiditas Solana (Meteora DLMM & DAMM V2) serta Robinhood Chain. Dokumen ini merangkum arsitektur, batasan rate limit, serta panduan teknis bagi OpenClaw untuk mengintegrasikannya ke sistem War Room secara aman dan terukur.

---

## 2. Struktur Paket & Pricing API Key

Berdasarkan dokumentasi resmi di `/api-key-dashboard/dashboard`:

| Tier | Harga | Rate Limit | Cakupan Endpoint | Keterangan |
|---|---|---|---|---|
| **Basic** *(Rencana Owner)* | **$10 Lifetime** (sekali bayar) | **5 RPM** (Requests Per Minute) | Limited / Standard API Endpoints | Sangat murah untuk telemetri berkala & riset. |
| **Premium** | $20 / bulan | 10 RPM | Premium API Endpoints | Skala menengah. |
| **Enterprise** | $40 / bulan | 20 RPM | High-volume API Endpoints | Skala institusi/bot frekuensi tinggi. |

### Implikasi Batasan 5 RPM (Tier Basic):
- **1 request per 12 detik**.
- **Larangan Keras:** Jangan pernah menembak API ini secara langsung (*direct on-demand*) dari UI frontend War Room. Satu kali refresh halaman oleh user bisa langsung menghabiskan kuota 5 RPM dan memicu error `429 Too Many Requests`.
- **Solusi Arsitektur:** Gunakan **Pola Worker Snapshotting**. Worker War Room mengambil snapshot berkala (misal: tiap 15–30 menit), menyimpan hasilnya ke cache lokal (`/var/lib/warroom/lpagent-snapshot.json` atau SQLite), dan UI hanya membaca cache lokal tersebut.

---

## 3. Fitur & Kapabilitas Endpoint LP Agent

LP Agent memposisikan diri sebagai terminal likuiditas multi-chain yang berfokus pada protokol penghasil yield fee likuiditas:

### A. Jaringan & Protokol yang Didukung
1. **Solana (`SOL`):**
   - **Meteora DLMM** (Dynamic Liquidity Market Maker — concentrated liquidity per-bin).
   - **Meteora DAMM V2** (Dynamic Automated Market Maker V2).
2. **Robinhood Chain (`ROBINHOOD`):**
   - **Uniswap V3 & Uniswap V4** (Arbitrum Orbit L2, Chain ID 4663).

### B. Endpoint Kategori Data & Analitika (Telemetry)
- **`GET /api/v1/pools` (Discover Pools):**
  - Filter pool berdasarkan chain, volume, fee APR, dan TVL.
  - Sangat berguna untuk mendeteksi pool mana yang sedang mengalami lonjakan volume transaksi (fee farming).
- **`GET /api/v1/pools/{address}` & `GET /api/v1/pools/{address}/onchain-statistics`:**
  - Statistik on-chain mendalam: jumlah posisi terbuka, total modal masuk, rasio token, dan unique users.
- **`GET /api/v1/pools/{address}/top-lpers` (Top Liquidity Providers):**
  - Menampilkan ranking LPer paling sukses pada pool tersebut.
  - **Potensi Edge War Room:** Melacak strategi range/bin yang dipasang oleh *smart liquidity provider* untuk ditiru atau dianalisis perilakunya.
- **`GET /api/v1/positions/opening` & `GET /api/v1/positions/historical`:**
  - Melacak status posisi LP dan riwayat PnL/revenue (rentang 7D dan 1M) milik wallet tertentu.

### C. Endpoint Eksekusi & Manajemen On-Chain (Transaction Building)
- **`POST /api/v1/pools/zap-in`:**
  - Menghasilkan serialised transaksi untuk masuk ke pool likuiditas langsung dari SOL murni (auto-swap ke rasio pasangan token yang pas).
  - Submit transaksi via **Jito Block Engine bundles** (`/api/v1/pools/zap-in/submit`) untuk jaminan landing tanpa kena front-running/MEV sandwich.
- **`POST /api/v1/position/zap-out`:**
  - Mengambil quote dan menghasilkan transaksi withdraw likuiditas kembali menjadi SOL murni, juga dikirim via Jito bundle.
- **`POST /api/v1/position/claim-fees`:**
  - Otomatis klaim akumulasi fee dari posisi DLMM/DAMM v2 dan menukar fee tersebut ke SOL (compounding).

### D. Fitur Ramah AI Agent
- Dokumentasi menyediakan entry-point khusus AI: `https://docs.lpagent.io/llms.txt`.
- Panduan integrasi AI: `https://docs.lpagent.io/ai-api-guide.md`.
- File OpenAPI lengkap: `https://docs.lpagent.io/api-reference/openapi.json`.

---

## 4. Evaluasi Keselarasan dengan Standar Kerja War Room

War Room dibangun dengan pakem ketat:
1. **Catatan Kejujuran Wajib:** Setiap angka harus jelas statusnya: terukur vs belum terverifikasi.
2. **Paper Trade Dulu 1:1:** Tidak ada uang riil yang dipertaruhkan sebelum sistem paper trade membuktikan ekspektansi positif.
3. **Gerbang Live Terkunci (`armed=false`):** Tidak boleh ada eksekusi wallet otomatis tanpa otorisasi bertahap.

### Bagaimana LP Agent Masuk ke War Room?

```
┌─────────────────────────────────────────────────────────────────┐
│                     LP Agent API ($10 Lifetime)                 │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Polling tiap 15m (max 5 RPM)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│             War Room Worker (warroom_worker/adapters)           │
│  - Ambil top pool Meteora DLMM & DAMM v2                        │
│  - Ambil wallet Top LPers                                       │
│  - Tulis cache ke /var/lib/warroom/lp-meteora.json              │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               War Room Simulator (Paper LP Tracker)             │
│  - Simulasikan posisi virtual di pool terpilih                  │
│  - Hitung Estimasi Fee Reward vs Impermanent Loss               │
│  - Catat Ekspektansi & PnL secara jujur (tanpa uang riil)       │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Dashboard War Room (/crypto atau /lp)          │
│  - Kartu sinyal LP: Pool terbaik hari ini                       │
│  - Catatan kejujuran: Sumber data LP Agent API (5 RPM cache)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Rencana Aksi Teknis untuk OpenClaw (Implementation Roadmap)

Setelah Owner membeli API key di `portal.lpagent.io` dan menyimpannya di server, berikut panduan langkah teknis yang direkomendasikan untuk OpenClaw:

### Tahap 1: Penyimpanan Credential
- Simpan API key di environment file aman:
  ```bash
  # Di /home/admin/warroom/.env (atau systemd environment)
  LPAGENT_API_KEY="lp_live_xxxxxxxxxxxxxxxx"
  LPAGENT_BASE_URL="https://api.lpagent.io/v1"
  ```
- Pastikan masuk ke `.gitignore` dan terverifikasi oleh pre-commit hook `.gitleaks.toml`.

### Tahap 2: Pembuatan Adapter Worker (`warroom_worker/adapters/lpagent.py`)
Buat class client sederhana dengan *rate-limit guard*:
- Menggunakan `httpx` async client.
- Pasang mekanisme throttling: jeda minimal 12–15 detik antar panggilan jika ada request berurutan, atau gunakan token-bucket limiter (5 token/menit).
- Tangani status `429`: jika terkena rate-limit, backoff minimal 60 detik tanpa membuat worker crash.
- Ambil endpoints esensial:
  1. `get_top_pools(chain="SOL", platform="meteora")`
  2. `get_top_lpers(pool_address)`

### Tahap 3: Integrasi Data ke Worker Snapshotting
- Daftarkan job baru di `services/worker/src/warroom_worker/jobs.py`:
  - Interval eksekusi: setiap 20 atau 30 menit sekali (misal: di menit ke-10 dan ke-40).
  - Simpan payload hasil olahan ke file snapshot atau database War Room.
  - Masukkan `catatan_kejujuran`:
    ```json
    {
      "sumber": "LP Agent Open API (Meteora DLMM/DAMM v2)",
      "frekuensi_snapshot": "30 menit",
      "status_verifikasi": "terukur via API pihak ketiga",
      "armed": false
    }
    ```

### Tahap 4: Paper Trade Tracker (Mencari Edge / Cuan)
- Sebelum menyentuh transaksi riil (Zap-in Jito), buat modul evaluasi paper:
  - Pantau 3 pool Meteora dengan Fee/TVL ratio tertinggi selama 7 hari berturut-turut.
  - Catat apakah fee harian yang dihasilkan benar-benar menutup risiko volatilitas harga token (Impermanent Loss).
  - Jika rasio Fee > IL secara konsisten dengan ekspektansi > +0,3R, barulah formulasikan SOP eksekusi live.

---

## 6. Kesimpulan & Rekomendasi Akhir

1. **Langkah Tepat:** Keputusan owner mengambil plan **$10 Lifetime** sangat rasional — biaya kecil, tanpa beban langganan bulanan (*zero burn rate*), dan membuka akses ke API data likuiditas Solana yang rapi.
2. **Prioritas Eksekusi:** Integrasi ini sebaiknya diposisikan sebagai **modul ekspansi data (telemetri/riset)**. Jangan sampai mengganggu fokus utama War Room saat ini (Arm E murah Polymarket, evaluasi BSJP IDX, dan stabilisasi OKX Crypto).
3. **Dokumen ini siap dijadikan acuan OpenClaw** untuk menyusun kode adapter begitu API key tersedia.
