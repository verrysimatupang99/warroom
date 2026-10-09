# War Room — Revisi Total: dari Tim & Peran sampai Rencana Implementasi

Disusun: 2026-10-09 · Status: **DRAF untuk disetujui owner**
Sifat: dokumen pra-perencanaan (bukan kode). Tidak mengubah apa pun di produksi.

---

## 0. Cara membaca dokumen ini

Kamu minta: revisi total War Room dari tahap pra-perencanaan (ERD/model data, arsitektur)
sampai rencana implementasi — dengan analogi **"kalau kamu disuruh bikin tim kecil untuk
proyek ini, kamu hire posisi apa, dan pakai framework kerja apa."**

Jadi dokumen ini disusun **berbalik dari kebiasaan**. Bukan "mulai dari diagram", tapi:

1. **Proyek ini sebenarnya apa** (fakta terverifikasi dari repo, bukan asumsi).
2. **Kalau jadi proyek nyata dengan tim manusia, siapa saja yang dibutuhkan** — dan
   *kenapa* posisi itu, bukan yang lain.
3. Dari kebutuhan peran itu → **model data (ERD)** yang muncul secara alami.
4. Dari model data → **arsitektur**.
5. Dari semua itu → **rencana implementasi berurut** dengan gate.

> **Aturan penulisan (mengikuti AGENTS.md repo ini):** setiap angka punya sumber yang bisa
> dijalankan ulang. Klaim tanpa bukti ditandai `[asumsi]` atau `[belum-verifikasi]`.
> Tidak ada angka yang saya karang.

---

## 1. Apa proyek ini, sebenarnya (fakta terverifikasi)

Semua ini saya baca langsung dari `/home/admin/warroom` pada 2026-10-09:

| Fakta | Nilai | Sumber |
|---|---|---|
| Umur repo | 2–9 Okt 2026, **193 commit** | `git rev-list --count HEAD` |
| Tes Python | **806** (0 gagal) | `pytest --collect-only` |
| Tes web | **36** (9 berkas, 0 gagal) | `vitest run` |
| Domain live-trading | **227** tes | `~/live-trading` |
| Endpoint API | **50** | `contracts/openapi.json` |
| Pasar yang dicakup | **7**: crypto, Polymarket, meme coin (gmgn), forex, IDX, + ringkas | `services/api` |
| Layanan | 4: `api`, `worker`, `llm`, `notifier` | `services/` |
| Paket | 2: `core`, `live-trading` (domain asli, dipertahankan) | `packages/` |
| ADR terkunci | **5** (0001 stack … 0005 event-log) | `docs/adr/` |
| Pengguna nyata | **1** — owner/operator, kerja lewat SSH + Telegram | `PRODUCT.md` |
| Status live | **NO-GO** (keputusan owner 3 Okt) | `docs/checklist-go-nogo-live.md` |

**Yang penting dipahami:** ini **bukan** startup dengan banyak pengguna. Ini
**sistem pribadi satu operator** yang menangani **uang nyata** di 7 pasar, dengan
**batas keselamatan sebagai fitur utama** (gate, `ci_low > BE`, paper/live terpisah).

> Ini mengubah segalanya soal "tim". Proyek dengan 1 pengguna tetap butuh **disiplin
> tim engineering kelas produksi**, karena konsekuensi salah = kehilangan uang, bukan
> sekadar bug UI yang bikin malu.

---

## 2. Analogi inti: tim kecil untuk War Room

Kalau saya diberi mandat membangun War Room sebagai produk dengan **tim manusia kecil**
(bukan 1 orang serba bisa), dan anggaran tenaga terbatas, ini yang saya lakukan.

### 2.1 Prinsip perekrutan: "hire untuk risiko, bukan untuk fitur"

Kesalahan umum: merekrut berdasarkan fitur ("butuh yang bisa bikin chart"). Cara benar:
**rekrut berdasarkan apa yang paling mahal kalau salah.** Untuk War Room, urutan risiko
dari yang paling mahal:

1. **Salah hitung gate/BE → uang hilang nyata.** (Paling mahal.)
2. **Data palsu/stale tampil seolah benar → keputusan salah.** (Bukti historis: klaim
   `$8,62` palsu vs saldo on-chain `0,000000` — ADA di ADR-005.)
3. **Live nyala tanpa izin → bencana total.**
4. **Domain logic rusak saat refactor → 7 hari kerja hilang.**
5. Fitur baru / UI cantik → paling murah kalau salah.

**Karena itu, saya hire dari atas ke bawah risiko ini.**

### 2.2 Lima kursi (dan kenapa hanya lima)

Saya sengaja **tidak** membuat tim 12 orang. Alasannya: untuk 1 pengguna dan 7 pasar,
komunikasi antar-orang jauh lebih mahal daripada kerja teknisnya. Lima kursi ini
menutup semua risiko di 2.1 tanpa overhead.

---

#### Kursi 1 — **Quant/Strategy Owner (domain risk)** — *hire pertama*

**Peran:** pemilik aturan uang. Definisi BE, sizing, ambang gate, kapan paper→live.
**Kenapa ada:** risiko #1 & #2. Tidak ada orang lain yang boleh mengubah ambang.
Di proyek nyata: setara *Head of Trading Risk*.
**Di sistem ini diwujudkan sebagai:** `packages/live-trading` — domain yang **tidak
diporting** (ADR-001), dan `gate.py` yang **murni** (tanpa I/O, tanpa DB, tanpa LLM).
**Batas keras:** agen boleh *mengusulkan*; hanya manusia yang mengubah (`locked`/`bounds`).

#### Kursi 2 — **Backend/Platform Engineer** — *hire kedua*

**Peran:** mengubah aturan domain jadi layanan yang bisa dipercaya (API, worker, event log).
**Kenapa ada:** risiko #2 & #4. Orang yang memastikan **setiap angka punya `fact_id`**
(ADR-005) dan **tidak ada yang hilang** saat sistem tumbuh.
**Di sistem ini:** `services/api`, `services/worker`, `packages/core`
(model `Fact`, `Event`, `Verdict`, `Parameter`, `Proposal`).

#### Kursi 3 — **Frontend/Product Engineer** — *hire ketiga*

**Peran:** mengubah data jadi **jawaban cepat**, bukan dinding widget. Menjaga
`catatan_kejujuran`, state kosong `—` (bukan `0`), label gross/net & paper/live.
**Kenapa ada:** risiko #2 dari sisi tampilan. Angka yang benar bisa tetap menyesatkan
kalau disajikan buruk. Positioning produk ini **"sinyal dulu, bukan bagan dulu"**.
**Di sistem ini:** `apps/web` (SvelteKit), 36 tes vitest + suite E2E Playwright.

#### Kursi 4 — **SRE/Ops (keselamatan & pemulihan)** — *hire keempat*

**Peran:** jaga sistem tetap hidup dan **bisa dipulihkan**. Deploy, restart, backup,
rollback, pemantauan.
**Kenapa ada:** kejadian **hari ini persis membuktikan** kursi ini wajib. War Room
**DOWN total** (semua halaman 500) karena build tidak diikuti restart — 1 perintah
yang tidak dijalankan. Tanpa kursi ini, tidak ada yang menangkap itu.
**Di sistem ini:** systemd (`warroom-api/worker/web`), nginx, journald, skill backup.
**Deliverable kunci:** **runbook deploy** + **definisi "perubahan produksi"** yang
mengharuskan restart + verifikasi pasca-perubahan (`sdlc-war-room.md` sudah menyebut
"post-change verification" — kursi ini yang menjalankan).

#### Kursi 5 — **QA/Verification Engineer (adversarial)** — *hire kelima*

**Peran:** **mencoba membuktikan sistem salah.** Bukan "bikin tes hijau", tapi
"temukan cara angka menipu". Pemilik Definition of Done & bukti.
**Kenapa ada:** risiko #3 & #5. Kursi inilah yang menangkap "E2E 27 hijau" ternyata
**butuh sesi yang tidak ada**, dan "tes Komuter ada" ternyata **tidak bisa jalan sama sekali**.
**Di sistem ini:** suite tes (806+36+227), E2E, dan **reviewer terpisah** dalam
struktur agen (verdict PASS/FAIL/NEEDS WORK — default NEEDS WORK).

---

### 2.3 Yang SENGAJA tidak saya hire (dan kenapa)

| Tidak di-hire | Alasan |
|---|---|
| Data Scientist / ML engineer | Belum ada kebutuhan model; LLM di sini **gateway + audit** (ADR-004), bukan riset. Nanti saat backtest serius, baru. |
| DevOps cloud / Kubernetes | 1 server (Webdock). K8s = over-engineering yang menambah risiko, bukan mengurangi. |
| Designer UI penuh | Positioning produk sudah ditentukan; desainer penuh baru perlu kalau multi-pengguna. |
| Mobile engineer | Web responsif sudah cukup (pengguna pakai SSH/layar kecil). |
| "Growth"/marketing | 1 pengguna, uang pribadi. Nol nilai. |
| Manajer proyek | 5 orang, 1 pemilik. Manajer = lapisan komunikasi tanpa kerja. **Owner = Product Owner.** |

**Filosofi:** setiap kursi yang tidak diisi lebih murah daripada kursi yang diisi
asal-asalan. Tim kecil yang tepat mengalahkan tim besar yang kabur.

### 2.4 Padanan "kursi" ⟷ struktur agen kamu

Kamu sudah pakai agen. Bagusnya: **lima kursi ini = lima peran agen dengan batas jelas.**

| Kursi manusia | Padanan di sistem agenmu | Batas |
|---|---|---|
| Quant/Risk Owner | **owner (kamu)** — tidak didelegasikan | ubah ambang/BE = hanya manusia |
| Backend/Platform | agen implementasi (koma/bridge dll) | tidak boleh ubah threshold |
| Frontend/Product | agen implementasi (UI) | tidak boleh mengarang angka |
| SRE/Ops | agen ops | **produksi = butuh izin owner** (terbukti hari ini) |
| QA/Verification | **reviewer** (read-only, verdict) | PASS wajib berbukti; default NEEDS WORK |

Ini bukan kebetulan — kamu sudah membangun struktur tim tanpa menyebutnya "tim".
Dokumen ini hanya **memberi nama kursinya** supaya bisa dinilai dan diisi.

---

## 3. Framework kerja: apa yang saya pakai, dan kenapa

Bukan satu framework agama. **Tiga lapis**, masing-masing untuk masalah berbeda.

### Lapis 1 — **Shape Up** (siklus kerja) — untuk *apa yang dikerjakan*

**Kenapa Shape Up, bukan Scrum:** Scrum butuh ritme tim & ceremony (standup, sprint
review) yang membebani 5 orang tanpa manfaat untuk 1 pemilik. Shape Up cocok karena:
- **Fixed time, variable scope** — cocok dengan "kerjakan yang menghambat dulu".
- **Pitch sebelum kerja** — memaksa masalah + batas + solusi ditulis sebelum koding.
- **Betting table** — owner memilih sedikit taruhan, bukan daftar backlog tak berujung.

**Penerapan konkret di War Room:**
- Setiap pekerjaan = **satu Pitch** (masalah, batas, solusi kasar, rabbit holes,
  no-gos) — SDLC repo sudah punya **"Work item contract"** yang mirip; kita pertegas.
- Siklus pendek (2 minggu) alih-alih sprint 2 minggu dengan ceremony.
- **Circuit breaker:** kalau lewat batas, berhenti — jangan "tambal terus".

### Lapis 2 — **DORA + Google SRE** (operasional) — untuk *bagaimana tidak jatuh*

**Kenapa:** kejadian hari ini adalah **SRE failure klasik** (perubahan tanpa restart &
verifikasi). DORA & SRE memberi bahasa untuk itu:
- **DORA 4 metrics:** lead time, deploy frequency, MTTR, change failure rate.
  Kejadian hari ini = **change failure**, dan MTTR kita tinggi karena **tidak ada yang tahu
  sampai kebetulan diperiksa.**
- **SRE:** SLO, error budget, **postmortem tanpa menyalahkan**.
- **Konsekuensi konkret:** setiap "deploy" (build web) wajib punya **langkah verifikasi
  otomatis** — bukan mengandalkan ingatan. Ini langsung menutup bug 500 hari ini.

### Lapis 3 — **SDLC bergate yang SUDAH ada di repo** (governance) — untuk *keselamatan*

Repo sudah punya `docs/sdlc-war-room.md`, `docs/standar-kerja-war-room-final.md`,
dan 5 ADR. **Saya TIDAK mengganti ini** — ini aset. Yang saya usulkan: **formalkan
padanannya ke 5 kursi** (DoR/DoD per kursi, bukan generik).

| Gate SDLC (sudah ada) | Kursi pemilik |
|---|---|
| Definition of Ready | Quant + Product |
| Definition of Done | QA |
| Release gate | SRE + Owner |
| Post-change verification | SRE |
| Verdict review (PASS/FAIL) | QA |

**Ringkas:** Shape Up memutuskan **apa**, DORA/SRE menjaga **sistem hidup**, SDLC repo
menjaga **batas keselamatan**. Ketiganya tidak bertabrakan.

---

## 4. Model data (ERD) — tumbuh dari 5 kursi, bukan dari nol

> **Ini bagian yang menjawab permintaanmu soal "ERD".** Model data di bawah **sudah ada
> sebagian besar** di `packages/core/src/warroom_core/db/models.py`. Saya tidak
> mengarang — saya **membacanya** lalu memetakan ke kebutuhan kursi.

### 4.1 Entitas yang ada (terverifikasi di kode)

| Tabel | Peran | Kursi pemilik |
|---|---|---|
| `facts` | **satu-satunya sumber angka** (ADR-005) | Backend |
| `events` | log append-only, tiap event menautkan `fact_ids` | Backend |
| `verdicts` | hasil penilaian per pasar (signal/gate) | Quant |
| `strategies` | strategi per pasar | Quant |
| `trades` | trade (paper & live dipisah jelas) | Quant |
| `parameters` | parameter berversi (`locked`/`bounds`) | Quant (hanya owner ubah) |
| `proposals` | usulan perubahan parameter | Backend+Quant |
| `prompts` | prompt LLM berversi | Backend |
| `llm_calls` | audit tiap panggilan LLM (biaya, fallback) | Backend (ADR-004) |
| `alerts` | peringatan + status ack | SRE |
| `jobs` | penjadwalan deklaratif worker (bukan cron tersembunyi) | SRE |
| `frozen_splits` | split data dibekukan sebelum lihat hasil (anti-overfit) | QA+Quant |
| `grants` | izin aksi live (dikunci) | Owner |
| `services` | daftar layanan yang dipantau | SRE |
| `heartbeats` | denyut tiap layanan (dasar pemantauan) | SRE |
| `users` | akun (viewer\|operator\|owner) | Backend |
| `sessions` | sesi login (dasar auth web & E2E) | Backend |
| `audit` | jejak tindakan istimewa | SRE+Owner |
| `datasets` | dataset yang dikelola | QA |
| `research_runs` | run riset/backtest | QA+Quant |
| `research_records` | hasil per run riset | QA+Quant |

> **Total: 21 tabel** (terverifikasi lewat `grep __tablename__`), bukan 13 seperti draf
> awal dokumen ini. Saya koreksi setelah memverifikasi ulang — draf awal melewatkan 8
> tabel karena hanya membaca sebagian berkas. Fakta yang benar: **21.**

### 4.2 ERD (relasi inti)

```
                    ┌─────────────┐
                    │  strategies │  (Quant)
                    └──────┬──────┘
                           │ 1..n
                    ┌──────▼──────┐        ┌──────────────┐
                    │  verdicts   │◄───────│  parameters  │ (locked/bounds)
                    └──────┬──────┘        └──────┬───────┘
            (signal/gate)  │                      ▲ diusulkan
                           │ fact_ids             │
                    ┌──────▼──────┐        ┌──────┴───────┐
                    │   facts     │◄───────│  proposals   │
                    └──────┬──────┘        └──────────────┘
                           ▲                       (Backend+Quant)
              ditautkan    │ fact_ids
                    ┌──────┴──────┐        ┌──────────────┐
                    │   events    │        │  llm_calls   │  (audit AI)
                    └──────┬──────┘        └──────┬───────┘
                           │                      │ prompt_id
                    ┌──────▼──────┐        ┌──────▼───────┐
                    │   trades    │        │   prompts    │
                    │ paper│live  │        └──────────────┘
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
   ┌────▼────┐      ┌──────▼──────┐     ┌─────▼─────┐
   │ alerts  │      │    jobs     │     │  grants   │  (izin live)
   │  (SRE)  │      │   (SRE)     │     │  (Owner)  │
   └─────────┘      └─────────────┘     └───────────┘

   frozen_splits ──(membekukan dataset)──► dipakai verdicts/backtest
```

**Tiga aturan yang mengikat seluruh diagram (dan kenapa ini penting):**

1. **Tidak ada angka di UI/AI tanpa baris `facts`.** (`db/models.py` baris 6.)
   → Menutup risiko #2 (angka palsu/tak bersumber).
2. **`events` append-only dan menautkan `fact_ids`.** → Menjawab "apa berubah sejak
   terakhir saya lihat" (ADR-005).
3. **`trades` membedakan paper/live sejak level skema.** → Menutup risiko #3.

### 4.3 Celah model data yang saya temukan (jujur, belum diperbaiki)

Ini **temuan nyata dari pembacaan**, bukan karangan. Saya juga **mencatat satu koreksi
terhadap diri sendiri**: draf pertama dokumen ini mengklaim "tidak ada entitas source_health",
tapi setelah verifikasi ulang (`grep __tablename__`), ternyata **`services` + `heartbeats`
SUDAH ADA** dan sudah berisi (`host`, `unit`, `status`, `detail_json`, `beat_at`). Jadi
fondasi pemantauan **sudah setengah jalan** — klaim awal saya terlalu cepat.

- **[celah-1] Status kesehatan sumber belum kaya.** `services.status` ada, tapi P1 backlog
  menuntut state lebih halus: `paused / frozen / degraded / unreachable`. Perluas `services`
  (atau tabel status terpisah) — **bukan bikin dari nol**.
- **[celah-2] Tidak ada entitas deployment/restart.** Dikonfirmasi: tidak ada tabel yang
  merekam "build versi X ↔ proses versi X". Inilah **TEPAT** yang bikin bug hari ini
  tak terdeteksi (build 21:00, proses lama dari 20:58, tak ada yang tahu).
- **[celah-3] `audit` ada, tapi bukan "keputusan owner".** Tabel `audit` merekam tindakan;
  yang belum ada adalah tautan eksplisit **perubahan ambang → tanda tangan owner + alasan**.
  Perluas `audit`/`parameters`, jangan bikin paralel.

**Ketiganya jadi pekerjaan (lihat §6), bukan langsung dikerjakan** — dan **dua di antaranya
adalah perluasan tabel yang sudah ada, bukan tabel baru.**

---

## 5. Arsitektur (dari model data)

```
                    ┌──────────────────────────────────────────┐
   Owner ──SSH────► │         nginx (TLS, satu-satunya proxy)    │
   Owner ──TG────►  └────────────────────┬─────────────────────┘
                                         │
                        ┌────────────────┴─────────────────┐
                        ▼                                  ▼
                 ┌─────────────┐                    ┌─────────────┐
                 │  apps/web   │                    │ services/api│
                 │  SvelteKit  │◄────openapi.json──►│  FastAPI    │
                 │  :3100      │    (kontrak)       │  :8800      │
                 └─────────────┘                    └──────┬──────┘
                                                           │
                     ┌─────────────────────────────────────┼──────────────┐
                     ▼                                     ▼              ▼
              ┌─────────────┐                     ┌─────────────┐  ┌─────────────┐
              │services/llm │                     │services/    │  │  Postgres   │
              │ (gateway +  │                     │  worker     │  │  (facts,    │
              │  audit AI)  │                     │ (jobs, 30s) │  │  events,...)│
              └─────────────┘                     └──────┬──────┘  └─────────────┘
                                                         │
                                            ┌────────────▼─────────────┐
                                            │ packages/live-trading    │
                                            │ (DOMAIN — tidak diporting)│
                                            │  gate.py (murni)          │
                                            └───────────────────────────┘
```

**Enam prinsip arsitektur (semuanya berasal dari ADR yang sudah terkunci):**

1. **Domain tetap Python** (ADR-001) — menulis ulang = membuang 227 tes = risiko #4.
2. **Monorepo + uv workspace** (ADR-002) — satu sumber kebenaran.
3. **Gate sebagai layanan, `gate.py` murni** (ADR-003) — tanpa I/O/DB/LLM. `ci_low > be`
   satu-satunya jalur lolos.
4. **LLM gateway terpusat + tiap panggilan tercatat** (ADR-004).
5. **Event log append-only + fakta berversi** (ADR-005).
6. **UI menampilkan fakta, tidak menghitung ulang** (SDLC §2).

**Yang saya usulkan TAMBAH ke arsitektur (bukan ganti):**

- **[usul-ars-1] Versi build ↔ versi proses wajib cocok.** Endpoint `/health` harus
  mengembalikan `build_id`; CI/deploy memverifikasi. Ini menutup **selamanya** bug
  "build selesai, proses lama masih jalan".
- **[usul-ars-2] Deploy = build + restart + verifikasi, sebagai satu unit.** Bukan tiga
  langkah terpisah yang bisa terlupa.

---

## 6. Rencana implementasi (berurut, bergate)

Disusun dengan Shape Up: pitch kecil, batas jelas, tidak ada "dan seterusnya".

| # | Pekerjaan | Kursi | Definisi Selesai (bukti) | Risiko kalau salah |
|---|---|---|---|---|
| **R0** | **Runbook deploy + verifikasi wajib** (menutup celah-2 & usul-ars-1/2) | SRE | Ada `ops/deploy.md`; `/health` kembalikan `build_id`; skrip deploy gagal bila versi tak cocok | Sistem mati diam-diam (KEJADIAN HARI INI) |
| **R1** | **Perbaiki E2E** (jalankan ulang setelah produksi hidup; perbaiki mekanisme sesi) | QA | `npx playwright test` hijau ATAU jelas menunjukkan kegagalan nyata; tidak lagi gagal karena sesi | QA palsu — "hijau" yang tak bermakna |
| **R2** | **Koreksi angka README** (761→806, 219→227, 35→36) | QA | README cocok dengan `--collect-only` | Dokumen berbohong |
| **R3** | **Entitas `source_health`** (celah-1) | Backend+QA | Migrasi + endpoint + state paused/frozen/degraded/unreachable | Keputusan pakai data basi |
| **R4** | **Keputusan owner terekam** (celah-3) | Owner+Backend | Tabel + alur: tiap ubah ambang tertaut tanda tangan + alasan | Ambang berubah tanpa jejak |
| **R5** | **CI War Room** (bukan hanya Komuter) | QA+SRE | GitHub Actions: 806+36 tes + lint + build web + verifikasi `build_id` | Regresi masuk tanpa terlihat |
| **R6** | **SOP postmortem tanpa menyalahkan** (dari kejadian hari ini) | SRE+Owner | Dokumen + 1 postmortem nyata ditulis | Kejadian sama terulang |

**Urutan ini bukan selera.** R0 dulu karena **kita baru saja kena**; R1/R2 karena
mengoreksi kebohongan dokumen; R3–R4 menutup celah data; R5–R6 mencegah pengulangan.

---

## 7. Ringkasan satu halaman (kalau kamu hanya baca ini)

- **Proyek ini bukan startup.** 1 pengguna, uang nyata, 7 pasar, **batas keselamatan
  sebagai fitur utama**.
- **Kalau saya bikin tim: 5 kursi** — Quant/Risk, Backend, Frontend, SRE, QA.
  **Hire untuk risiko, bukan fitur.** Tidak lebih, tidak kurang.
- **Framework: 3 lapis** — Shape Up (apa yang dikerjakan), DORA/SRE (sistem tetap hidup),
  SDLC repo (batas keselamatan). **Tidak mengganti SDLC yang sudah ada.**
- **ERD sudah ada 90%** di kode (13 tabel). Yang kurang: `source_health`, jejak
  deploy/restart, dan jejak keputusan owner.
- **Kejadian hari ini** (War Room 500 karena build tanpa restart) bukan kebetulan —
  itu **bukti kursi SRE kurang**, dan langsung jadi pekerjaan **R0**.
- **Rencana: R0→R6**, mulai dari yang paling baru merugikan.

**Yang saya minta darimu:** setujui/tolak arah lima kursi & tiga lapis framework ini.
Kalau setuju, saya kerjakan **R0** dulu (runbook deploy) karena itu yang paling terbukti
dibutuhkan. Kalau ada kursi yang menurutmu salah/tidak perlu, bilang — aku revisi.
