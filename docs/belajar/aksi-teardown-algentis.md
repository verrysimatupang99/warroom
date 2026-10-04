# Tindak lanjut teardown Algentis — aksi 1 & 3 (4 Okt 2026)

Dasar: keputusan owner menyetujui 3 aksi dari `docs/kompetitor/algentis-2026-10-04.md`.

---

## ✅ Aksi 1 — Kalender makro + gerbang stand-down · SELESAI

| Item | Bukti |
|---|---|
| Collector baru | `packages/live-trading/src/live_trading/collectors/macro.py` |
| Sumber | kalender mingguan ForexFactory (JSON publik, tanpa API key) |
| Diuji live | **79 event** ditarik, cache ditulis `state/cache/macro_calendar.json` |
| Terpasang di snapshot | `bagian.macro` muncul di `state/snapshot.json` |
| Sampai ke War Room | fakta `bagian` di Postgres memuat `macro` (ditulis **08:34:07**) |
| Tes | **8 tes baru**; suite penuh **439 lulus**; ruff bersih |
| Commit | `40ae513` |

**Perilaku gerbang:** `stand_down()` mengembalikan event **High-impact** dalam **60 menit ke depan**
(mata uang USD/EUR/JPY/GBP/AUD/CHF/CAD/CNY). Sengaja hanya melihat ke depan — mencegah entri buta
sebelum rilis, bukan melarang setelah volatilitasnya lewat. Saat ini `stand_down: false`
(High berikutnya: FOMC minutes 7 Okt).

**Disiplin yang dipakai:** cache lokal + fallback ke cache basi **beserta umurnya**, dan kalau
sumber mati tanpa cache → error jujur (bukan nol, bukan `n/a` tanpa jejak).

---

## ✅ Aksi 3 — Halaman Bukti · SELESAI

| Item | Bukti |
|---|---|
| Rute baru | `apps/web/src/routes/bukti/+page.svelte` (+ entri navigasi "Bukti") |
| Isi | gate per venue **apa adanya** dari `/api/v1/gate/evaluate`: n, win rate, break-even, CI bawah/atas, n dibutuhkan, verdict, kebijakan |
| Blok eksplisit | **"Yang TIDAK kami klaim"** + **"Yang akan mengubah verdict"** |
| Prinsip | klien **tidak menghitung ulang** apa pun; setiap angka membawa sumber + umur |
| Verifikasi | `svelte-check` **0 error** (dari 4), build `adapter-node` sukses, `/bukti` **200** di produksi |
| Commit | `b57fcab` |

### Kebetulan yang berguna: 4 bug lama ketemu & diperbaiki
`svelte-check` membongkar cacat yang tidak terlihat sebelumnya:

1. `Block.svelte` dan `MetricTile.svelte` mengirim prop **`sumber`** padahal `FreshnessBadge`
   menerima **`source`** → **sumber tidak pernah tampil** di badge. Ini bukan kosmetik: jejak audit
   yang jadi janji halaman Bukti justru hilang di komponen yang menampilkannya.
2. `client.ts` — `ProposalsPayload` dipakai tapi tidak diimpor (error TypeScript).
3. `ProposalCard.svelte` — `onexec` punya default `null` tapi tipenya tidak menerima `null`.

---

## ✅ Aksi 2 — Distribusi sinyal ke Telegram · SELESAI (4 Okt, lanjutan)

| Item | Bukti |
|---|---|
| Adapter | `services/worker/src/warroom_worker/adapters/signals.py` — baca-saja ledger `verdicts.jsonl`, **tanpa jaringan/kuota** |
| Handler + job | `handler_signal_sync` + `JobSpec signal-sync` (900 s, ttl 6 jam > interval) |
| Alur | ledger → fakta `signal.<pair>` → alert ber-dedupe subjek → Telegram |
| Label jujur | setiap pesan membawa: *kandidat belum-terbukti — gate statistik belum lolos* |
| Uji | 8 tes adapter (**447 lulus**), ruff bersih |
| Uji integrasi DB | fakta + alert + tautan `fact_ids=[10216]` terbentuk, pesan berformat benar → lalu dibersihkan agar tidak spam |
| Transport terbukti | event `alert.sent` → `ok=true transport=telegram` |
| Commit | `7f58f21` |

**Perilaku saat ini:** jendela 6 jam → **0 sinyal** — dan itu **benar**: sinyal lolos terakhir
3 Okt 22:19. Ini justru demonstrasi "signal or silence": kalau tidak ada setup yang lulus, sistem
diam, bukan memaksa sinyal.

Infrastruktur lama yang dipakai ulang (sudah ada sejak awal): `TelegramTransport` +
`/etc/warroom/notifier.env` + dedupe semantik `_alert()` + audit setiap percobaan sebagai `Event`
di DB (sumber kebenaran tetap DB, bukan transport).

**Temuan saat itu (pemicu pekerjaan ini):** mesin sinyal sudah ada sebagai pustaka
(`signals/{agents,engine,gates,smc}.py` — orderflow, whale, sentiment, risk, macro, `collect()`),
tetapi **tidak ada satu job pun yang menulis fakta `signal.*`** — daftar kind di DB hanya
`snapshot, poly.*, gmgn, ai.*, learner`, padahal IA UI sudah menyiapkan
`topikArea.crypto = ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.']` sejak awal.

**Yang dibangun:** job `signal-sync` **membaca** ledger `verdicts.jsonl` yang sudah ditulis job
`collect` (`lt scan`) — jadi tidak ada panggilan jaringan baru dan tidak ada kuota tambahan —
lalu menerbitkan fakta `signal.<pair>` dan mengabarkan yang lolos lewat alert ber-dedupe subjek.
Catatan desain: mesin sinyal sendiri sudah menandai bahwa *confluence tidak dipakai sebagai gate*
(pelajaran studi 6-agen) — jadi kita **tidak** menambah agen demi keyakinan.

⚠️ **Batas yang mengikat:** sesuai temuan teardown dan gate yang masih `NOT_PROVEN`, sinyal
dikirim sebagai **kandidat + alasan**, dilabeli belum terbukti — **bukan** ajakan beli. Kita tidak
boleh meniru pola "bukti tidak terverifikasi" yang justru jadi kelemahan kompetitor.

---

## 🔧 Perbaikan penting di luar 3 aksi: merge F3 baru setengah jalan

Saat memverifikasi Aksi 1, ketemu masalah nyata: **`bagian.macro` tidak muncul** di War Room
walau kodenya sudah di repo.

**Sebabnya:** cutover F3 sebelumnya hanya mengalihkan unit `warroom-*`; **4 unit `live-trading-*`
masih menjalankan kode dari copy lama** (`/home/admin/live-trading/.venv`). Jadi ada **dua salinan
kode** dan perubahan baru tidak sampai ke produsen snapshot.

**Perbaikan (sudah dijalankan):**

| Unit | Sebelum | Sesudah |
|---|---|---|
| snapshot · collect · dashboard · watchdog | `/home/admin/live-trading/.venv/…`, WorkingDirectory lama | `/home/admin/warroom/.venv/…`, WorkingDirectory `/home/admin/warroom` |

`LT_HOME=/home/admin/live-trading` **tetap** → state tidak pindah.
`live-trading-backup` dibiarkan (skrip shell, tidak meng-import kode).
Backup unit asli: `/root/unit-backup-20261004/`.

**Bukti sesudah perbaikan:** `live-trading-snapshot` → `Result=success`, `ExecMainStatus=0`;
snapshot memuat `macro`; dash `:8799` **200**; publik **200**; `/bukti` **200**; **0 unit failed**.
Kini **satu salinan kode** melayani semuanya.

---

## 🎨 UI/UX yang layak diambil dari mereka (belum dikerjakan)

Dipilih sebagai **pola desain**, bukan menyalin aset/kode (itu hak cipta):

1. **Judul hero satu kalimat yang menegaskan sikap** ("the signal that knows when to stay silent").
   Padanan kita: kejujuran gate sebagai sikap, bukan sekadar fitur.
2. **Feed yang memperlihatkan proses, bukan hanya hasil** — termasuk baris **SKIP + alasannya**.
   Kita sudah punya bahan (event log, alasan gate); tinggal disajikan.
3. **Blok "honest limits" yang eksplisit** — mereka menulis batas di halaman produk. Halaman
   Bukti kita sudah memuatnya; layak diangkat ke halaman depan.
4. **Tipografi & disiplin warna:** mereka memakai satu keluarga display + satu sans + satu mono
   dengan kontras tinggi. Rumah kita sudah punya token (`angka`, `label-mikro`); tinggal dijaga.
5. **Halaman edukasi sebagai mesin SEO + kredibilitas** — 12 panduan. Murah dibuat, dan kita punya
   bahan asli (gate, biaya, disiplin) yang lebih jujur daripada kebanyakan konten sejenis.
