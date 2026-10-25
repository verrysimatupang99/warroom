# Roadmap Q4 2026 — War Room

Dibuat: 24 Okt 2026 | Acuan commit: `8f155e1`

Dokumen ini menggantikan target-target informal. Isinya sengaja dibuat **terukur**:
setiap tahap punya ambang lolos dan ambang gagal, dan gagal berarti berhenti —
bukan mencoba lagi dengan cara lain.

---

## 1. Kondisi awal (semua terukur, bukan perkiraan)

| Sistem | n | Metrik | Nilai | Sumber |
|---|---|---|---|---|
| EA forex (live) | 6 | avgR | **−0,09R** | `/api/v1/tencent/mt5/history` |
| EA forex (live) | 6 | profit factor | 0,63 | idem |
| Journal crypto | 145 | avgR | **−0,104R** | `~/wr_notes/trades_all.csv` |
| Journal crypto | 145 | win rate | 55,9% | idem |
| Filter jam 12–18 WIB | 59 | avgR | +0,367R | idem (8 hari) |
| SNR (SL di luar zona) | 1.744 | expectancy | +0,006R | `ops/uji_snr.py` (p=0,081) |
| SNR (SL di dalam zona) | 466 | expectancy | **−0,099R** | idem |

**Kesimpulan kondisi awal:** belum ada satu pun konfigurasi dengan expectancy
positif yang terbukti secara statistik. Yang ada hanya kandidat.

---

## 2. Prinsip kerja

1. **Ukur dulu, ubah kemudian.** Tidak ada filter baru yang dipasang sebelum
   dampaknya terukur pada data sendiri.
2. **Setiap tahap punya kill criteria.** Gagal = berhenti, bukan iterasi tanpa akhir.
3. **Jangan menambah lapisan untuk menutupi lapisan yang belum diukur.**
4. **Simulasi ≠ kenyataan.** Panel simulator tidak menghitung slippage; angka
   simulator selalu lebih optimis.

---

## 3. Tahapan

### Tahap 0 — Infrastruktur ✅ SELESAI (24 Okt 2026)

| Komponen | Status |
|---|---|
| Panel simulator A/B/C (`warroom-panel-sim.timer`) | aktif, 30 detik |
| Logger spread per jam (`/var/lib/warroom/telemetry_log.csv`) | aktif |
| Log kualitas fill (`/var/lib/warroom/fills.csv` + EA) | aktif |
| Laporan CLI (`laporan-panel.py`, `laporan-eksekusi.py`) | siap |
| Kartu panel di web (`/forex`) | terpasang |
| Audit fullstack | selesai, 1.046 tes lulus |

---

### Tahap 1 — Buktikan atau buang filter jam 12–18 WIB

**Hipotesis:** membatasi entry ke 12:00–18:00 WIB menghasilkan avgR positif.

| | |
|---|---|
| **Ukuran sampel** | ≥ 30 trade tertutup dengan filter aktif |
| **Lolos** | avgR ≥ **+0,15R** dan p-value < 0,05 |
| **Gagal** | avgR < **+0,05R** → buang filter, jangan dipaksakan |
| **Zona abu** | +0,05R ≤ avgR < +0,15R → lanjut kumpulkan sampai 60 trade |
| **Durasi** | 2–4 minggu |
| **Cara ukur** | `ops/laporan-panel.py` + analisa `panels_trades.csv` |

**Catatan:** sampel awal hanya 59 trade dalam 8 hari. Belum out-of-sample.

---

### Tahap 2 — Bereskan slippage (paralel dengan Tahap 1)

**Hipotesis:** eksekusi XAUUSDm punya slippage signifikan yang tidak terlihat.

| | |
|---|---|
| **Ukuran sampel** | ≥ 30 fill tercatat |
| **Lolos** | median slippage ≤ **5 point** ($0,05) |
| **Gagal** | median > **15 point** ($0,15) → perbaiki eksekusi sebelum apa pun |
| **Durasi** | 1–2 minggu |
| **Cara ukur** | `ops/laporan-eksekusi.py` |

**Konteks:** pada data crypto, SL rata-rata −1,12R (bukan −1,00R). Kalau pola sama
muncul di forex, itu kebocoran 12% per loss yang tidak terlihat di P&L harian.

---

### Tahap 3 — Validasi SNR

**Hipotesis:** SL yang diletakkan di luar zona S/R menghasilkan expectancy lebih baik.

| | |
|---|---|
| **Ukuran sampel** | 60 hari data M5 (~17.000 candle) |
| **Lolos** | p-value < **0,05** dengan arah efek konsisten |
| **Gagal** | p ≥ 0,05 → buang ide SNR |
| **Durasi** | 1 minggu (bisa dikerjakan sekarang) |
| **Cara ukur** | `ops/uji_snr.py` dengan `range_period` diperbesar |

**Status saat ini:** ❌ **GAGAL** — diuji ulang dengan 60 hari data (13.435 candle,
26.306 trade): selisih win rate **−0,3 poin persentase**, p = **0,741**. Efek +4,4 pp
pada uji 5 hari ternyata artefak sampel kecil. **Ide SNR dibuang** sesuai kill criteria.

| Uji | n | Terlindungi | Rentan | Selisih | p |
|---|---|---|---|---|---|
| 5 hari | 2.210 | 43,1% | 38,6% | +4,4 pp | 0,081 |
| **60 hari** | **26.306** | 42,6% | 42,8% | **−0,3 pp** | **0,741** |

---

### Tahap 4 — Keputusan modal

Baru dijalankan bila **Tahap 1 dan 2 lolos**.

| | |
|---|---|
| **Syarat** | avgR ≥ +0,15R (T1) **dan** median slippage ≤ 5 point (T2) |
| **Tindakan** | naikkan risiko bertahap: 2,5% → 5% → 7,5% per trade |
| **Batas** | drawdown harian tetap dijaga ratchet; stop bila DD > 10% |
| **Durasi** | bulan ke-2 |

---

## 4. Target angka (kalau Tahap 1–3 lolos)

Asumsi: risiko 2,5% per trade, 100 trade/bulan.

| avgR | Hasil per bulan |
|---|---|
| −0,10 (kondisi sekarang) | **−25%** |
| +0,05 | +12,5% |
| +0,10 | +25% |
| +0,20 | +50% |

**Poin penting:** avgR +0,05 saja sudah cukup untuk dua digit per bulan.
Targetnya tidak perlu ambisius — masalahnya sekarang berada di **minus**.

---

## 5. Yang tidak dijanjikan

| Klaim | Alasan menolak |
|---|---|
| 10× modal dalam sebulan | butuh avgR jauh di atas +0,37 secara konsisten; belum pernah terbukti > 8 hari |
| Profit bulan ini | data belum cukup untuk mengklaim apa pun |
| Angka simulator = angka nyata | simulator tidak menghitung slippage/komisi |
| Menambah filter baru sebelum diukur | menambah lapisan tanpa bukti hanya menurunkan frekuensi |

---

## 6. Dua jalur

| | Forex EA | Crypto journal |
|---|---|---|
| Data terkumpul | 6 trade | 145 trade |
| Jam pasar | 5 hari/minggu | 24/7 |
| Kecepatan sampel | lambat | **3–4× lebih cepat** |
| Status infrastruktur | live + instrumentasi | manual (Notion) |

**Prioritas:** crypto untuk kecepatan sampel, forex sebagai pembanding yang sudah live.

---

## 7. Cara verifikasi (perintah siap pakai)

```bash
cd ~/warroom

# Tahap 1 — kinerja panel
.venv/bin/python ops/laporan-panel.py

# Tahap 2 — kualitas eksekusi
.venv/bin/python ops/laporan-eksekusi.py

# Tahap 3 — validasi SNR
.venv/bin/python ops/uji_snr.py

# Kesehatan umum
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python ops/check-openapi-contract.py
```

---

## 8. Log keputusan

| Tanggal | Keputusan | Dasar |
|---|---|---|
| 24 Okt 2026 | Infrastruktur pengukuran diprioritaskan di atas perubahan strategi | semua konfigurasi masih expectancy negatif |
| 24 Okt 2026 | SNR belum dijadikan filter | p = 0,081, belum signifikan |
| 24 Okt 2026 | Filter jam 12–18 belum dipasang ke EA asli | sampel 8 hari, belum out-of-sample |
| 24 Okt 2026 | Panel A/B/C dijalankan sebagai simulasi, bukan order nyata | membandingkan skema tanpa risiko modal |
| 24 Okt 2026 | **SNR DITOLAK** — hipotesis tidak terbukti | 60 hari data (26.306 trade): selisih win rate **−0,3 pp**, p=0,741. Efek +4,4 pp pada 5 hari ternyata noise. |

---

## 9. Titik keputusan berikutnya

| Kapan | Apa |
|---|---|
| Senin 27 Okt (pasar buka) | mulai kumpulkan data Tahap 1 & 2 |
| +30 trade | evaluasi awal Tahap 1 |
| +30 fill | evaluasi Tahap 2 |
| Kapan saja | jalankan Tahap 3 dengan data 60 hari |
