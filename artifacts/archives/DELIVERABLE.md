# DELIVERABLE — Tinjauan Jalur Eksekusi Paper (open / evaluate / close)

**Peran:** Trading Systems / Execution Engineer · **Tanggal:** 5 Okt 2026
**Repo ditinjau:** `/home/admin/warroom` — **BACA-SAJA, tidak diubah** (bukti di bagian E)
**Output (semua di direktori kerja `/home/admin`):**

| Berkas | Isi |
|---|---|
| `DELIVERABLE.md` | ini (salinan identik: `DELIVERABLE-paper-eksekusi.md`) |
| `proposal.patch` | patch perbaikan — **belum diterapkan** |
| `test_paper_runner_regression.py` | 8 tes regresi |
| `repro_paper_runner.py`, `repro_paper_partial.py` | skrip reproduksi risiko |
| `patched/live_trading/execution/paper.py`, `patched/jobs.py` | salinan kerja tempat patch diuji |
| `applytest/` | sandbox bukti `git apply` berhasil |
| `DELIVERABLE-qa-cakupan-arsip.md` | isi `DELIVERABLE.md` milik tugas lain, diarsipkan utuh (md5 identik — tidak ada yang dihapus) |

---

## A. RISIKO + BUKTI

### Satu risiko: **runner TP1 yang sudah di-break-even tidak pernah bisa ditutup — `close_position` melempar `ValueError`, `evaluate` berhenti di tengah loop**

Mekanisme (semua pada kode apa adanya):

1. Saat TP1 kena, `evaluate()` **meng-overwrite `stop`** posisi ke break-even:
   `paper.py:189-192` → `p.stop = compute_be_stop(...)`; dengan `net_be=True`
   (persis yang dipakai worker: `jobs.py:722` `b_crypto.evaluate(prices, net_be=True)`),
   untuk LONG entry=100 `stop` jadi **100.1 — di *atas* entry**.
2. Penutupan menghitung R dari `stop` yang sudah dimutasi:
   `paper.py:149` `r = compute_r(target.direction, target.entry, target.stop, exit_price)`.
3. `compute_r` (`paper.py:33-36`) **melempar** `ValueError("stop harus di sisi yang benar…")`
   begitu `risk = entry - stop <= 0` — dan untuk runner risikonya memang 0/negatif.
4. Exception keluar dari `evaluate` → `handler_paper_eval` gagal **sebelum** loop
   Alert/Event (`jobs.py:725-745`). `run_one` (`schedule.py:262-266`) menangkapnya →
   job `paper-eval` berstatus `gagal`, tapi **tidak ada yang memperbaiki posisinya**.

**Akibat langsung: runner tak pernah bisa ditutup — kena SL di break-even maupun
melaju ke TP2, dua-duanya melempar.**

### Bukti 1 — traceback reproduksi (`repro_paper_runner.py`, dijalankan ulang 10:36 UTC)

```
[1] dibuka: #SIG7F2F865D entry=100.0 stop=95.0 tp1=105.0
[2] TP1: closed=[] status=tp1_hit_runner stop_baru=100.1
[3] evaluate saat harga = 100.0 (<= stop BE 100.1):
    ValueError: stop harus di sisi yang benar (long: stop < entry, short: stop > entry)
      File ".../live_trading/execution/paper.py", line 186, in evaluate
        closed.append(self.close_position(p.signal_id, p.stop, "closed_SL"))
      File ".../live_trading/execution/paper.py", line 149, in close_position
        r = compute_r(target.direction, target.entry, target.stop, exit_price)
      File ".../live_trading/execution/paper.py", line 36, in compute_r
        raise ValueError("stop harus di sisi yang benar ...")
[4] posisi di file setelah evaluasi gagal: 1 -> [('#SIG7F2F865D', 'tp1_hit_runner', 100.1)]
[5] ledger baris: 0 (harusnya 1 closed_SL)
[6] evaluate saat harga = 120.0 (>= tp2 110):
    ValueError: stop harus di sisi yang benar ...      <-- jalur TP2 pun ikut crash
```

### Bukti 2 — partial write: ledger vs notifikasi tidak sinkron (`repro_paper_partial.py`)

Urutan dalam loop: posisi A (ETH, kena SL) diproses **sebelum** runner B (SOL).

```
[3] evaluate(ETH=94 -> SL, SOL=100 -> BE SL):  ValueError ... (dari B)
[4] ledger: ['ETHUSDT:closed_SL']
    posisi sisa: [('SOLUSDT', 'tp1_hit_runner', 100.1)]
```

Artinya pada satu tick `paper-eval`:

- ETH **sudah tertutup** di ledger **dan hilang dari file posisi** (tulisan berlangsung
  per posisi: `close_position` → `_append_ledger` + `_save`),
- tetapi exception dari B membuat `handler_paper_eval` melempar **sebelum** loop
  `_alert(...)` / `s.add(Event(type="trade.closed", ...))` (`jobs.py:725-745`) berjalan
  → **tidak ada Alert Telegram, tidak ada Event SSE**, job berstatus `gagal`,
- posisi yang urutannya **setelah** runner tidak pernah dievaluasi sama sekali.

### Dampak yang mengikuti (konsekuensi langsung dari kode di atas, bukan spekulasi)

- `paper-eval` **gagal terus setiap tick** selama runner nyangkut; setiap kegagalan juga
  berarti SL/TP posisi lain tidak diperiksa pada tick itu.
- Runner menempati slot `max_concurrent_positions = 3` (`config.py:49`) **selamanya**,
  dan `RiskGate.check` memblokir pair yang sama (`risk.py`: `"{pair} sudah punya posisi terbuka"`),
  sehingga scanner makin lama makin terhambat.
- Buku kas (ledger) kehilangan trade runner → `daily_r` / batas rugi harian dihitung dari
  data tidak lengkap (padahal `RiskGate` justru dibuat ketat soal integritas ledger).

### Konfirmasi: tes yang ada tidak pernah menyentuh kasus ini

`packages/live-trading/tests/test_paper.py` hanya menguji *pembuatan* runner
(`test_tp1_digeser_ke_break_even_bukan_ditutup:65`, `test_tp1_digeser_ke_net_break_even_mexc:89`)
— **tidak ada satu pun tes yang menutup runner setelah TP1**. CLI juga rentan:
`cli.py:322` memanggil `b.evaluate(prices)` dengan `net_be=False` → `stop = entry`
→ `risk = 0` → `ValueError` yang sama.

---

## B. SKENARIO PEMICU

Skenario normal, bukan tepi langka:

1. **Tik `paper-scan`** → `handler_paper_scan` (`jobs.py:761`) membuka posisi paper
   (mis. SOLUSDT LONG entry 100 / SL 95 / TP1 105 / TP2 110) setelah lolos `RiskGate`.
2. **Tik `paper-eval` berikutnya** → harga ≥ 105 → TP1 kena → posisi jadi
   `tp1_hit_runner`, `stop` digeser ke **100.1** (`net_be=True`) → file disimpan, aman.
3. **Tik berikutnya, harga pullback wajar** (100.0 ≤ 100.1) → `hit_sl` →
   `close_position(..., p.stop, "closed_SL")` → **`ValueError`**.
   *Varian identik:* harga justru terbang ke 120 → `hit_tp2` → `close_position` di `tp2`
   → **`ValueError` juga** (bukti [6]).
4. Kondisi ini **laminating**: runner tidak bisa ditutup oleh mekanisme apa pun,
   sehingga `paper-eval` gagal setiap tick sampai intervensi manual.

Dipercepat oleh dua hal: `net_be=True` (worker) **maupun** `net_be=False` (`lt eval`)
sama-sama menghasilkan stop di sisi entry → dua-duanya melempar; dan nilai `stop` asli
sebelum patch **tidak disimpan di mana pun** di file posisi → tidak ada jalur pemulihan
lewat kode.

---

## C. USULAN PERBAIKAN + PATCH

**Akar masalah:** `compute_r` dipakai untuk dua pekerjaan yang bertentangan —
*validasi sisi stop saat open* (memang harus ketat) dan *hitungan R saat close*
(yang sah-sah saja berhadapan dengan stop yang sudah digeser ke break-even).

`proposal.patch` (2 berkas, 9 hunk) berisi:

1. **`PaperPosition.stop_init: float = 0.0`** — menyimpan stop asli saat open;
   `open_position` mengisinya. R exit selamanya dihitung dari **risiko awal**
   (kasus di atas: `(100.1−100)/(100−95) = +0.02R`, bukan crash).
2. **`compute_r_exit(pos, exit_price)`** — dipakai `close_position`, **tidak pernah melempar**:
   bila risiko awal tidak tersedia (posisi lama tanpa `stop_init`, stop sudah di BE)
   hasilnya `0.0` — exit break-even memang ≈ 0R. `compute_r` tetap ketat dan tetap
   penjaga validasi saat open (dibuktikan `test_validasi_open_masih_ketat`).
3. **Isolasi error per posisi di `evaluate`** — posisi rusak/korup dicatat ke
   `broker.errors`, tetap disimpan, **posisi lain tetap dievaluasi** (pertahanan lapis
   kedua; kasus bukti-2 di atas tidak lagi kehilangan Alert/Event).
4. **`handler_paper_eval` menyalurkan `broker.errors`** ke detail job
   (`GAGAL <signal_id> ...`) supaya kegagalan per posisi terlihat di `Event job.ran`
   / UI, bukan hilang.

**Status patch: BELUM diterapkan.** Repo tetap baca-saja.

Verifikasi yang sudah dijalankan (di sandbox `applytest/`, bukan di repo):

```
git apply --check /home/admin/proposal.patch   -> CHECK-OK
git apply /home/admin/proposal.patch           -> APPLY-OK
diff hasil apply vs patched/…                  -> IDENTIK-DENGAN-PATCHED
```

Cara menerapkan nanti (setelah review):

```
cd /home/admin/warroom && git apply --check /home/admin/proposal.patch && git apply /home/admin/proposal.patch
```

**Compat / rollback:**

- File positions lama (tanpa `stop_init`) tetap terbaca — field baru punya default
  (dibuktikan `test_file_positions_lama_tanpa_stop_init`).
- **Rollback perlu hati-hati:** file yang sudah berisi `stop_init` tidak bisa dibaca
  kode lama (`PaperPosition(**p)` → `TypeError`) — strip field dulu sebelum mundur.
- Runner lama yang sudah nyangkut sebelum patch: `stop_init` tidak ada → R exit = `0.0`
  (semantik break-even, akurat untuk kasus SL-BE; untuk runner yang ditutup di TP2
  R-nya jadi kurang-tinggi). Opsional: backfill `stop_init` dari payload Event
  `trade.opened` (berisi `to_dict()` posisi saat open, termasuk `stop` asli).

---

## D. TES REGRESI

Berkas: `/home/admin/test_paper_runner_regression.py` (8 tes).

| # | Tes | Yang dijaga |
|---|---|---|
| 1 | `test_module_yang_dimuat` | cegah lulus palsu (modul yang diimport memang yang dituju) |
| 2 | `test_runner_be_stop_long_dapat_ditutup` | **inti**: runner LONG kena SL di net BE → `closed_SL`, R +0.02, file bersih, ledger 1 baris |
| 3 | `test_runner_be_stop_short_dapat_ditutup` | arah SHORT sama |
| 4 | `test_runner_tp2_dapat_ditutup` | runner yang melaju ke TP2 ikut tertutup, R dihitung dari risiko awal |
| 5 | `test_posisi_rusak_tidak_menghentikan_evaluasi_lain` | 1 baris korup → posisi sehat tetap dievaluasi, korup tidak hilang, error dilaporkan |
| 6 | `test_file_positions_lama_tanpa_stop_init` | kompatibilitas file lama, R = 0.0 untuk BE |
| 7 | `test_validasi_open_masih_ketat` | patch tidak melunakkan validasi saat open |
| 8 | `test_open_positions_menyimpan_stop_init` | stop asli ikut tersimpan |

Hasil eksekusi nyata (dijalankan ulang setelah patch dibangun ulang):

```
# terhadap KODE DASAR (repo, tanpa patch) — harus gagal:
6 failed, 2 passed
  FAILED test_runner_be_stop_long_dapat_ditutup
  FAILED test_runner_be_stop_short_dapat_ditutup
  FAILED test_runner_tp2_dapat_ditutup - ValueError: stop harus di sisi yang benar ...
  FAILED test_posisi_rusak_tidak_menghentikan_evaluasi_lain
  FAILED test_file_positions_lama_tanpa_stop_init
  FAILED test_open_positions_menyimpan_stop_init   (KeyError: 'stop_init')
  (2 yang lulus = tes yang memang di luar risiko ini)

# terhadap PATCH (PAPER_SRC=/home/admin/patched):
8 passed

# suite lama terhadap PATCH (repo tidak diubah):
pytest .../packages/live-trading/tests/test_paper.py  ->  10 passed
```

Perintah:

```
cd /home/admin
/home/admin/warroom/.venv/bin/pytest -q -p no:cacheprovider test_paper_runner_regression.py
PAPER_SRC=/home/admin/patched /home/admin/warroom/.venv/bin/pytest -q -p no:cacheprovider test_paper_runner_regression.py
PAPER_SRC=/home/admin/patched PYTHONDONTWRITEBYTECODE=1 /home/admin/warroom/.venv/bin/pytest -q -p no:cacheprovider \
    /home/admin/warroom/packages/live-trading/tests/test_paper.py
```

Reproduksi risiko (tanpa patch):

```
/home/admin/warroom/.venv/bin/python /home/admin/repro_paper_runner.py
/home/admin/warroom/.venv/bin/python /home/admin/repro_paper_partial.py
```

---

## E. KEPATUHAN ATURAN + VERIFIKASI

- Repo dibaca saja: `git -C /home/admin/warroom status --porcelain` → **bersih (tidak ada output)**.
- Tidak ada tulisan baru ke repo: `find packages/live-trading services/worker -name '*.pyc' -newermt '-2 hours'`
  → **kosong**; seluruh repro/test menulis state ke `tmp_path`/`tempfile` di luar repo.
- Tidak ada `git commit/push`, tidak ada `systemctl`, tidak ada perubahan `/etc`,
  tidak ada state runtime yang disentuh, **tidak ada endpoint LLM yang dipanggil**
  (reproduksi murni lokal; `handler_paper_eval` tidak pernah dijalankan terhadap bursa).
- Tidak ada nilai kredensial yang dicetak.
- Semua keluaran berada di direktori kerja `/home/admin`.

**Sisa pekerjaan (jujur):** patch baru diuji pada salinan (`patched/`) plus suite lama
lewat override path — belum dijalankan terhadap repo asli karena repo baca-saja;
penerapan, pengecekan `ruff`, dan backfill `stop_init` runner lama belum dilakukan.
Catatan: beberapa berkas hasil sempat terhapus oleh proses lain di direktori ini
(patch, skrip repro, tes ditulis ulang dan diverifikasi ulang sebelum laporan ini
ditutup) — karenanya `DELIVERABLE.md` juga disalin ke `DELIVERABLE-paper-eksekusi.md`.

---

## F. RISIKO SEKUNDER YANG TERAMATI (di luar satu risiko utama — **tidak ditambal**)

Dicatat supaya tidak hilang, tapi sengaja tidak dicampur ke patch agar review tetap fokus:

1. **Race antar proses pada file positions.** `_save` (`paper.py:94-99`) memakai nama
   `.tmp` tetap + read-modify-write **tanpa lock**, sedangkan `lt` (CLI) bisa jalan
   bersamaan dengan worker → lost update: posisi yang baru dibuka bisa tertimpa dan
   hilang (atau kebalikannya). `RiskGate` punya `acquire_executor_lock`, tetapi
   `PaperBroker` tidak memakainya.
2. **Urutan tulis ledger → file posisi.** `close_position` meng-append ledger dulu
   (`paper.py:160-161`); proses mati di antaranya membuat close tercatat di ledger
   sementara posisi masih `open` → bisa ditutup dua kali (R dihitung dobel).
3. **Harga tanpa stempel waktu.** `handler_paper_eval` mengambil harga per pair
   (`jobs.py:717-721`) lalu memakainya apa adanya; pair yang gagal di-fetch **dilewati
   diam-diam**, dan harga pair pertama bisa sudah basi saat menilai pair terakhir →
   perbandingan SL/TP terhadap harga tua/parsial.
