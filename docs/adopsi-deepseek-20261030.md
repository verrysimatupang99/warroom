# Adopsi dari DeepSeek — 30 Okt 2026

Empat hal yang diambil dari ekspor chat DeepSeek dan sudah diterapkan ke War Room.
Yang diambil adalah **disiplin dan alat**, bukan strategi tradingnya.

## 1. Versioning strategi + jurnal tidak di-reset

**Masalah di DeepSeek:** jurnal di-reset 21 Sep dan 9 Okt; aturan PD/TP/BE berubah
berkali-kali tanpa label versi. Angka lama dan baru tidak bisa dibandingkan.

**Yang diterapkan:**
- `Settings.config_fingerprint()` — hash 12 karakter dari parameter risiko/strategi
  yang relevan (daily loss, max posisi, risk %, ATR/TP, bench, harian).
- Setiap baris `verdicts.jsonl` membawa `strategy_version` (sidik konfigurasi).
- `measure` meneruskan versi ke `outcomes.jsonl`; signal-sync meneruskannya ke fakta.
- Jurnal sinyal mengelompokkan hasil `per_versi`; UI menampilkan versi + WR/net.
- EA `POST /mt5/deal` menerima `strategy_version` opsional (default `unknown` sampai
  EA v3.2 mengirimnya).

**Batas:** 450 sinyal lama tetap berlabel `legacy` karena verdict-nya belum punya field
versi. Versi baru berlaku untuk verdict setelah deploy ini. Jurnal **tidak** di-reset.

## 2. Correction log append-only

**Masalah di DeepSeek:** BE dikoreksi menjadi SL di chat; tidak ada jejak perubahan data.

**Yang diterapkan:**
- `/var/lib/warroom/deal_corrections.csv` (ts, ticket, field, old, new, reason, source).
- `warroom_core.deal_koreksi` menerapkan koreksi terbaru per (ticket, field) tanpa
  mengubah baris `deals.csv`; baris hasil menyimpan `_koreksi`.
- Dipakai jurnal API, tracker DoD, dan rekonsiliasi statement.
- CLI: `tools/koreksi_deal.py --ticket … --field net --new … --reason …`.

**Bukti:** fixture ticket 9001 net 8.50 → koreksi 9.50; tracker mencetak net $9.50,
baris asli tetap 8.50.

## 3. Job-health watchdog

**Masalah di DeepSeek:** 124 respons cron, mayoritas gagal (crypto-morning 54/60,
xauusd-morning 47/53); tidak ada alarm.

**Yang diterapkan:**
- Job `job-health` tiap 5 menit.
- Alert `job/<nama>` bila status terakhir `gagal` atau `last_run_at` lebih tua dari
  3× interval (minimum 15 menit); job nonaktif diabaikan.
- Auto-ack saat job kembali ok dan tepat waktu.

**Bukti live:** `diperiksa=32 alert=0 pulih=0` setelah deploy.
Tes: job gagal/stale memicu 2 alert; pemulihan menutup alert; dedupe bekerja.

## 4. Monte Carlo bootstrap

**Masalah di DeepSeek:** bootstrap 10.000× dipakai untuk P(profit)/drawdown; War Room
hanya punya satu jalur equity.

**Yang diterapkan:**
- `warroom_core.montecarlo.bootstrap` — resample R dengan pengembalian, `seed` tetap.
- Job `jurnal-sinyal` menghitung MC dari `r_net` trade terisi dan menyimpannya di
  `jurnal_sinyal.json` + fakta + UI.
- Output: P(profit), total R P5/P50/P95, max drawdown P95.

**Bukti live (450 sinyal, 334 terisi, net fee 5 bps):**
`P(profit)=96,8%`, total R P5/P50/P95 = `+3,97 / +33,17 / +61,92`,
DD95 = `21,17R`.

## Yang tidak diambil

- Parsing R dari teks bebas (penyebab `closed_SL` terbaca +1R).
- Reset jurnal saat ganti strategi.
- Backtest in-sample sebagai bukti live.
- Leverage 100x pada sinyal vendor.

## Tes & status

- `packages/core/tests/test_deal_koreksi.py` (4)
- `packages/core/tests/test_montecarlo.py` (4)
- `packages/core/tests/test_forwardtest.py` (+1 koreksi)
- `packages/live-trading/tests/test_config.py` (+1 fingerprint)
- `services/worker/tests/test_job_health.py` (2)
- UI: `JurnalSinyal.test.ts` (MC + versi)
- Suite: **912** perintah AGENTS, **1126** root pytest, 72 vitest, 50 e2e.
