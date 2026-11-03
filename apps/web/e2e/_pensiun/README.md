# e2e/_pensiun — spec yang menjaga UI yang sudah tidak ada

Folder ini berisi spec Playwright yang **dipensiunkan** pada 3 Nov 2026, bukan
dihapus, supaya riwayatnya tidak hilang dan bisa dihidupkan lagi bila UI-nya
dikembalikan.

## Kenapa dipensiunkan

UI War Room dirombak (MarketShell, KurvaEkuitas, ForexCockpitExness, dll). Setelah
rombakan, **28 komponen di `src/lib/components/` tidak diimpor siapa pun** —
diverifikasi `grep -c ZonaAktif build/index.js` → `0`, artinya komponen itu memang
tidak pernah ter-render. Spec di folder ini menguji teks/panel dari komponen yatim
tersebut, jadi kegagalannya **bukan bug aplikasi**, melainkan test yang menjaga
fitur yang sudah pergi.

## Daftar & alasannya

| Spec | Menjaga | Kenapa pensiun |
|---|---|---|
| `cek_rombak.spec.ts` | "Dompet Rp 10 juta tampil di tiap market" (rombakan 7 Okt) | Komponen dompet per-market (`DompetLintasMarket`) yatim; UI sekarang `MarketShell` |
| `cek_perbaikan.spec.ts` | Home: status hari ini + tabel Akurasi & PnL + legenda pakem | Sebagian sudah pindah ke Home sekarang, sebagian komponennya (`ZonaAktif`) yatim |
| `cek_home_revisi.spec.ts` | Revisi Home 7 Okt (card status + akurasi digabung) | Struktur Home sudah dirombak lagi setelahnya |
| `cek_lipatan_home.spec.ts` | Pengurangan density Home (3 lapisan) | Susunan lapisan sudah berubah |
| `cek_zona_forex.spec.ts` | Panel "Zona & Sinyal Mesin (Forex)" di /forex | `ZonaAktif` yatim; /forex sekarang `MarketShell` tanpa panel itu |
| `cek_bukti.spec.ts` | Halaman Kinerja & Bukti, tabel tujuh kolom | Halaman riset/bukti sudah direstrukturisasi |
| `cek_penjelasan.spec.ts` | Panel penjelasan | Komponen `Penjelasan` yatim |
| `cek_timestamp.spec.ts` | Kejujuran waktu sinyal (timestamp + umur) | Timestamp sudah diverifikasi di `cek_home.spec.ts` (**lulus**) |
| `cek_panel_reaper.spec.ts` | Panel "Status mesin Reaper" di /forex | Panel tidak ada di `MarketShell` |

## Yang TIDAK dipensiunkan

- `cek_home.spec.ts` — **lulus 2/2** setelah fakta pasar disemai
  (`ops/e2e-seed-fakta.py`). Panel "Akurasi & PnL per Market" masih hidup, dirender
  inline di `src/routes/+page.svelte`, bukan lewat komponen `AkurasiPasar`.
- Spec lain yang masih menguji UI yang benar-benar ada.

## Gelombang kedua (verifikasi 3 Nov, setelah suite berjalan penuh)

Setelah suite lengkap dijalankan, tersisa 41 kegagalan. Diperiksa satu per satu:
**teks yang di-assert sudah tidak ada di `src/` sama sekali** (dicek dengan
`grep` ke seluruh berkas `.svelte`). Sepuluh spec lagi dipensiunkan:

| Spec | Teks yang dicari | Kenapa |
|---|---|---|
| `cek_idx_langkah` | `LANGKAH 1` | Panel langkah IDX dilepas |
| `cek_lp_vonis` | `Peluang hari ini`, `Hati-hati` | Panel vonis LP dilepas |
| `cek_ukur_halus` | `Setup Lolos Gate`, `Akurasi per Strategi` | Tab Ukur dilepas |
| `cek_bandarmologi` | `Skor Bandarmologi (0–100)` | Panel skor dilepas |
| `cek_cockpit_crypto` | `OKX Live` | Cockpit crypto lama, kini MarketShell |
| `cek_eksekusi_halus` | `FAKTA HARGA, BUKAN SINYAL` | Panel eksekusi lama |
| `cek_istilah` | `STATUS HARI INI` | Panel status lama |
| `cek_kalender_makro` | `Agenda makro` | Kalender makro dilepas |
| `cek_kandidat_aktif` | `Kandidat Aktif (ledger gate)` | Panel kandidat lama |
| `cek_setup_eksekusi` | `Kandidat Setup SMC Crypto` | **sub-tab `?sub=setup`/`?sub=eksekusi` di /crypto sudah tidak ada** |

Bukan dipensiunkan karena teks (tetap aktif, gagal karena data/sesi):
`cek_basi`, `cek_market`, `cek_invariant_idx`, `cek_verdict`, `cek_poly_be_wr`,
`cek_sistem_mesin`, `cek_mode_utama`, `cek_verifikasi-website`, `qa-lengkap`,
`a11y`, `screenshot`.

## Gelombang ketiga: teks ADA tapi komponennya YATIM

Klasifikasi pertama hanya bertanya "teksnya ada di `src/`?". Itu **tidak cukup**:
teks bisa hidup di komponen yang sudah tidak diimpor route mana pun, jadi tidak
pernah dirender — spec-nya tetap mustahil lulus. Dua spec kena kasus ini:

| Spec | Sebab |
|---|---|
| `cek_semantik_risiko` | `Batas Risiko & Kapasitas` ada di `RiskMeter.svelte`, tapi komponen itu **yatim** — tak diimpor route mana pun. Juga memakai `?sub=cockpit` yang tak ada lagi. |
| `cek_sse_kejadian` | Teks `terfilter topik area · N kejadian` **tidak ada di src**; panel kejadian kini di `/sistem` lewat `EventFeed`, dan `EventFeed` sendiri juga yatim. `?sub=cockpit` tak valid. |

Pelajaran yang dicatat: `sub` yang valid di `/crypto` hanya
`ringkas`, `sinyal`, `uji`, `eksekusi`. Spec yang menyebut `cockpit`/`setup`
sudah pasti gagal.

Celah yang ditemukan di alat pemeriksa: versi pertama hanya membaca
`getByText('literal')` dan **melewatkan `getByText(/regex/)`** — itu sebabnya
`cek_sse_kejadian` lolos dari saringan awal.

## Gelombang keempat: teks/atribut yang dicari sudah tidak ada

Diperiksa dari **pesan error Playwright yang asli**, bukan dari membaca kode:
untuk setiap test yang gagal, locator yang tidak ketemu dicek langsung ke `src/`.

| Spec | Yang dicari | Status |
|---|---|---|
| `cek_badge_mode` | `sumber: OKX` | hilang |
| `cek_forex_peluang` | `Dompet Paper Forex` | hilang |
| `cek_invariant_idx` (2 test) | `Dompet Paper IDX` | hilang |
| `cek_idx_peluang` | `Beli Sore Jual Pagi` | hilang |
| `cek_sistem_mesin` | `LP Agent · likuiditas Solana` | hilang |
| `cek_ikon_target` | `nav[aria-label="Navigasi area"]` | atribut hilang |
| `cek_gate_idx` | `Gate live-trading — centang otomatis` | teks ada, tapi di `KartuGateSetup` yang **yatim** |

## Yang TIDAK dipensiunkan, dan alasannya

Beberapa kegagalan ternyata **bug nyata**, dan dua di antaranya sudah diperbaiki di
commit yang sama (bukan dengan melonggarkan assert):

- `a11y` — pelanggaran kontras nyata: angka `02`–`05` di `OyenzaToolsSuite.svelte`
  memakai `opacity: 0.6` di atas `#16181a` → **3,56:1** (WCAG AA butuh 4,5:1).
  Dinaikkan ke `0.75` (≈4,9:1). Ditambah link di `/masuk` yang hanya diwarnai tanpa
  garis bawah (melanggar WCAG 1.4.1) → kini selalu bergaris. **8/8 lulus.**

## Akar sesi yang menipu (diperbaiki 3 Nov)

Gejala: `cek_verdict` gagal dengan **"verdict is not iterable"**, `qa-lengkap` timeout di
`loginUi`. Tampak seperti dua bug, ternyata satu sebab.

API menyetel cookie `wr_session` dengan **`Secure=true`** (`auth.cookie_secure()`).
Runner memakai `http://127.0.0.1:4174`, dan **browser menolak mengirim cookie `Secure`
lewat HTTP**. Akibatnya login membalas 200, tetapi setiap request sesi berikutnya 401 —
dan spec melaporkan galat yang menyesatkan, bukan "sesi tidak terpakai".

Bukti yang membedakan dugaan dari fakta: request dengan header `Cookie` **eksplisit**
dibalas 200, request tanpa header 401, padahal cookie ada di jar konteks.

Perbaikan (konfigurasi, bukan melonggarkan assert):
- API uji dijalankan dengan `WARROOM_COOKIE_SECURE=0` — sudah tersedia di `auth.py`
  sebagai jalur resmi untuk pengujian lokal. Produksi di balik TLS tetap `Secure`.
- `loginLewat()` tidak lagi memakai `page.request` untuk memeriksa sesi (itu tidak
  membawa cookie konteks); kini login lalu membuktikan sesi lewat `fetch` dari halaman.
  Bila sesi tetap mati, ia melempar pesan yang menyebut penyebabnya.

`qa-lengkap` TETAP gagal, dan itu wajar: ia memakai akun asli owner/operator dari
`~/.config/warroom/accounts.env`, sedangkan API uji memakai DB tes yang hanya berisi
`uji-web`. Akun `owner` **tidak ada** di DB tes → "kredensial tidak sah". Untuk
menjalankannya perlu akun uji owner+operator disemai ke DB tes.

## Kalau mau dihidupkan lagi

1. Pasang kembali komponennya ke route yang tepat.
2. Pindahkan spec dari folder ini kembali ke `e2e/`.
3. Jalankan `npx playwright test <spec>` dan pastikan lulus **karena fiturnya ada**,
   bukan karena assert dilonggarkan.

Spec di sini tidak dijalankan (`playwright.config.ts` memakai `testDir: 'e2e'` dan
tidak merekursif ke folder ini), jadi tidak menambah waktu CI.

## Status akhir 3 Nov: 12 sisa kegagalan sudah diklasifikasi

Diukur dengan menelusuri graf impor dari `src/routes/` (bukan grep teks — teks bisa
"ADA" tapi di komponen yatim). **42 dari 71 komponen** terjangkau dari route.

### A. Yatim — mustahil lulus, apa pun datanya

| Spec | Yang dicari | Di mana |
|---|---|---|
| `cek_aturan_gate` | `Nilai per Aturan Gate` | tidak ada di komponen mana pun |
| `cek_gmgn_status` | `Memecoin` | `PasarGmgn` (yatim) |
| `cek_market` (2 test) | `Sinyal & Entry Setup` | `MarketSignal` (yatim) |
| `cek_mode_utama` | `section[aria-live]` | `KepalaVerdict` (yatim) |
| `cek_idx_vonis` | `Dompet Paper` | `DompetPasar`/`DompetLintasMarket` (yatim) |

### B. Dirender, gagal karena data

| Spec | Sebab |
|---|---|
| `cek_home` | timestamp sinyal belum diisi |
| `cek_jurnal_ekuitas` | butuh `kinerja.n_titik > 0`; `/journal/performance` balas 503 "Belum ada riwayat ekuitas" |
| `cek_poly_be_wr` | tabel per-arm BE-WR butuh data arm |
| `screenshot` | tab "Riset" di `/polymarket` |

### C. Butuh produksi

`cek_verifikasi-website` (2 test) — membalas 503/401 terhadap stack lokal.

## Gelombang final (3 Nov): diselesaikan sampai selesai

Ditelusuri dengan **graf impor rekursif** dari `src/routes/` — 45 dari 92 komponen
`.svelte` benar-benar terjangkau. (Versi pertama skrip ini hanya membaca
`src/lib/components/*.svelte` sehingga melewatkan `components/info/`, dan sempat
salah menyimpulkan.)

### Dipensiunkan: UI-nya tidak ada lagi

| Spec | Sebab |
|---|---|
| `cek_aturan_gate` | `Nilai per Aturan Gate` tidak ada di .svelte mana pun |
| `cek_gmgn_status` | Kartu status hidup ada di `PasarGmgn` (yatim). Yang tersisa hanya baris tabel penjelasan statis di `/info` |
| `cek_market` (2 test) | Memakai 5 `?sub=` sekaligus (`setup`, `struktur`, `bsjp`, `arm`, `lp`) — **tidak satu pun valid** |
| `cek_mode_utama` | `section[aria-live="polite"]` hanya ada di `KepalaVerdict` (yatim) |
| `cek_idx_vonis` | `/idx` **tidak punya penanganan `sub` sama sekali**; kolomnya Kode/Harga/Perubahan/VWAP — tanpa WR/DD/VONIS |
| `cek_poly_be_wr` | `/polymarket` hanya merender `StandbyPasar`; `AkurasiPasar` (pemilik `BE-WR`) tidak diimpor apa pun |

### Bukan stale — diperbaiki atau diberi data

| Spec | Tindakan |
|---|---|
| `cek_home` | Assert kesegaran kini sadar-data: pasar tanpa sinyal dikecualikan, pasar yang PUNYA sinyal tetap wajib menyebut waktu |
| `cek_jurnal_ekuitas` | Disemai deret `mt5_snapshot` (30 titik) → `n_titik=30`, drawdown 5,648% terhitung nyata |
| `screenshot` | Entri `polymarket-riset` dilepas dari daftar SUB (tidak ada tab `Riset`); `sistem-kebijakan` tetap |
| `cek_verifikasi-website` | Butuh produksi: kini butuh opt-in `WARROOM_VERIFIKASI_PRODUKSI=1`, bukan dilewati diam-diam |
