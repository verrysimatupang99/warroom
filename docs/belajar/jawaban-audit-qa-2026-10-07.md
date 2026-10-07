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
