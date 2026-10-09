# Desk Tencent — amati · tiru · modifikasi (9 Okt 2026)

**Arahan owner (9 Okt):** *"amati tiru modifikasi aja agar sesuai dengan existing dulu"* ·
*"ketiganya lah, tapi apikey mexcnya jangan diambil"* · *"gas a"* (tiru tampilan/UX ke web War Room).

**Sifat pekerjaan:** baca-saja ke Tencent. Tidak ada perubahan, penulisan, atau restart di Tencent.
Kredensial (`~/.hermes/mexc_futures.json`, `~/.hermes/.env`) **tidak dibaca, tidak disalin, tidak disebut isinya.**

---

## 1. Objek yang diamati

Halaman `http://43.155.219.37/markets/` = **Trading Command Center** (Forex · Crypto · IDX).
Satu halaman indeks + tiga "desk", tiap desk punya backend HTTP sendiri yang dilayani nginx.

| Desk | Web | Backend (systemd user) | Port | Sumber data |
|---|---|---|---|---|
| Crypto | `/crypto/index.html` | `crypto_dashboard.py` (1810 baris) | 8771 | `cron/jobs.json`, `cron/output/<id>/`, `crypto-watchlist.json`, `state/onchain_enrich.jsonl`, MEXC live¹ |
| IDX | `/idx616/` | `idx616_dashboard.py` (461 baris) + `idx616_academy.py` (20 baris) | 8767 / 8768 | `cron/state/idx616_signal_ledger.db`, `idx-journal/idx_journal.xlsx`, `cron/executions.db`, `cron/state/idx616_drift.json` |
| Forex | `/xau/index.html` | `xauusd_dashboard_api.py` (790 baris) | 8766 | `trading-journal/{xauusd,multipair}_journal.json` |

¹ Panel MEXC (saldo/posisi live) membaca kredensial di `~/.hermes/mexc_futures.json`.
**Atas arahan owner, panel ini TIDAK ditiru** — karenanya kredensial tidak pernah disentuh.

### Pola arsitektur ketiga desk (seragam)

```
direktori statis (index.html self-contained, vanilla JS)
        │  fetch('api/...')
        ▼
Python stdlib http.server (ThreadingHTTPServer, tanpa framework)
        │  dijalankan systemd *user* service (tahan restart gateway)
        ▼
nginx: /desk/  → file statis ;  /desk/api/ → http://127.0.0.1:PORT
```

Catatan nginx teramati (`sites-enabled/maxlabs-compact`):
- `/xau/` → alias `/var/www/xauusd-dashboard/`; `/xau/api/` → `127.0.0.1:8766/api/`
- `/idx616/` → `127.0.0.1:8767/idx616/`; `/idx616/api/research|academy` → 8767/8768
- `/markets/` → `/var/www/markets/` (halaman indeks)
- Desk Crypto dilayani terpisah pada port 8771 (**dari dalam Tencent `127.0.0.1/markets/` = 404**;
  `/markets/` menyajikan indeks saja, isi desk dilayani vhost lain).

### Endpoint per desk (terverifikasi 200, ditarik dari luar)

- **Crypto** (`/crypto/api/…`): `summary`, `pipeline`, `watchlist`, `agent6`, `equity`, `news`,
  `risk`, `scanlog`, `market_flow`, `flow`, `export.xlsx`
- **IDX** (`/idx616/api/…`): `state`, `performance`, `events`, `feed`, `equity`, `wallet`,
  `drift`, `journal`, `journal.csv`
- **Forex** (`/xau/api/…`): `stats`, `trades`, `watchlist`, `charts`, `activesignals`(= `fxplays`),
  `multipair`, `performance`, `session`, `news`, `scanlog`, `edge`, `export.xlsx`

---

## 2. Isi nyata yang sudah tersaji (contoh yang ditarik 9 Okt)

- **Crypto risk**: `open_count=2, max_open=2, balance=$20.62`, dua posisi SHORT (LINK_USDT, SUI_USDT) 10×.
- **Crypto pipeline**: job `crypto-5agent-pipeline-653`, `last_status=ok`, model `qonek/deepseek-v4.1-flash`.
- **Crypto flow (A6)**: ETH spot $840M / futures $12,1B, OI $5,89B (−3,16%), funding −0,0012%.
- **Forex activesignals**: zona XAUUSD 4H/1H (OB demand BUY 4104–4139 / 4110–4124), SR resistance SELL 4146+.

## 3. Yang dinilai layak ditiru (bagian UI/UX, bukan kredensial)

1. **Kartu "Gate live-trading — centang otomatis"** per setup: `LAYAK LIVE` / `UNPROVEN — paper dulu`,
   tiap syarat (mean R, winrate, max-DD, jumlah hari) dicentang ✓/✗ dengan nilainya.
   *Sejalan dengan aturan kita* (gate sebagai keputusan penyajian, bukan angka karangan).
2. **"Cluster-robust (bootstrap per hari) — angka jujur, bukan raw WR"**: mean R **per hari**,
   CI95, dan label `DRIFT` bila `rolling20_r < 0`.
   *Sejalan dengan `signal-performance-validation` (bootstrap per hari, bukan per trade).*
3. **Pemisahan blok**: Equity · Sinyal hidup · Journal · Paper Wallet · Operasional.
4. **Kolom jujur**: Ticker · Setup · Entry · Session · Skor · Status · **Hasil** (kosong = belum dinilai).
5. **Tombol ekspor** `.xlsx`/`.csv` dari halaman (bukan file mentah yang dipaksakan dibaca).

## 4. Yang TIDAK ditiru / sudah kita miliki

- Pembacaan file mentah Tencent langsung (kita punya lapisan `facts` + `fact_id`, ADR-004/005/006).
- Panel MEXC live (butuh kredensial — dilarang).
- Gaya "satu halaman JS raksasa": War Room memakai Svelte + komponen.

---

## 5. Rencana tiru-modifikasi (A) per desk — "sesuai existing"

Prinsip: **tampilan/UX ditiru, data tetap dari `facts` War Room** (setiap angka punya `fact_id`).

| Tahap | Desk | Yang ditiru | Sumber data di War Room | Kredensial |
|---|---|---|---|---|
| 1 | **IDX** | Gate-checklist per setup, cluster-robust per hari, tabel journal (Status/Hasil), ekspor | `idx_sinyal`, `idx_akurasi`, `bagian`, `dompet` (sudah ada; ledger mesin dibaca baca-saja) | tidak perlu |
| 2 | **Forex** | Zona sinyal aktif (pair/TF/kind/side/zona/play), sesi, performance per pair | `forex_sinyal`, `pasar_akurasi`, `bagian` | tidak perlu |
| 3 | **Crypto** | Cockpit pipeline, A6 confluence, equity, flow spot-vs-futures | `crypto_sinyal`, `pasar_akurasi`, `posisi`, `ledger` | **tanpa panel MEXC** |

Urutan dipilih dari kesiapan bahan: IDX paling siap (ledger sudah dibaca, ada gate-checklist nyata),
Forex menyusul, Crypto terakhir karena bergantung kredensial eksekusi yang tidak boleh diambil.

## 6. Verifikasi yang menyertai tiap tahap

- Setiap angka baru di UI wajib punya baris `facts` dan `fact_id` (ADR-004 butir 5).
- E2E lewat origin produksi (`https://0xgunsl1ng3r.xyz`), bukan `127.0.0.1:3100`.
- Gate/ambang (`n≥30`, `ci=0.90`, rumus BE) **tidak diubah** — hanya penyajian.
- Panel MEXC tetap absen sampai owner memasang kredensial sendiri di server ini (keputusan owner).

## 7. Catatan kejujuran (apa yang belum)

- Selisih angka crypto (Tencent `crypto_equity.jsonl` 12 baris vs lokal 31 baris) **belum direkonsiliasi**.
  Lokal memuat koreksi 9 Okt (AAVE −1,028R, TP2 tidak dihitung); perlu dibandingkan sebelum jadi klaim.
- Forex `forex_ledger = trade 0` → belum bisa dinilai (bukan "rugi").
- Standalone belum tercapai: sumber data memang publik (Binance/MEXC/TradingView), tetapi
  mesin sinyal + jurnal masih hidup di Tencent; migrasi = kerja lanjutan, bukan sekadar tampilan.
