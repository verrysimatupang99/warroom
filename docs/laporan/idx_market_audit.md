# Laporan Audit Arus Foreign Flow, Akumulasi Bandarmologi & Codebase IDX
**Tanggal Audit:** 23 Oktober 2026  
**Entitas:** IDX Equity Specialist — War Room Platform (`/home/admin/warroom-agents/idx`)  
**Peninjau:** IDX Equity Specialist (Model: Laguna-s-2.1 Subagent & Primary Agent)

---

## 1. Executive Summary & Arsitektur Pasar IDX di War Room

Workspace `/home/admin/warroom-agents/idx` beroperasi sebagai lingkungan kerja mandiri untuk domain pasar ekuitas Indonesia (Bursa Efek Indonesia / IDX). Seluruh pipeline mengacu pada prinsip arsitektur War Room:
1. **ADR-005 & Prinsip Anti-Halusinasi:** Data intelijen berasal dari fakta empiris (database/feed read-only), dilarang mengarang angka (`tidak-izin`/`n/a` jika data tidak terbaca, bukan nol).
2. **Segmentasi Pipeline & Cap Fase 2:** 
   - **Data Feed / Ingestion:** Arjum Collector (`packages/live-trading/src/live_trading/collectors/idx.py`) dan Hermes MiniMax Proxy (`services/api/src/warroom_api/routers/idx.py`).
   - **Kuantitatif & Analitik:** Bandarmologi Broker-Flow Replicator (`packages/live-trading/src/live_trading/collectors/bandarmologi.py`).
   - **Pod IDX (`packages/live-trading/src/live_trading/pods/idx.py`):** Dibatasi pada **Cap Fase 2** (analisis sinyal mirror & konsentrasi, order disiapkan untuk eksekusi manual di broker, tanpa auto-order liar).
3. **Status Pengujian:** 39 unit test pada `test_bandarmologi.py` dan `test_collectors.py` lulus 100% (audit run: Python 3.14.7, pytest-8.4.2).

---

## 2. Analisis Arus Foreign Flow & Mekanisme Deteksi Arjum API

Foreign Flow (aliran dana asing) pada pasar reguler IDX dideteksi melalui pelacakan data agregat dan broker summary dari endpoint Arjum API (`stock.arjum.com`):

### 2.1. Sumber Data & Endpoint
- `/api/screener/latest`: Menyaring saham berdasarkan metrik likuiditas, volume pemicu, dan pergerakan harga. (TTL: 30 menit).
- `/api/broker-summary/{code}`: Menyajikan rincian broker pembeli/penjual (`bval`, `sval`, `bfrq`, `sfrq`, `nval`). (TTL: 60 menit).
- `/api/history/{code}`: Riwayat OHLCV harian untuk baseline pembanding return. (TTL: 4 jam).
- `/api/analysis/{code}`: Indikator teknikal, fundamental, dan estimasi arus foreign. (TTL: 24 jam).

### 2.2. Integritas Deteksi Foreign Flow
- Arus asing dihitung dari selisih beli bersih (`nval` positif) pada broker-broker dengan kode klasifikasi partisipan asing (misalnya broker berkode AK, BK, CS, KZ, RX, ZP).
- Agregasi net flow tidak berdiri sendiri; dikorelasikan dengan pergerakan harga saham untuk mendeteksi apakah terjadi **Mark-up dengan Foreign Accumulation** atau **Distribution on Strength**.

---

## 3. Audit Logika Bandarmologi (`bandarmologi.py`)

Modul `packages/live-trading/src/live_trading/collectors/bandarmologi.py` mereplikasi parameter sistem "KRAKEN FLOW / ORCA" (IHSG Screener) dengan transparansi formula tanpa klaim palsu.

### 3.1. Parameter yang Berhasil Direplikasi
- **Average Trade Size (ATS):**
  $$\text{ATS Beli} = \frac{\sum \text{Nilai Beli}}{\sum \text{Frekuensi Beli}}, \quad \text{ATS Jual} = \frac{\sum \text{Nilai Jual}}{\sum \text{Frekuensi Jual}}$$
  *Catatan Audit:* Implementasi menggunakan fungsi `_total_berpasangan(brokers, 'bval', 'bfrq')` yang menjamin hanya broker dengan pasangan nilai dan frekuensi lengkap yang dihitung. Hal ini mencegah distorsi pembagi yang membengkak bila data salah satu broker korup.
- **Porsi Frekuensi Beli (`porsi_frq_beli`):**
  $$\frac{\sum \text{Frekuensi Beli}}{\sum \text{Frekuensi Beli} + \sum \text{Frekuensi Jual}}$$
  Rasio $> 0.5$ mengindikasikan dominasi inisiatif beli di pasar reguler.
- **Net Buy / Net Nilai (`net_nilai`):**
  Akumulasi nominal beli bersih broker (`nval`).
- **No Sell (`no_sell`):**
  Broker akumulator teratas (pembeli no. 1) memiliki aktivitas jual sangat minim ($\frac{\text{frq\_jual}}{\text{frq\_beli}} < 0.20$), mengindikasikan akumulasi tanpa buang muatan.
- **Top Volume & Frequency:** Terakomodasi dari agregat broker summary harian.

### 3.2. Parameter yang Tidak Dapat Direplikasi (Data Boundary)
- **High Bid/Offer:** Membutuhkan data *Order Book / Depth Queue Level II* secara real-time. Arjum API dan TradingView tidak menyediakannya.
- **High Non-Regular:** Membutuhkan data transaksi pasar negosiasi/tunai (pasar non-reguler) yang tidak ada di skema Arjum.
- *Status Kepatuhan:* Modul secara eksplisit memuat `CATATAN_REPLIKASI` dan `LABEL_JUJUR` pada setiap payload keluar, melarang klaim "edge pasti untung".

### 3.3. Formula Heuristik & Evaluasi Backtest
Skor komposit heuristik (0–100) dihitung secara transparan:
- Porsi Frekuensi Beli: Bobot **40 poin**
- Net Beli Positif: Bobot **30 poin**
- ATS Beli > ATS Jual: Bobot **20 poin**
- No Sell Trigger: Bobot **10 poin**

**Mekanisme Evaluasi `test_history()`:**
- Menggunakan `broker_accumulation` vs baseline return $N$-hari (Horizon: 5, 10, dan 20 hari).
- **Aturan Verifikasi Ketat:**
  1. `ada-keunggulan`: Jika $\ge 2$ horizon mengungguli baseline pasar.
  2. `perlu-uji-tambahan`: Jika seluruh horizon pasar acuan juga positif (mencegah kebetulan bullish market diklaim sebagai kehebatan sinyal).
  3. `tidak-terbukti`: Jika sinyal tidak melampaui rata-rata hari acuan.

---

## 4. Audit Kolektor & Integritas Data (`collectors/idx.py`)

Kolektor `packages/live-trading/src/live_trading/collectors/idx.py` mengimplementasikan guard ketat terhadap resource Arjum:

### 4.1. Bug Pencegahan Double Suffix `.JK.JK`
- **Akar Masalah (Incident 6 Okt 2026):** WebSocket daemon menghasilkan ticker berakhiran `.JK` (misal `CAMP.JK`). Saat diproses oleh komponen konsumen, `yfinance` menambahkan `.JK` kembali menjadi `CAMP.JK.JK` (404), yang memicu fallback otomatis ke Arjum dan menghabiskan 1.447 kuota dalam sehari.
- **Solusi Kolektor:** Fungsi `_kode_bersih(code)` secara idempoten memotong suffix `.JK` dan melakukan uppercase:
  ```python
  def _kode_bersih(code: str | None) -> str:
      kode = str(code or "").strip().upper()
      if kode.endswith(".JK"):
          kode = kode[:-3]
      return kode
  ```

### 4.2. Quota Guard & Anti-Freeze Bug (`_kuota_basi`)
- **Quota Limit:** 6.000 panggilan/hari. Ambang batas aman dikonfigurasi melalui `settings.arjum_min_remaining`.
- **Bug Freeze Resolusi (Insiden 5 Okt 2026):** Dulu, jika kuota tersisa $<$ ambang batas, panggilan langsung diblokir. Karena diblokir, header HTTP tidak pernah dibaca lagi, menyebabkan `remaining` membeku pada angka kemarin dan mematikan feed IDX selama 11 jam.
- **Logika Pencegah Saat Ini:** `_kuota_basi()` mengecek apakah tanggal catatan kuota berbeda dengan hari ini (WIB/UTC+7). Jika tanggal basi, guard meloloskan satu panggilan untuk membaca header segar (`x-ratelimit-remaining`), lalu memperbarui state kuota lokal.

### 4.3. Pola Caching & Audit Logging
- Berkas cache disimpan di `state/cache/arjum/{safe_key}.json`.
- TTL terisolasi per jenis endpoint (30m untuk screener s/d 7 hari untuk fundamental/musiman).
- Setiap request live maupun cache-hit dicatat ke JSONL audit harian: `logs/arjum_audit_YYYY-MM-DD.jsonl`.

---

## 5. Data Feeds & Integrasi Pipeline

1. **Proxy Router FastAPI (`services/api/src/warroom_api/routers/idx.py`):**
   - Meneruskan panggilan analitik langsung ke MiniMax node (Tencent) via Tailscale IP (`100.126.10.74:8790`).
   - Melayani endpoint: `/api/v1/idx/stats`, `/signals`, `/market`, `/flow`, `/ledger`, `/equity`, `/feed`, `/news`, `/scanners`, `/official`.
   - Read-only tanpa beban komputasi lokal, mematuhi prinsip War Room sebagai agregator keputusan.
2. **Pod Live Trading IDX (`packages/live-trading/src/live_trading/pods/idx.py`):**
   - Menghitung `analyze_mirror` (status sinyal terbuka/unik) dan `analyze_concentration` (distribusi R-risk per setup).
   - Status dilaporkan dengan label eksplisit: `"cap Fase 2: order disiapkan, eksekusi manual di broker"`.

---

## 6. Temuan Audit & Rekomendasi Action Plan

### Temuan:
1. **Validitas Codebase:** Semua pengujian unit suite IDX dan Bandarmologi berstatus **100% Passed**. Kode bersih dari hardcode credentials.
2. **Keterbatasan Data Bandarmologi:** Formula ATS dan No Sell sudah solid, namun metrik akumulasi masih berbasis broker harian bukan intraday order book flow.
3. **Penyimpanan Kuota:** Mekanisme anti-freeze sudah teruji aman dan berjalan stabil di Python 3.14 environment.

### Action Plan / Rekomendasi:
1. **Penyaringan Skrining Sebelum Panggilan Broker Summary:**
   Tetap pertahankan batasan `maks_ticker=8` pada fungsi `skrining()` di `bandarmologi.py` agar kuota Arjum 6.000/hari tetap terjaga untuk job analitik lain.
2. **Koneksi Intraday Flow (Tahap Mendatang):**
   Jika nanti dibutuhkan parameter *High Bid/Offer*, integrasi harus dilakukan melalui broker feed resmi atau data stream IDX Tick-by-Tick, bukan memaksakan scraping ke Arjum.
3. **Pemeliharaan Audit JSONL:**
   Pastikan rotasi berkas `arjum_audit_*.jsonl` di direktori logs dipantau oleh worker maintenance berkala agar tidak memakan disk pada node lokal.

---
*Laporan audit disahkan oleh IDX Equity Specialist untuk Chief Orchestrator & War Room Board.*
