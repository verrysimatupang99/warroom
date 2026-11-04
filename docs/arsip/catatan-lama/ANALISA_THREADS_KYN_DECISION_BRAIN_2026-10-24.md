# Analisa Threads — "Kyn Legacy / DECISION BRAIN" (@arjani.ari)

Tanggal: 24 Okt 2026
Sumber: https://www.threads.com/@arjani.ari/post/De38vzsj40h (2.3K views, 11 jam)

---

## 1. Isi thread

**Post utama:**
> • Kyn Legacy • DECISON BRAIN.
> Konsep state machine yang me-retrace setiap candle XAUUSD berurutan → BIAS → SNR MAP →
> FILTER → SYNERGY → DECISION → GUARD. Gak lolos check list NO TRADE.
> Python + API Broker + MQL5, dibangun bareng CLAUDE ☆ SONNET ENGINE.

**Klarifikasi penulis (dari balasan):**
- "Ini baru **konsep**" — belum ada backtest/forward test
- "**Bukan EA** — lebih ke saran keputusan buat trader... dia sebagai translator kepada trader"
- "Walaupun bisa gue suntik EA, gue lebih nyaman gue yang ambil keputusan"
- Pipeline: `INGEST > BIAS Check > SNR Mapping > Volatility Filter > Synergy Check > Risk Guard`
- "If even one metric misses the checklist, the system instantly kills the setup (NO TRADE)"
- UI: Python dengan "lightweight particle rendering loop" untuk menandai blok mana yang
  sedang memasok data ke decision engine

**Tanggapan di kolom komentar:** satu orang menanyakan backtest (dijawab: belum ada),
satu meminta detail, satu menawarkan kolaborasi dengan analisa makro.

---

## 2. Perbandingan dengan War Room kita

| Tahap Kyn Legacy | Padanan di War Room | Status |
|---|---|---|
| **INGEST** | telemetri MT5 tiap 1–5 detik (bid/ask/spread/ATR/EMA) | ✅ kita lebih rapat |
| **BIAS** | tren H1 + sesi (Asian/London/NY) | ✅ ada |
| **SNR MAP** | — | ❌ **kita tidak punya** |
| **FILTER (volatilitas)** | ATR M5 + ambang Laya | ✅ ada |
| **SYNERGY** | multi-sesi + verdict Laya + R:R | ✅ ada |
| **DECISION** | status `OK` / `WAITING_SETUP` | ✅ ada |
| **GUARD** | fail-closed + R:R guard + drift check + daily ratchet | ✅ **kita lebih lengkap** |

### Kesamaan yang mencolok
Filosofi "**satu syarat gagal → NO TRADE**" itu persis **R3 fail-closed** yang kita bangun.
Dua orang sampai ke prinsip yang sama secara independen — itu konfirmasi desain, bukan kebetulan.

### Perbedaan mendasar
| | Kyn Legacy | War Room |
|---|---|---|
| Peran | **decision support** (manusia eksekusi) | **eksekusi otomatis** (EA) |
| Validasi | belum ada backtest | 1.035 tes otomatis |
| Data live | belum ada | 145 trade crypto + 6 trade forex tercatat |
| Eksekusi | manual | EA MT5 + guard berlapis |

---

## 3. Celah yang mereka tunjukkan pada kita

**SNR MAP — pemetaan support/resistance eksplisit.**

Sistem kita menentukan level dari **jarak ATR** (`risk`/`reward` relatif), bukan dari
struktur harga. Artinya SL/TP kita tidak tahu di mana swing high/low, liquidity pool,
atau level yang dihormati pasar.

Ini menjelaskan sebagian temuan analisa crypto kita:
- `sl-placement` punya win rate **3,1%** — SL ditempatkan di zona rawan
- 54 trade SL rata-rata **−1,12R** — SL kena lebih dalam dari rencana

Kalau level diturunkan dari struktur (SNR), SL bisa diletakkan **di balik** level,
bukan di tengah zona likuiditas.

**Ini kandidat perbaikan paling berdampak** yang muncul dari riset ini.

---

## 4. Ide lain yang layak diambil

**Visualisasi tahap pipeline.** Mereka menandai "blok mana yang sedang memasok data".
Kita hanya punya `blocked_reason` di tahap akhir — kalau sinyal ditolak, kita tahu
alasan terakhirnya, tapi tidak tahu tahap mana yang paling sering menggagalkan.

Menambahkan pencatatan per-tahap (BIAS lolos? FILTER lolos? SYNERGY lolos?) akan
langsung menunjukkan **di mana bottleneck sistem kita** — persis seperti analisa
"jam mana yang merugi" tapi untuk tahap keputusan.

---

## 5. Penilaian jujur

**Kelebihan:** arsitektur bersih, urutan tahap masuk akal, filosofi fail-closed benar,
dan penulisnya sadar batas (mengaku masih konsep, tidak mengklaim profit).

**Kekurangan:** belum ada backtest sama sekali, belum ada angka, belum ada bukti.
Tanpa validasi, "state machine 7 tahap" tidak berbeda dari daftar keinginan —
dan setiap tahap tambahan menambah peluang menolak setup yang sebenarnya bagus.

**Yang bisa kita ambil:** konsep **SNR MAP** dan **visibilitas per-tahap**.
Yang **tidak** perlu ditiru: menambah lapisan tanpa mengukur dampaknya lebih dulu.

---

## 6. Rekomendasi

1. **Uji ide SNR MAP** — tambahkan pemetaan swing high/low + zona likuiditas sebagai
   filter, lalu bandingkan `sl-placement` rate sebelum vs sesudah. Ini terukur.
2. **Catat status per-tahap** di engine (bukan hanya `blocked_reason` akhir), tampilkan
   di dashboard. Murah, dan langsung menunjukkan bottleneck.
3. **Jangan** menambah tahap baru sebelum yang ada diukur. Kita sudah punya 3 guard
   berlapis; menambah lapisan ke-4 tanpa data hanya menurunkan frekuensi trade.
