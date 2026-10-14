# Playbook Trading Paper — pelajaran dari live trade & repo terbukti

Status: acuan kerja. Tanggal: 14 Okt 2026.
Sumber: `tencent-cronjob-trade.md`, `tencent-dashboard-live.md`, `repo-trading-arsitektur.md`
ketiganya di `docs/riset/`.

Tujuan: menaikkan peluang **profit** paper trade dengan meniru apa yang **terbukti bekerja**
di sistem live (Tencent, uang nyata) dan di repo publik yang mapan, dan dengan menghindari
kesalahan yang sudah memakan biaya nyata.

---

## 1. Aturan masuk (entry)

- **Gerbang konkurensi** dulu: `MIN_CONFLUENCE` (Tencent turun dari 5/6 ke 2/6 setelah
  terbukti terlalu ketat menahan trade bagus). Ambang harus SAMA di semua jalur (harian &
  watch) — Tencent pernah kena "dua standar untuk setup yang sama" (1 Sep 2026).
- **LIMIT-only, tanpa stop-entry.** Limit yang dipasang ke zona yang sudah ditembus = keisi
  instan ke pasar yang jatuh. Kalau harga sudah melewati zona → tandai WATCH, jangan entry.
- **Filter ATR minimum** (Tencent: 0.15% harga). Membuang pair yang volatilitasnya terlalu
  tipis untuk biaya; terbukti menyaring EURUSD yang dua-duanya SL tanpa membuang XAU/NAS100.
- **Blackout sesi & berita**: hindari jam Asia tipis; mundur ±30 menit dari rilis
  high-impact, ±15 menit medium. Ini menyaring mayoritas trade buruk.
- **Anti-duplikat berbasis umur, BUKAN tanggal kalender** (Tencent: `DEDUPE_HOURS=12`).
  Dedupe berbasis tanggal meloloskan sinyal kembar di tengah malam. Dan **jangan** biarkan
  exception tertelan mematikan dedupe (bug `datetime.datetime` pernah mematikan dedupe senyap).

## 2. Ukuran posisi & risiko

- **Risiko dari jarak stop, bukan notional tetap.** 1R = risk_pct × saldo **awal** (tanpa
  compounding — sampel kecil, compounding hanya memperbesar derau; lihat `dompet.py`).
- **Batas risiko**: `MAX_OPEN_TOTAL=2`, `MAX_OPEN_PER_PAIR=1` (Tencent).
- **Daily loss stop**: `daily_r <= -1.5R` → berhenti entry baru hari itu.
- **Risiko tak terbatas harus diklasifikasi, bukan disembunyikan.** Gap membuka posisi di
  luar stop → R bisa < -1R (Tencent: sampai -13,84R). `dompet.py` sudah mengklasifikasi
  (wajar/gap/dalam/ekstrem) dan menerbitkan `pelanggaran_1r`. **Jangan pakai setup dengan
  risiko tak terbatas sebagai tulang punggung dompet** (ARA_HUNTER: -139R sendirian).

## 3. Aturan keluar — "exit rule v3" (inti profit)

Ini aturan yang terbukti di Tencent dan SUDAH dikodekan di `execution/paper.py`:

1. **TP1 (1R) → tutup 50% + geser SL ke break-even.** Status posisi jadi `tp1_hit_runner`.
2. **Runner** dibiarkan berlari ke TP2 (2R).
3. **BE di-arm tepat di TP1** (v2 dulu menunggu 1,2R — v3 mengubah ke tepat TP1; caption
   harus sama agar tidak kontradiksi).

**Akuntansi konservatif (wajib):**
- Bila satu candle memuat SL **dan** TP → **anggap SL kena lebih dulu**. Mengasumsikan hasil
  baik akan menggelembungkan win-rate.
- Runner yang berhenti di BE setelah TP1 bernilai **+0,5R**, bukan 0R.
- Effective TP2 saat ada partial = `(rr_tp1 + rr_tp2)/2`.
- **NO FILL bukan trade** dan **tidak** masuk hitungan win-rate (r=0).

## 4. Seleksi strategi (1-2 terbaik per market)

- **Rank dengan Python dari data tersimpan**, bukan dari kepala. Simpan tiap run
  (market × strategi × metrik) ke JSON/CSV, lalu urutkan di kode.
- **Metrik multi-faktor**: Net PnL, Max Drawdown, Sharpe, Profit Factor (+ n, win-rate).
  Profit tanpa drawdown/Sharpe = overfit.
- **Gate ambang numerik sebelum "aktif"**: mis. Sharpe > 0,8 **dan** DD < 15% selama 2 bulan
  (praktik komunitas Freqtrade). Di sistem ini ambang minimum: `n >= 20` dan `sum_r > 0`.
- **Satu strategi = satu dompet/ledger terisolasi** (beebots `BEE_START_EQUITY_USD`).
  Perbandingan antar-strategi baru sah kalau equity tidak tercampur. Ditegakkan di
  `strategi_terpilih.py::dompet_strategi()`.
- **Status jujur**: `aktif` (bukti positif) / `belum-terbukti` (sampel kecil / metrik bukan-R)
  / **`dihentikan`** (bukti negatif). Yang merugi TIDAK dijalankan.

## 5. Backtest: jangan bohongi diri

- **Satu jalur kode** backtest ↔ paper. Kalau logika punya dua implementasi, metrik bohong.
- **Walk-forward + out-of-sample**, bukan satu split.
- **Ringkas backtest jujur 14 Okt** (crypto, 8441 kandidat):
  - Semua (tanpa gate): bersih **-0,003R**; "t=+4,63 (kuat)" pada GROSS, tapi setelah biaya
    praktis nol.
  - Lolos gate: bersih **-0,029R**; "tidak bisa dibedakan dari derau".
  - **Kesimpulan jujur: belum ada strategi crypto yang terbukti untung setelah biaya.**
- Artinya: **jangan aktifkan strategi karena "kelihatan bagus"**. Yang belum terbukti
  ditandai `belum-terbukti`, bukan dipaksa `aktif` (R-17/R-38 antislop: jangan tampilkan
  angka tanpa sumber; kosong/jujur lebih baik dari menyesatkan).

## 6. Biaya = pembunuh profit (jangan lupa)

- **Fee dua kali** (masuk + keluar). Tencent mencatat biaya terukur dari buku nyata
  (`collectors/depth.py` + `execution/costs.py`), bukan asumsi 0,1%.
- **Gross yang positif sering jadi bersih negatif setelah biaya** — lihat angka backtest di
  atas (-0,003R). Profit bersih = profit kotor − fee − biaya data/inferensi.
- **Cap biaya non-trading** (beebots `JEV_DAILY_USD_CAP=2`): batasi biaya LLM/API harian.

## 7. Keselamatan & operasi

- **Risk layer di plain code**, independen dari LLM/sinyal (beebots: model keputusan tak
  pernah melihat endpoint order; bisa veto/kecilkan/paksa).
- **Fail safe**: sinyal/LLM down → tahan, jangan buka posisi.
- **Kill switch** (Auramaur: file `KILL_SWITCH`) dan **cooldown** sebagai warga kelas satu.
- **Validasi tiap order**, baca ulang posisi sebelum retry (Tencent: stale-state pernah
  menyisakan posisi tanpa SL).
- **Jurnal = satu sumber kebenaran** lintas sub-sistem (Tencent); dedupe/exposure/konflik
  semua membacanya.
- **Loop internal untuk trading, cron untuk housekeeping** (backtest ulang, backup harian).

## 8. Yang HARUS dicatat saat mencari profit (disiplin bukti)

1. Setiap klaim profit harus punya sumber berkas (ledger/metrik), bukan narasi.
2. Sampel kecil (< 20 trade) = derau, bukan bukti — tandai dengan jujur.
3. Statistik sadar-korelasi: geser ke klaster per hari/pair; N efektif << jumlah trade.
4. Konservatif selalu menang: bila ragu antara dua tafsir hasil, pilih yang lebih buruk.

---

### Rujukan kode di sistem ini

| Konsep | Lokasi |
|---|---|
| Dompet Rp 10 jt/market | `dompet.py` (`WALLET_IDR`) |
| Exit rule v3 (TP1 50% + BE + runner) | `execution/paper.py` (`tp1_hit_runner`, `_r_penutupan`) |
| Biaya terukur | `execution/costs.py`, `collectors/depth.py` |
| Seleksi strategi + dompet terpisah | `strategi_terpilih.py` |
| Registry status strategi | `pasar.py` (`STRATEGI_PASAR`) |
| Gate risiko | `risk.py`, `execution/keputusan.py` |
| Pakem bukti (n efektif, INSUFFICIENT → TUNING) | `pakem.py` |
