# ADR-003 — Gate sebagai layanan: satu implementasi `ci_low > BE`

Status: **diterima** · Tanggal: 2026-10-02 · Fase: P0 (implementasi P1-T2)

## Konteks

Aturan gate (`n ≥ 30`, Wilson dua sisi 90%, lolos hanya bila `ci_low > BE`, split data dibekukan
sebelum melihat hasil, hasil grid = "eksplorasi") sekarang hidup sebagai teks di prompt dan
tersebar di beberapa skrip. Dua definisi "lolos" adalah cara paling mudah untuk tidak sengaja
melonggarkan ambang. Proyek Polymarket sudah membuktikan nilainya: contoh 18:56Z dengan
`winPct 89,4%` vs `BE 86,39%`, `ci.lo 86,38` → **gagal** (tidak melonggarkan).

## Keputusan

1. **Satu modul**: `packages/core/gate.py` dengan tanda tangan
   `gate.evaluate({n, win, be, ci=0.90, min_n=30, split}) →
   {verdict: lolos|gagal|insufficient, reason, ci_low, ci_high, required_n}`.
2. **Satu endpoint**: `POST /api/v1/gate/evaluate` memakai fungsi yang sama.
3. **UI, learner, dan CI memakai definisi itu** — tidak ada implementasi kedua.
4. `required_n` dihitung dan **ditampilkan** (GateMeter) supaya "butuh 4–5 hari lagi" jadi angka.
5. `verdict=lolos` **hanya** bila `ci_low > be`. Tanpa `split=frozen:<id>` → `insufficient`.
6. Ambang dan rumus BE **hanya boleh diubah manusia (owner)** — bukan agen, bukan LLM.

## Konsekuensi

- Mengubah definisi gate = mengubah satu berkas + satu tes; efeknya langsung ke UI, learner, CI.
- Hasil eksplorasi (grid search) tidak bisa dipromosikan tanpa sampel baru + split beku; kalau
  dipaksa, gate mengembalikan `insufficient` dengan alasan, bukan `lolos`.
- Semua keputusan gate tercatat di `events` (fakta + alasan), jadi bisa diaudit.

## Alternatif yang ditolak

- **Gate tetap sebagai teks prompt**: LLM tidak boleh memutuskan lolos/tidak; teks tidak bisa diuji.
- **Gate di dalam UI saja**: learner dan CI akan butuh versi lain → kembali ke dua definisi.
- **Gate di dalam skrip backtest saja**: tidak bisa dipakai learner/UI, dan tidak punya endpoint
  untuk ditampilkan sebagai meter bergerak.