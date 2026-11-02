# Handover — Riset Gold Reaper (sesi OMP 2 Nov 2026)

> Diekstrak dari sesi agent OMP `2026-11-02T07-01-04-268Z_01a19b0f` sebelum OMP dilepas
> dari server. Arsip penuh: `/home/admin/backup-omp/omp-sessions-20261102.tar.gz`.
> Ditulis 2 Nov 2026 oleh Hermes.

---

## 1. Status satu layar

| Item | Status |
|---|---|
| Wave 0 — audit & fondasi | ✅ DONE (`docs/wave0-audit-20261102.md`) |
| Gate G1 — Golden Pullback emas | ❌ **NO-GO** (diuji di PAXG 5,8 th) |
| Lab 3 hipotesis (momentum sesi, opening range NY, trend sesi) | ❌ **NO-GO, ketiganya** |
| EA exporter `ops/mt5/WarRoom_HistoryExporter.mq5` | ✅ selesai, teraudit bebas `OrderSend` |
| Ingestor/validator `packages/live-trading/.../ingest_mt5.py` | ✅ selesai |
| Data XAUUSD multi-tahun | ⛔ **BLOKIR utama** — hanya ada 27 hari |

**Riset terhenti di satu titik:** data XAUUSD multi-tahun tidak ada di mesin ini,
dan terminal MT5 di container tidak login ke akun `452009427`.

---

## 2. Hasil Gate G1 (NO-GO, jangan diulang tanpa data baru)

Golden Pullback diuji pada **51.133 candle PAXG 1h (5,8 tahun)** — bukan XAUUSD,
karena XAUUSD lokal cuma 30 hari. Hasil:

| Metrik | Nilai |
|---|---|
| Expectancy | −0,308 R |
| Profit factor | 0,608 |
| R kotor (sebelum biaya) | −3,61 R |
| Prob. profit (bootstrap 2.000×) | 20,1% |
| Sensitivitas 16 parameter | tidak ada plateau |

Catatan: rugi sudah muncul **sebelum biaya** → arah entry-nya yang salah, bukan spread.

**Bug yang ditemukan di kode sendiri:** model biaya sempat salah (spread malah
membantu posisi selamat). Sudah diperbaiki + seluruh backtest dijalankan ulang.
Angka lama dibuang. Runner dikunci 19 unit test.

PR #83 sudah merge ke `main`, CI hijau.

---

## 3. Lab 3 hipotesis (semua NO-GO)

| Hipotesis | n | Ekspektansi | PF | t-stat |
|---|---|---|---|---|
| Momentum antar-sesi | 1530 | −0,054 R | 0,91 | −1,45 |
| Opening range NY | 827 | −0,003 R | 0,99 | −0,09 |
| Trend sesi | 4640 | −0,117 R | 0,84 | −5,76 |

**Dua bug kode sendiri yang ditemukan:**
1. Filter opening range 0,7× ATR membunuh semua sinyal (jam 13:00 UTC range-nya
   1,4–2,2× ATR harian, bukan 0,7×).
2. Cek breakout di candle terakhir range mustahil terpicu (`close` selalu di dalam
   `low/high` miliknya sendiri).

**Catatan proses:** commit pertama sempat ter-push langsung ke `main`; revert
`276b61a` lalu masuk lewat PR #84. `main` bersih, riwayat menyimpan jejaknya.

Dokumen: `docs/riset-reaper-g1-20261102.md`, `docs/riset-reaper-lab-3-hipotesis-20261102.md`

---

## 4. Temuan Laya AI (penting, belum ditindak)

Laya = middleware keputusan + gate risiko di War Room, **bukan chatbot**.

| Peran | Komponen |
|---|---|
| Penilai sinyal | `laya_forex.py` → verdict BULLISH/BEARISH/NEUTRAL + confidence |
| Sentinel latar | `laya_sentinel.py` → status + bias global |
| Gate fail-closed | `laya_verdict.py` + timer 60s → verdict basi >180s = semua eksekusi ditolak |

**Hasil uji empiris 7 skenario: model ini tidak layak dipakai di jalur eksekusi.**

| Input | Output |
|---|---|
| Konteks kosong | SKIP, p=0,4908 |
| XAUUSD BUY setup ideal | SKIP, p=0,2596 |
| XAUUSD BUY bodoh (floating −180, 3 posisi, free margin 40) | SKIP, p=**0,2710** ← skor lebih tinggi |
| 12 sinyal XAU asli dari DB Telegram | 12/12 SKIP |

- **Never EXECUTE**: ambang 0,60, skor tertinggi 0,49. Kalau dinyalakan = dead-lock permanen.
- Tidak bisa membedakan trade bagus vs buruk.
- Deterministik per arah (8 BUY berbeda semua 0,2596).
- Penyebab: ModernBERT 395M zero-shot classifier, salah tafsir fungsional.

**Kabar baik:** `WARROOM_LAYA_ENABLE` tidak diset di prod → default OFF, tidak ada damage.

**4 aksi yang direncanakan:**
1. Mulai log verdict ke DB (sekarang tidak ada historisasi → overlay tidak bisa di-backtest).
2. Alert Telegram saat fail-closed macet >180s.
3. Fail-safe sudah benar (`TAK_DIKETAHUI` saat model gagal) — tinggal alarm.
4. Tambah fallback model (Nectere) karena sekarang single point of failure.

Dokumen: `docs/investigasi-laya-ai-20261102.md`

---

## 5. Rencana 7 Wave (revisi dari 4 wave)

Prinsip: **tidak ada uang nyata bergerak tanpa lolos gate.**

| # | Wave | Gate | Estimasi |
|---|---|---|---|
| 0 | Audit & Fondasi ✅ | Laporan tertulis | DONE |
| 1 | Riset Quant Gold Reaper | **G1**: PF>1,3 OOS, DD<10%, robust 3 konfigurasi | 7–10 hari |
| 2 | Platform Core | **G2**: end-to-end paper hijau, kill-switch teruji | 10 hari |
| 3 | Multi-Strategi & Multi-Market | **G3**: 2+ strategi lolos G1 tanpa ubah core | 10–14 hari |
| 4 | Forward Test Cent | **G4**: 20 hari, DD<10%, PF live ≥70% backtest | 4 minggu |
| 5 | Hardening & Produksi | **G5**: zero critical, DR drill lolos | 1–2 minggu |
| 6 | Skala & Handover | **G6**: owner bisa jalankan tanpa agent | berkelanjutan |

Framework: hybrid 4 lapis — Stage-Gate + Kanban (per wave) + Spec-Driven
Development (per fitur) + statistik riset (per strategi).

**Rekomendasi agent saat itu:** Wave 4 tidak punya kandidat untuk dipromosikan.
Lanjut ke **Wave 2 (bangun platform inti)** — infrastrukturnya dipakai ulang
terlepas dari strategi mana yang lolos nanti.

---

## 6. ⛔ Blokir: kenapa riset tidak bisa lanjut

Bukti yang dikumpulkan langsung di container:

1. Terminal MT5 hidup tapi **tidak login** (`mt5-status.sh`). Tidak ada log
   `20261102.log`, port MCP `22346` tidak pernah listen.
2. Di seluruh wine prefix hanya ada 4 simbol ter-cache: `EURUSD, GBPUSD, USDCHF,
   USDJPY`. **Nol byte XAUUSD.**
3. `MetaEditor64.exe /compile` gagal (exit=124, tidak menghasilkan `.ex5`) — jalur
   compile EA tertutup.
4. `config/accounts.dat` kosong. `terminal.ini` tidak punya field login tersimpan.
5. Port 3300 = nginx default kosong, tidak ada selkies/x11vnc. Xdotool + XWD bisa
   screenshot tapi input sintetis X tidak sampai ke aplikasi Windows di wine.
6. Data yang ada: `data/hist/XAUUSD_15m.csv` = **27 hari** (21 Sep – 21 Okt 2026),
   kualitas bersih (0 duplikat, 0 bar OHLC inkonsisten) tapi cakupan tidak cukup.

---

## 7. Yang dibutuhkan dari owner (pilih satu)

1. **Investor password akun `452009427`** (Exness-SC) — paling aman, read-only,
   tidak bisa order. Ambil di MT5: Tools → Options → Server → Change password →
   kolom *investor password*. Atau via Personal Area Exness.
   → setelah itu: login, subscribe `XAUUSDm`, tarik M1 2019–2026 lewat MCP.
2. **Login manual sekali** di noVNC container `warroom-mt5-node`, lalu drag
   `XAUUSDm` ke Market Watch. Setelah itu agent bisa jalan sendiri.
3. **Taruh file ekspor** XAUUSD (M1/M15, 2019–2026) di `data/hist/` — ekspor dari
   MT5 Windows sendiri via History Center, atau sumber publik (Dukascopy, HistData,
   Kaggle — sebutkan sumbernya agar tercatat).

**Catatan:** EA exporter butuh **spread** dan **tick volume** ikut terekam. Kalau
sumber publik tidak punya spread, pakai asumsi konservatif 20–30 poin dan tulis
eksplisit di laporan.

---

## 8. Langkah pertama begitu data ada

1. Validasi paket data (`ingest_mt5.py`) → laporan kualitas.
2. Profil volatilitas per sesi.
3. Hipotesis A → B → C, satu per satu, dengan gate yang sama (tidak dilonggarkan).
4. Iterasi sampai lolos G1 **atau** dinyatakan NO-GO dengan bukti.

**Aturan yang tidak boleh dilanggar:** jangan mengisi kolom G1 pakai CSV 27 hari
atau PAXG. Lebih baik jujur kosong daripada laporan yang terlihat hijau tapi
tidak berarti.
