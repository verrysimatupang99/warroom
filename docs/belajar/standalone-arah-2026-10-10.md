# Standalone: War Room sebagai pembaca API Tencent vs. memindahkan mesin ke sini

Tanggal: 2026-10-10 · Status: **menunggu keputusan pemilik** (agen tidak memilih sendiri)

## Pertanyaan

Setelah desk Tencent ditiru (crypto/idx/forex) dan War Room di sini bisa menampilkan
gambaran yang sama, muncul dua arah:

1. **Pembaca API** — War Room di sini tetap menampilkan dari fakta lokal, dan *bila perlu*
   menarik angka live dari API publik Tencent (`http://43.155.219.37/...`). Mesin tetap di Tencent.
2. **Pindahkan mesin** — skrip/cron yang menghasilkan data dipindah ke sini, lalu Tencent
   ditinggalkan (atau jadi cadangan). War Room jadi mandiri penuh (standalone).

## Bukti (dibaca apa adanya, tanpa kredensial)

### Yang berjalan di Tencent sekarang

Cron `~/.hermes/cron/jobs.json`: **46 job, 18 aktif**. Semuanya **penulis data / mesin**,
bukan sekadar UI:

| Job | Jadwal | Baris | Jenis |
|---|---|---|---|
| `xauusd_reactive.py` | tiap jam 06–22 Sen–Jum | 970 | mesin forex (XAUUSD) |
| `multi_pair_signal.py` | */30 13–23,0–3 Sen–Jum | 554 | mesin forex (multi-pair) |
| `xauusd_smc_data.py` | 30 14 * * 1-5 | 512 | kolektor data SMC forex |
| `crypto_watch_eval.py` | 5 * * * * | 398 | evaluasi watchlist crypto |
| `crypto_pipeline_collect.py` | 0 */2 * * * | 326 | kolektor pipeline crypto |
| `crypto_auto_exec.py` | 20 */2 * * * | 228 | **eksekutor otomatis crypto** |
| `multipair_digest.py` | 0 8 * * * | 154 | digest multi-pair |
| `whale_series.py` | 7 * * * * | 124 | seri whale (HL) |
| `crypto_outlook_collect.py` | 0 8 * * * | 74 | kolektor outlook crypto |
| `weekly_scan.sh` / `journal_track.sh` / `rc_grader.sh` / `arjum_ws_run.sh` / `hl_whale_*` | berbagai | kecil | pembantu |
| `disk_guard.sh` / `disk_hygiene.sh` | 360m / mingguan | kecil | perawatan host |
| `9f7f77d38730` (prompt LLM) | 0 7 * * 1-5 | — | narasi SMC XAUUSD |

Total ± **2.600 baris skrip Python mesin** + 2 job LLM. Ini **bukan** tampilan — ini
mesin yang mengumpulkan, menilai, dan (untuk crypto) **mengeksekusi**.

### Yang SUDAH ada di sini

- War Room lokal: fakta (`facts`), gate (ADR-003/006), ledger, karantina, uji akurasi,
  panel desk crypto/idx/forex hasil tiru Tencent.
- Eksekusi otomatis crypto **sudah pernah berjalan di Tencent** (`crypto-auto-exec-653`);
  di sini eksekusi live masih NO-GO (gate belum disentuh, `armed=false`).

## Konsekuensi tiap arah

**Arah 1 — Pembaca API (usaha kecil)**
- Butuh: penarik HTTP ke endpoint publik Tencent + peta `endpoint → fakta` (seperti yang
  sudah dipakai intel MCP).
- Untung: cepat, tidak menyentuh mesin/kredensial.
- Rugi: War Room **bergantung pada Tencent hidup**; kalau Tencent mati, desk kehilangan
  angka live. Bukan "standalone" sungguhan. Endpoint publik harus tetap dijaga.
- Catatan: ada nilai "desk" (mis. flow/news crypto) yang di sini belum ada faktanya,
  jadi ini bisa jadi pelengkap, bukan pengganti.

**Arah 2 — Pindahkan mesin (usaha besar)**
- Butuh: memindah ±2.600 baris skrip + 18 jadwal cron + dependensi (websocket, exchange
  API, DB) ke host ini; lalu uji bahwa keluaran identik sebelum mematikan Tencent.
- Untung: benar-benar mandiri; satu tempat untuk mesin + bukti; tidak ada dua sumber kebenaran.
- Rugi: risiko tinggi, butuh waktu, dan **menyentuh kredensial exchange** (MEXC) — yang
  saat ini **tidak boleh diambil**. Tanpa kredensial itu, job eksekusi crypto tidak bisa pindah utuh.
- Hambatan keras: kunci MEXC ada di Tencent (`~/.hermes/mexc_futures.json`). Memindah
  eksekutor berarti memindah/membaca kunci → **di luar izin saat ini**.

## Rekomendasi agen (untuk dipertimbangkan, bukan diputuskan sendiri)

Lakukan **bertahap**, mulai dari yang aman:

1. **Sekarang — Arah 1 sebagai pelengkap**, bukan pengganti: tarik hanya yang *tidak* ada
   di sini (mis. flow/news crypto) lewat endpoint publik, ditandai jelas sumbernya.
   Ini sudah sejalan dengan "amati, tiru, modifikasi".
2. **Lalu — pindahkan mesin yang TIDAK butuh kredensial exchange dulu** (kolektor data,
   digest, whale, perawatan host). Setelah keluaran terbukti sama, matikan di Tencent.
3. **Terakhir — mesin eksekusi crypto** hanya bila pemilik secara eksplisit mengizinkan
   pemindahan kredensial MEXC. Sampai itu, eksekusi tetap di Tencent.

## Yang dibutuhkan dari pemilik

- Pilih arah (1 / 2 / bertahap seperti di atas).
- Bila memilih memindah mesin: izin eksplisit soal kredensial MEXC (boleh dipindah atau tidak).
- Bila memilih pembaca API: izin tetap mengakses endpoint publik Tencent untuk penarikan berkala.
