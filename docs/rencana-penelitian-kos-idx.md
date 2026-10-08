# Rencana Penelitian King of Scalper untuk War Room

**Status:** proposed research-only
**Tanggal:** 8 Oktober 2026
**Owner keputusan:** user
**Execution mode:** research / paper evidence only
**Production promotion:** blocked until owner approval and statistical gates pass

## Keputusan

Materi `/tmp/warroom-materi/` tidak dimasukkan langsung ke produksi. Sepuluh formula King of Scalper diperlakukan sebagai kandidat strategi IDX scalping yang harus diuji terhadap arsip data yang sudah tersedia.

Materi Axiom, DexScreener, SIPD, dan ebook bonus tetap menjadi referensi operasional atau arsip; tidak menjadi sumber signal baru tanpa spesifikasi dan bukti yang terukur.

## Tujuan penelitian

Menjawab satu pertanyaan:

> Apakah formula King of Scalper menambah informasi di atas bandarmologi War Room yang sudah ada, setelah biaya, gap, dan aturan eksekusi dihitung secara walk-forward?

Hasil yang mungkin:

- **Tidak menambah informasi:** dibuang atau disimpan sebagai referensi.
- **Menambah informasi tetapi belum cukup bukti:** tetap research-only.
- **Lolos evidence gate:** masuk paper shadow untuk observasi tambahan.
- **Lolos paper shadow dan keputusan owner:** baru dipertimbangkan untuk jalur operasional; bukan otomatis live.

## Kandidat yang diuji

1. Bandar Blitz
2. Flash Cuan
3. Gorilla Punch
4. Nitro Push
5. Pump Hunter
6. Precision Hit
7. Rocket Scalper
8. Shadow Entry
9. Spike Ride
10. Tiger Jump

Formula harus disimpan sebagai konfigurasi/metadata evaluator, bukan langsung sebagai signal production.

## Sumber data

- Arsip tick IDX yang sudah tersedia di environment War Room.
- Granularitas 1 menit dan 5 menit sesuai formula.
- Daily bars hanya bila formula memang membutuhkan daily context.
- Tidak menambah panggilan API eksternal selama tahap pertama.
- Sumber, periode, hash, dan timezone wajib dicatat.

## Prosedur wajib

### Fase 1 — Translasi formula

- Terjemahkan setiap formula ke fungsi deterministik.
- Tandai field yang tidak tersedia atau definisinya ambigu.
- Jangan menebak threshold yang tidak terbaca dari OCR.
- Formula dengan input ambigu diberi status `blocked_spec`.

### Fase 2 — Dataset dan split

- Bekukan dataset sebelum melihat hasil.
- Gunakan `split=frozen:<id>` yang tercatat di database.
- Pastikan outcome tersedia.
- Catat periode train/validation/test atau walk-forward windows.
- Simpan manifest dan hash.

### Fase 3 — Replay/evaluator

Untuk setiap kandidat, hitung:

- sinyal generated,
- fill assumption,
- entry,
- stop,
- target,
- exit reason,
- biaya,
- slippage,
- gap loss,
- R per trade,
- status no-fill/cancelled/invalid.

Tidak boleh hanya menghitung win rate dari sinyal yang terlihat bagus.

### Fase 4 — Perbandingan baseline

Bandingkan setiap formula dengan:

- bandarmologi skor 0–100 saat ini,
- baseline IDX yang relevan,
- setup ARA/BSJP/INTRADAY bila horizon-nya sebanding.

Perbandingan hanya sah bila timeframe, population, cost policy, dan exit policy sama.

### Fase 5 — Evidence gate

Per kandidat tampilkan:

- `n` trade tuntas,
- jumlah hari efektif,
- win rate,
- mean R,
- total R,
- CI lower bound,
- break-even,
- deff,
- max drawdown,
- worst loss,
- biaya tercatat atau bruto,
- split id,
- sumber data.

Status evidence mengikuti pakem War Room:

- `INSUFFICIENT`
- `DIRECTIONAL`
- `PRELIMINARY`
- `TUNING`

Tidak ada status `promotable` tanpa split beku, evidence memadai, expectancy positif, dan tidak ada model breach.

## Acceptance criteria

Penelitian dianggap selesai bila:

- 10 kandidat memiliki status eksplisit: `tested`, `blocked_spec`, atau `not_available`.
- Tidak ada angka yang berasal dari threshold OCR yang ditebak.
- Dataset dan split dapat direproduksi dari hash.
- Baseline memakai definisi yang sama.
- Biaya, slippage, no-fill, dan gap dicatat.
- Hasil negatif tetap ditampilkan.
- Tidak ada kandidat yang otomatis masuk production signal.
- Report berisi rekomendasi `discard`, `keep research`, atau `paper shadow` per kandidat.

## Yang tidak dilakukan

- Tidak mengubah threshold owner.
- Tidak mengubah BE policy.
- Tidak membuka live gate.
- Tidak menulis ke Tencent.
- Tidak menambah collector API.
- Tidak menyalin PDF berhak cipta ke repo.
- Tidak menampilkan klaim `high win-rate` tanpa evidence.

## Deliverables

1. `kos_rules.yaml` atau format konfigurasi setara untuk formula yang sudah tervalidasi spesifikasinya.
2. Evaluator/replay research-only.
3. Dataset manifest dan frozen split record.
4. Report per kandidat.
5. Baseline comparison.
6. Owner decision memo: discard / keep research / paper shadow.

## Prioritas

Ini adalah backlog research **P2**, bukan blocker untuk operasi dashboard. P0/P1 tetap lebih penting:

1. source health state,
2. candidate/evaluated/open/closed state separation,
3. authenticated RBAC/IDOR/SSE QA,
4. baru penelitian King of Scalper.
