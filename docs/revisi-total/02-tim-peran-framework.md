# 02 — Tim, Peran, dan Framework Kerja

Disusun: 2026-10-09 · Status: **DRAF untuk disetujui owner**

> **Ini dokumen yang menjawab permintaanmu langsung:** *"kalau kamu disuruh buat tim kecil
> untuk ngerjain War Room, kamu hire posisi apa, dan pakai framework kerja apa."*
> Dok 00 memuat ringkasan; dok ini **detail operasionalnya** — apa yang tiap orang
> kerjakan tiap hari, dan artefak apa yang mereka hasilkan.

---

## 1. Cara saya berpikir soal "hire siapa"

Sebelum menyebut jabatan, saya pegang aturan ini:

> **Rekrut berdasarkan konsekuensi, bukan berdasarkan fitur.**

Pertanyaan pemandu: *"kalau orang ini salah, apa yang paling mahal?"* Jawabannya
menentukan urutan rekrut. Untuk War Room:

| Kalau salah di sini… | Yang hilang | Paling mahal? |
|---|---|---|
| Aturan gate/BE | **uang nyata** | ★★★★★ |
| Angka tak bersumber tampil sebagai benar | keputusan salah | ★★★★☆ |
| Live nyala tanpa izin | bencana | ★★★★★ (jarang tapi fatal) |
| Domain rusak saat refactor | 7 hari kerja | ★★★☆☆ |
| Fitur/UI jelek | waktu pengguna | ★☆☆☆☆ |

**Urutan jabarannya = urutan rekrutnya.**

---

## 2. Lima kursi — rinci (bukan sekadar nama jabatan)

### 🪑 Kursi 1 — Quant / Strategy Owner

- **Judul nyata di industri:** Head of Trading Risk / Quant Lead.
- **Tanggung jawab harian:** definisi & pemeliharaan BE, sizing, ambang gate, kebijakan
  paper→live. Menilai apakah sebuah sinyal "layak dieksekusi".
- **Artefak yang dia hasilkan:** `strategy-*.md`, definisi gate, catatan keputusan.
- **Bukti dia bekerja:** `packages/live-trading` (tidak diporting, ADR-001), `gate.py`
  murni, 227 tes domain.
- **Batas keras:** **hanya dia (owner) yang mengubah ambang.** Agen mengusulkan lewat
  `proposals`, tidak pernah `apply` sendiri.
- **Kenapa di sini bukan digabung:** kalau orang yang menulis UI juga yang menetapkan
  ambang uang, akan ada dorongan halus "bikin angkanya lolos". Pemisahan ini = keselamatan.

### 🪑 Kursi 2 — Backend / Platform Engineer

- **Judul nyata:** Backend Engineer (Python/FastAPI).
- **Tanggung jawab harian:** API (`services/api`), worker (`services/worker`), core
  (`packages/core`) — termasuk 21 tabel & migrasi Alembic.
- **Artefak:** endpoint, migrasi, `facts`/`events` yang konsisten.
- **Bukti bekerja:** 50 endpoint, event log append-only, setiap angka punya `fact_id`.
- **Batas keras:** UI tidak menghitung ulang angka domain; backend yang menegakkan.

### 🪑 Kursi 3 — Frontend / Product Engineer

- **Judul nyata:** Product Engineer (frontend-heavy).
- **Tanggung jawab harian:** `apps/web` (SvelteKit) — menyajikan **jawaban cepat**,
  menjaga `catatan_kejujuran`, state kosong `—` bukan `0`, label gross/net & paper/live.
- **Artefak:** halaman, komponen, 36 tes vitest + suite E2E.
- **Bukti bekerja:** positioning "sinyal dulu, bukan bagan dulu" benar-benar terasa.
- **Batas keras:** **tidak boleh mengarang angka**; hanya menampilkan fakta dari API.

### 🪑 Kursi 4 — SRE / Ops

- **Judul nyata:** Site Reliability Engineer.
- **Tanggung jawab harian:** deploy, restart, backup, rollback, pemantauan
  (`services`+`heartbeats`), verifikasi pasca-perubahan.
- **Artefak:** **runbook deploy**, skrip verifikasi, postmortem.
- **Bukti dia dibutuhkan:** **kejadian 8–9 Okt** — War Room 500 total karena build tidak
  diikuti restart. Kursi ini yang menangkap/cegah.
- **Batas keras:** **perubahan produksi butuh izin owner** (terbukti hari ini — saya
  berhenti menunggu izinmu sebelum restart).

### 🪑 Kursi 5 — QA / Verification Engineer

- **Judul nyata:** QA Engineer (adversarial / test-focused).
- **Tanggung jawab harian:** **mencoba membuktikan sistem salah.** Pemilik
  Definition of Done & bukti.
- **Artefak:** suite tes (806 + 36 + 227), E2E, laporan temuan.
- **Bukti dia bekerja (hari ini):** menemukan bahwa (a) angka README salah (761 vs 806),
  (b) tes Komuter **mati total** (tak bisa jalan), (c) "E2E 27 hijau" ternyata **butuh
  sesi yang tak ada**.
- **Batas keras:** verdict **PASS wajib berbukti**; default `NEEDS WORK`.

---

## 3. Yang SENGAJA tidak di-hire — dan kenapa

Ini sama pentingnya dengan daftar di atas. **Tim yang kabur karena terlalu banyak
lebih buruk daripada tim kecil yang tepat.**

| Kandidat | Putusan | Alasan |
|---|---|---|
| Data Scientist / ML Engineer | ❌ sekarang | LLM di sini = **gateway + audit** (ADR-004), bukan riset. Nanti saat backtest serius. |
| DevOps cloud / Kubernetes | ❌ | **1 server.** K8s menambah risiko, bukan mengurangi. |
| Designer UI penuh | ❌ sekarang | Positioning produk sudah diputuskan; desainer penuh baru perlu saat multi-pengguna. |
| Mobile engineer native | ❌ | Web responsif cukup (pengguna SSH + layar kecil). |
| Growth / marketing | ❌ | 1 pengguna, uang pribadi. Nol nilai. |
| Manajer proyek / Scrum Master | ❌ | 5 orang, 1 pemilik. **Owner = Product Owner.** Manajer = lapisan tanpa kerja. |
| Security engineer khusus | ⚠️ nanti | Untuk sekarang: "shared responsibility" (SDLC §3) + review agen. Naik jadi kursi saat ada pengguna lain. |

---

## 4. Framework kerja — tiga lapis, masing-masing untuk masalah berbeda

Bukan satu framework agama. **Tiap lapis menyelesaikan masalah yang berbeda**, dan
lapis ketiga **sudah ada di repo** (tidak saya ganti).

### Lapis 1 — **Shape Up** → untuk *"apa yang dikerjakan"*

**Kenapa bukan Scrum:** Scrum butuh ceremony (standup, sprint review, velocity) yang
memberatkan 5 orang tanpa manfaat untuk **1 pemilik**. Shape Up lebih pas:

| Elemen Shape Up | Penerapan di War Room |
|---|---|
| Fixed time, variable scope | Siklus pendek; kalau lewat batas → **berhenti**, bukan tambal |
| Pitch sebelum kerja | Satu pitch = masalah + batas + solusi kasar + rabbit holes + no-go |
| Betting table | Owner memilih **sedikit** taruhan, bukan backlog tak berujung |
| Circuit breaker | Batas waktu keras per pekerjaan |

**Sudah setengah ada:** `docs/sdlc-war-room.md` §4 "Work item contract" ≈ Pitch.
Kita tinggal pertegas jadi format baku.

### Lapis 2 — **DORA + Google SRE** → untuk *"bagaimana sistem tetap hidup"*

**Kenapa:** kejadian 8–9 Okt adalah **SRE failure klasik** — perubahan (build) tanpa
verifikasi (restart + cek versi). DORA & SRE memberi bahasa & metriknya:

| Konsep | Arti di sini | Aksi konkret |
|---|---|---|
| DORA: change failure rate | Berapa % perubahan bikin masalah | Ukur; kejadian 8 Okt = 1 failure tercatat |
| DORA: MTTR | Lama pemulihan | **Tinggi** — tak ada yang tahu sampai kebetulan diperiksa → perbaiki dengan **alert** |
| SLO / error budget | Target ketersediaan | Web harus 200; budget habis → stop fitur, perbaiki |
| Postmortem tanpa menyalahkan | Belajar dari insiden | Tulis postmortem kejadian 8–9 Okt sebagai contoh pertama |

**Konsekuensi konkret:** setiap deploy = **build + restart + verifikasi** (satu unit),
bukan tiga langkah yang bisa terlupa. Ini masuk **R0**.

### Lapis 3 — **SDLC bergate yang sudah ada** → untuk *"keselamatan"*

Repo sudah punya: `sdlc-war-room.md`, `standar-kerja-war-room-final.md`, **5 ADR terkunci**.
**Ini aset — tidak diganti.** Yang saya usulkan: **formalkan ke 5 kursi.**

| Gate | Kursi pemilik |
|---|---|
| Definition of Ready | Quant + Product |
| Definition of Done | QA |
| Release gate | SRE + Owner |
| Post-change verification | SRE |
| Verdict review (PASS/FAIL) | QA |

---

## 5. Bagaimana 5 kursi ↔ struktur agenmu (pemetaan)

Kamu sudah menjalankan struktur ini tanpa menamainya "tim":

| Kursi manusia | Padanan agen | Batas |
|---|---|---|
| Quant / Risk Owner | **owner (kamu)** | ubah ambang/BE = **hanya manusia** |
| Backend / Platform | agen implementasi (koma, bridge, dll) | tak boleh ubah threshold |
| Frontend / Product | agen implementasi UI | tak boleh mengarang angka |
| SRE / Ops | agen ops | **produksi = butuh izin owner** ✅ |
| QA / Verification | **reviewer** | read-only, verdict PASS/FAIL, default NEEDS WORK |

**Kesimpulan:** sistem agenmu **sudah** sebuah tim 5 kursi. Yang kurang hanya dua hal:
1. **Nama & tanggung jawab tertulis** (dok ini).
2. **Beberapa gate belum ditegakkan otomatis** (mis. verifikasi deploy → R0).

---

## 6. Irama kerja (cadence) yang saya usulkan

| Irama | Aktivitas | Siapa |
|---|---|---|
| **Harian** | Cek `alerts` + `heartbeats`; kalau ada anomali, catat | SRE |
| **Per pekerjaan** | Pitch → kerja → DoD + bukti → verdict | semua |
| **Mingguan** | Tinjau 1 postmortem / temuan QA | QA + Owner |
| **Per siklus (2 minggu)** | Betting table: pilih pekerjaan berikutnya | Owner |
| **Saat insiden** | Pemulihan dulu → postmortem tanpa menyalahkan | SRE → semua |

---

## 7. Pertanyaan terbuka untuk owner

1. **Setuju 5 kursi ini**, atau ada yang mau digabung/ditambah/dihapus?
2. **Lapis framework:** sreg dengan Shape Up + DORA/SRE, atau kamu punya preferensi lain
   (mis. Kanban murni, atau XP)?
3. **Cadence di §6** — apakah "harian cek alert" realistis untukmu, atau mau lebih jarang?
