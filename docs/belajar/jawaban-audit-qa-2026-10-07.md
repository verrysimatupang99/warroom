# Jawaban audit QA eksternal — 7 Okt 2026 (hermes webdock)

Laporan QA eksternal masuk 7 Okt 2026 (audit authenticated, mode baca saja). Dokumen ini
mencatat **apa yang dikerjakan**, **apa buktinya**, dan **apa yang sengaja tidak dikerjakan
karena butuh keputusan pemilik**. Ditulis dari kode & hasil uji.

## Ringkasan: 9 butir daftar prioritas QA

| # | Temuan QA | Status | Bukti |
|---|---|---|---|
| 1 | Setup Crypto melewati batas risiko 1% | ✅ Selesai — **ternyata bug pelabelan** | lihat §1 |
| 2 | Invariant IDX (rugi > 1R, saldo negatif) | ✅ Selesai — dikarakterisasi + ditandai | lihat §2 |
| 3 | Bedakan dataset statistik | ✅ Selesai | kolom "Tuntas (n)" + catatan populasi |
| 4 | Freshness badge di tiap market card | ✅ Selesai | badge PAPER/HISTORIS + sumber + umur |
| 5 | Loading/skeleton anti blank screen | ✅ Selesai | shell pra-hydration di `app.html` |
| 6 | CSP Report-Only | ✅ Selesai | header live di produksi |
| 7 | Authorization/IDOR test | ✅ Selesai | 7 tes baru (755 total hijau) |
| 8 | Rotasi kredensial + TOTP | ⚠ **butuh pemilik** | lihat §8 |

Plus: flag NOT COST-ADJUSTED (Forex) dan pemindai nama aksesibel.

---

## §1 Crypto "risiko 3,813% vs policy 1%" — bug PELABELAN, bukan pelanggaran

QA benar bahwa angka itu bertentangan dengan label — tetapi **angkanya bukan risiko akun**.
Angka itu **jarak stop**. Bukti dari ledger nyata:

| Pair | Jarak stop | Ukuran posisi | Risiko akun |
|---|---|---|---|
| 1000PEPEUSDT | 3,813% | $25,55 | **1% dari $100 = $1** |
| SUIUSDT | 2,011% | $47,28 | 1% |
| LINKUSDT | 1,76% | $53,75 | 1% |

Rumusnya di `risk.py`: `size_usd = risk_usd ÷ effective_stop_pct` — makin lebar stop, makin
kecil posisi, sehingga risiko akun **tetap 1%**. Jadi tidak ada setup yang melampaui policy;
yang salah adalah UI menamai jarak stop sebagai "risiko".

**Perbaikan:** istilah dipisah tegas di semua tempat —
- kartu kandidat: `R:R … · jarak stop 3,813% · risiko akun 1%`
- RiskMeter: label "Risiko Akun / Trade" + keterangan "ukuran posisi = 1% ÷ jarak stop"
- pesan Telegram & Home ikut dikoreksi.

## §2 IDX "stop-loss dilanggar" — NYATA, dan sekarang dikarakterisasi

QA benar, dan angkanya bahkan lebih buruk dari yang terlihat di UI. Bukti dari
`idx_ledger.db` (278 trade tuntas):

- **97 trade rugi melebihi 1R** — wajar 181 · gap 1–2R 17 · dalam 2–5R 43 · **ekstrem >5R 37**
- Terburuk: **MBTO.JK −13,84R** (ARA_HUNTER, entry 228, SL 222,3, ditutup di open sesi berikutnya)
- Penyebab mekanis: posisi ditahan sampai open sesi berikutnya → gap pembukaan bisa 14× risiko
- 350 sinyal berstatus `CREATED` (tertua 24 Sep) — **bukan posisi berjalan**, mesin dibekukan

**Perbaikan (bukan menyembunyikan angka):**
- `dompet.py` menerbitkan `invariant` (jumlah pelanggaran, klasifikasi gap/dalam/ekstrem,
  trade terburuk, penjelasan) + `sinyal_yatim`
- Banner **MODEL BREACH** di kartu dompet IDX (tampil juga di mode ringkas): jumlah, terburuk,
  klasifikasi, sebab, dan konsekuensi eksplisit — *"rugi maksimal 1R tidak berlaku; ukuran
  posisi wajib diperkecil atau diperlakukan berisiko tak terbatas"*
- Catatan bahwa `CREATED` bukan posisi berjalan
- Tes: `test_dompet_invariant.py` (breach + tenang), E2E `cek_invariant_idx.spec.ts`

## §3 Label populasi dataset

QA: "n=12 di ringkasan vs n=16 di narasi — bisa valid, tapi UI belum tegas."
Perbaikan: kolom `n` → **"Tuntas (n)"** + tooltip + catatan populasi di kaki tabel
(AkurasiPasar & Home): dihitung dari **trade tuntas**, bukan sinyal dinilai / kandidat aktif /
posisi berjalan; bandingkan hanya populasi yang sama.

## §4 Badge mode per kartu market

QA: "user harus membaca jauh ke bawah untuk tahu live/stale/paper/historical."
Perbaikan: API menerbitkan `sumber`, `mode` (LIVE/PAPER/HISTORIS), `catatan_mode`; kartu Home
menampilkan badge mode + "sumber: … · data N lalu". **IDX jujur berlabel HISTORIS** (beku).

## §5 Layar kosong sebelum hydration

Akar masalah: `ssr = false` (disengaja — rute butuh cookie; 401 → /masuk), sehingga HTML yang
tersaji benar-benar kosong. Perbaikan: shell statis di `app.html` (kerangka + skeleton
berdenyut, tanpa angka pasar) yang digantikan aplikasi saat hydration. Crawler/otomasi tidak
lagi membaca "blank".

## §6 CSP Report-Only + header tambahan

Terpasang di nginx produksi (dan disalin ke `ops/nginx-warroom.conf`):

```
Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self';
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com; img-src 'self' data:;
  connect-src 'self'; frame-ancestors 'none'; base-uri 'self';
  form-action 'self'; object-src 'none'
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

Report-only = tidak memblokir apa pun; **naik ke enforce adalah keputusan manusia** setelah
log bersih.

## §7 Authorization/IDOR

`services/api/tests/test_authorization_idor.py` (7 tes): 16 endpoint 401 tanpa sesi; viewer
403 di semua jalur tulis; operator 403 di aksi owner **tetapi boleh dry-run**; IDOR proposal
antar-operator; path traversal tidak dianggap area sah; filter SSE tidak membocorkan tipe lain.

## §8 Rotasi kredensial (butuh pemilik)

QA benar: sandi dikirim lewat percakapan. Yang perlu **pemilik** lakukan (tidak bisa
diwakilkan dari kode):
1. ganti sandi akun operator yang dipakai QA;
2. jangan pakai sandi itu di layanan lain;
3. aktifkan TOTP;
4. simpan hanya di vault.

## Yang masih terbuka (jujur)

- **CSP masih Report-Only** — menunggu log bersih + keputusan pemilik.
- **Data IDX beku** (cron Tencent pause): 350 sinyal yatim tidak akan tuntas sampai mesin
  dihidupkan lagi. Ledger tetap utuh sebagai bukti.
- **Forex bruto** (spread/komisi broker belum ada di jurnal) — ditandai, belum diperbaiki
  (butuh data dari broker).
- **LP belum direkonsiliasi on-chain** — dinyatakan apa adanya.

---

## Insiden pasca-QA: "web masih terus memuat" (dilaporkan pemilik, 7 Okt)

**Gejala:** halaman tidak bisa dibuka; yang terlihat skeleton berdenyut selamanya.

**Akar masalah (buatan sendiri):** shell pra-hydration di `app.html` — dipasang untuk
menghilangkan layar kosong yang dilaporkan QA — **tidak pernah dihapus** setelah aplikasi
hidup. Skeleton statis menutupi UI yang sebenarnya sudah jalan sempurna (judul benar, DOM
lengkap, API sehat). Jadi bukan "sedang memuat"; ia menutupi.

**Mengapa tes lolos:** semua tes membaca `body.innerText`/textContent — dan elemen yang
TERTUTUP lapisan lain tetap punya textContent. Tes mengukur "ada di DOM", bukan "terlihat".
Kelas bug ini tidak bisa ditangkap tes berbasis teks.

**Perbaikan (dua lapis):**
1. `+layout.svelte`: `$effect` menghapus `#shell-muat` begitu aplikasi hidup.
2. `app.html`: `body:has(#konten) #shell-muat { display: none !important }` — pengaman CSS
   murni; bekerja walau JS utama telat/gagal. Kegagalan ini jadi mustahil, bukan sekadar
   diperbaiki sekali.

**Tes penjaga baru:** `e2e/cek_shell_hilang.spec.ts` mengukur YANG TERLIHAT:
- shell tidak tampil (computed style, bukan keberadaan),
- `document.elementFromPoint` di tengah layar harus milik aplikasi,
- `#konten` tinggi > 200 px.
Diuji di 4 halaman termasuk `/masuk`.

**Pelajaran yang dikodifikasi:** untuk UI, "ada" ≠ "terlihat". Setiap lapisan penutup
(shell, overlay, modal, skeleton) wajib punya tes yang memeriksa hasil render yang terlihat.

**Dampak ke tes flaky:** dua tes kebijakan (`sub-baru`, `qa-lengkap`) yang klik tab
"Kebijakan" ikut rapuh karena klik dilakukan sebelum halaman interaktif (dan sempat
tertutup shell). Keduanya diperkuat: tunggu tab terlihat, lalu klik, lalu tunggu hasil
dengan timeout eksplisit.

---

## Pelajaran tes (7 Okt, dari insiden shell → 3 tes usang)

Tiga kesalahan berbeda yang semuanya tampak seperti "fitur rusak", padahal tesnya yang salah:

1. **"Ada" ≠ "terlihat"** — shell pra-hydration menutupi aplikasi; semua tes lolos karena
   membaca `body.innerText` (elemen tertutup tetap punya textContent). → tes baru
   `cek_shell_hilang.spec.ts` memakai `elementFromPoint` + tinggi elemen nyata.
2. **"Terlihat" ≠ "siap diklik"** — elemen bisa terlihat sementara listener Svelte belum
   terpasang; klik hilang diam-diam. → penanda `data-app-siap` di AppShell + util
   `tungguSiap(page)`; dipakai tes sebelum berinteraksi.
3. **Tes bisa usang tanpa ada yang rusak** — sub "Dataset" sudah berganti nama "Riset"
   (keputusan owner 7 Okt), tetapi tes masih mencari "Dataset" → menunggu 2 menit lalu
   gagal. Begitu pula `role="button"` vs `role="tab"`. → kedua tes diperbarui; waktu
   turun dari ~2 menit (flaky) menjadi ~1,4 detik (stabil).

**Aturan yang berlaku sekarang:** setiap tes UI menunggu `tungguSiap()` dulu; setiap
lapisan penutup (shell/overlay) wajib punya tes yang mengukur hasil render yang terlihat;
label sub-tab di tes harus merujuk nav.ts (satu sumber), bukan hafalan.

---

# Audit QA putaran 2 (7 Okt) — jawaban & bukti

## 1. Polymarket: kontradiksi "EDGE TERBUKTI" vs gate — DIPERBAIKI

**Temuan QA benar dan penting:** halaman menampilkan klaim keunggulan, sementara gate di
bawahnya menyebut split belum dibekukan. Satu halaman, dua kesimpulan.

**Akar:** `StatisticalEdgeCard` hanya memeriksa `CI95 bawah > BE`, sedangkan gate resmi
(`gate.py`, ADR-003) **menolak promosi** selama `split` belum `frozen:<id>`. Ditambah lagi
sumber menerbitkan label mentah `verdict_alat: "EDGE"` yang diteruskan apa adanya ke UI.

**Perbaikan (dua lapis):**
- Kartu edge tunduk gate yang sama: `splitBeku && ciLolos && sampelCukup && n>=100` → baru
  "EDGE TERBUKTI"; selain itu **"BELUM DIPROMOSIKAN"** + alasan ditulis apa adanya + baris
  status split eksplisit.
- `sinyal.py`: label mentah "EDGE" tidak diteruskan saat split kosong → tier **EKSPLORASI**,
  arah **TAHAN**.

**Bukti live:** kartu kini menulis "BELUM DIPROMOSIKAN · split data: belum dibekukan ·
butuh ≈7392 sampel (kini 4133)". Kartu Home: `TAHAN / EKSPLORASI`.

## 2. IDX: breach/gap dipisahkan + saldo negatif berkonteks

- Banner **SALDO NEGATIF** tepat di atas angka saldo + label "modal habis — bukan sekadar
  rugi" pada angkanya.
- Klasifikasi **per setup** terbit dan tampil sebagai kolom BREACH:
  `ARA_HUNTER 94/198 (47,5%)`, `BSJP_ARA 2/19`, `BSJP_STRONG 1/26`, `INTRADAY 0/35`.
- Total tetap: 97/278 melewati 1R (gap 17 · dalam 43 · ekstrem 37).

**Catatan jujur:** kerugian MODEL-nya belum diperbaiki — ARA_HUNTER masih menahan posisi
sampai open sesi berikutnya. Yang diperbaiki adalah **keterlihatannya**, bukan strateginya.
Perbaikan strategi = keputusan pemilik (mis. keluar sore yang sama, atau perlakukan sebagai
risiko tak terbatas dengan ukuran posisi jauh lebih kecil).

## 3. Kesegaran: "basi" kini bisa dibuka

"N basi" di TopBar adalah tombol → daftar: kunci, umur vs TTL, **sumber**, dan penjelasan
mengapa sebagian sengaja tetap tampil (mesin beku → ditandai HISTORIS di halaman pasarnya).

## 4. CSP: Report-Only → **ENFORCE**

Temuan QA benar: Report-Only belum proteksi. Investigasi menemukan dua hal:
1. Report-Only **tanpa `report-uri`** tidak pernah mengumpulkan laporan — "menunggu log
   bersih" tak akan pernah selesai.
2. Uji enforce lewat browser membuktikan akan ada pelanggaran: skrip bootstrap inline
   SvelteKit (hash berubah tiap build), dan `ssr = false` membuat fitur `csp` SvelteKit
   tidak menyisipkan meta apa pun.

**Solusi:** `ops/csp-enforce.sh` menghitung sha256 skrip inline dari HTML yang **sedang
tersaji**, menulis snippet nginx, reload — dipanggil otomatis di akhir `deploy-web.sh`
setelah health gate. Script tidak diberi `unsafe-inline`; hanya style.

**Bukti:** header `Content-Security-Policy` (enforce) terpasang di produksi dengan hash
benar; UI terverifikasi hidup (shell hilang, konten tampil, E2E hijau).

## 5. Authorization/IDOR/SSE — dan DUA BUG NYATA yang ditemukan

Saat menjawab butir ini, pengujian isolasi SSE menyingkap dua bug lama:

1. **Kelaparan aliran SSE.** `_fetch` mengambil 200 baris terakhir tanpa peduli topik lalu
   menyaring di Python; `after` hanya maju untuk baris yang cocok. Karena tabel events
   didominasi `job.ran` (12.000+ baris), klien bertopik membaca 200 baris tak-cocok yang
   sama selamanya → aliran area tidak pernah sampai ke kejadian relevan.
   **Perbaikan:** filter topik di SQL + `_fetch` mengembalikan id tertinggi yang DIBACA.
2. **Backfill tidak menyaring.** Panel Kejadian Area meminta 120 kejadian terakhir tanpa
   filter → hampir pasti `job.ran` → panel selalu "0 kejadian".
   **Perbaikan:** `/api/v1/events` menerima daftar prefix; backfill disaring per area.

**Bukti:** panel Kejadian crypto kini "29 kejadian" (mis. DOGEUSDT `trade.opened`).
Tes baru: event trade ditenggelamkan di antara 300 `job.ran` → tetap ketemu, tidak diulang.

Suite: 8 tes authorization/IDOR/SSE hijau; pytest penuh hijau; ruff bersih.

## Sisa yang butuh pemilik

- **Rotasi sandi + TOTP** (sandi pernah lewat percakapan).
- **Perbaikan strategi ARA_HUNTER** (bukan lagi soal tampilan).
- **CSP**: bila kelak menambah sumber luar (CDN baru), hash/daftar di `csp-enforce.sh`
  harus ikut diperbarui — kalau tidak, halaman akan memblokirnya sendiri.

---

## Temuan susulan: profit harian dihitung sebagai risiko (7 Okt, saat kerja tab Eksekusi)

**Kelas bug:** angka benar, **label salah** → kesimpulan salah. Persis yang dikritik audit.

`hari_ini_r` di fakta `risiko` adalah **PnL hari ini dalam R** — negatif berarti rugi.
Dua tempat memakai `Math.abs()` sehingga hari yang **profit** ditampilkan seolah pelanggaran:

| Tempat | Gejala |
|---|---|
| `RiskMeter.svelte` | Hari +4,00 R tampil sebagai "Risiko Terpakai 4,00 R / 3,00 R Max" + badge **LIMIT TERCAPAI** |
| `format.ts` → `statusRisikoDari()` | Ambang 90%/60% dari nilai absolut → profit besar memicu "limit tercapai" |

Artinya: **setiap hari yang profit, sistem menuduh dirinya melanggar batas risikonya sendiri.**

**Perbaikan:**
- `statusRisikoDari()` + `persenRisikoTerpakai()` baru: hanya sisi RUGI yang memakai kuota.
- `RiskMeter`: `0,00 R / 3,00 R Max` + baris terpisah `+4,00 R profit hari ini — tidak memakai kuota batas rugi`.
- Baris ringkasan tab Eksekusi ikut dikoreksi.

**Pelajaran yang dikodifikasi:** untuk besaran yang punya ARAH (PnL, risiko, selisih),
`Math.abs()` adalah bau bahaya — ia membuang tanda, dan tanda itulah yang membedakan
"untung" dari "melanggar batas". Setiap kali memakai `abs()` pada besaran berarah,
tanyakan: apakah pembaca akan menyimpulkan hal yang sama untuk +X dan −X?

**Tes penjaga:** `e2e/cek_semantik_risiko.spec.ts` — bila hari profit, kuota terpakai
HARUS `0,00 R` dan badge TIDAK boleh "LIMIT TERCAPAI". Mengunci semantik, bukan tampilan.

---

## Pembaruan halus UI (7 Okt, arah desain "Serene Capital" dari Stitch)

Desain Stitch pertama dinilai pemilik "berlebihan" (8+ blok, belasan badge, 4.214 px).
Digenerate ulang dengan prompt "pembaruan halus" → 1.440 px, 4 blok, 2 label. Tiga idenya
diterapkan memakai token War Room (bukan Tailwind, bukan tema navy):

**Tab Ukur:**
1. Baris ringkasan bahasa manusia di atas (diturunkan dari data pengukuran, bukan karangan).
2. Tiga angka besar per kartu (trade · total R · win rate) — sebelumnya empat angka sama besar.
3. Tabel akurasi mode ringkas (4 kolom). **Temuan:** tabel ini sebelumnya TIDAK PERNAH
   tampil di tab Ukur — kondisi `sub === 'ukur'` pada pemanggilnya berada di dalam grid
   yang hanya dirender untuk cockpit/setup (kode mati).

**Tab Eksekusi:**
1. Baris ringkasan (posisi terbuka · kuota risiko terpakai · trade tuntas).
2. Label `FAKTA HARGA, BUKAN SINYAL` dipindah ke JUDUL kartu Overextended — dulu hanya
   di catatan kaki sehingga tabelnya bisa disalahartikan sebagai daftar sinyal.

**Dua bug infrastruktur yang ikut ketemu:**
- `deploy-web.sh`: jalur `ops/` dihitung setelah `cd apps/web` → `csp-enforce.sh` selalu
  "gagal dipasang" saat dipanggil dari deploy (padahal jalan manual).
- `csp-enforce.sh`: kini retry 5× saat mengambil HTML (node baru restart kadang belum siap).

**Cara melihat desain Stitch (pratinjau, tanpa CSP):**
`https://0xgunsl1ng3r.xyz/desain/stitch-halus.html` (acuan yang dipakai) ·
`/desain/stitch-mandiri.html` (yang "berlebihan", pembanding) ·
`/desain/stitch-1.html` (Bloomberg lama).
Catatan: berkas di `/desain/` dilayani nginx dengan CSP khusus (berkas pihak ketiga, hanya
untuk dilihat); berkas mandiri sudah menanam CSS-nya sendiri sehingga tampil tanpa CDN.
