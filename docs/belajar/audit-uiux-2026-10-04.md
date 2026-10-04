# Audit UI/UX terukur — 4 Okt 2026

Dijalankan dengan **fastmcp-browser** (32 MCP tool, WebExtensions, tanpa CDP) terhadap aplikasi
yang berjalan di `https://0xgunsl1ng3r.xyz`. Semua angka **diukur dari render nyata**, bukan
perkiraan: kontras dihitung dari `getComputedStyle` + latar efektif, ukuran target dari
`getBoundingClientRect`.

## 0. fastmcp-browser: terpasang dan **berjalan headless** ✅

Asumsi awal saya salah dan itu terbukti saat diuji: alat ini dirancang untuk browser desktop
manusia, tetapi di VPS tanpa display ini ia **tetap jalan**.

| Langkah | Hasil |
|---|---|
| `git clone` + `npm install` + `npm run build` (server) | ✅ `dist/src/index.js` |
| `node build.mjs` (ekstensi) | ✅ `dist/chromium` + `dist/firefox` |
| Server bridge | ✅ listen `127.0.0.1:9229` |
| Chromium headless (Playwright) + ekstensi | ✅ service worker termuat |
| `browser_status` via CLI | ✅ `{"connected":true,"capabilities":{tabs,dom,snapshot,screenshot,storage,cookies,evaluate,…}}` |

**Yang TIDAK berhasil:** `browser_screenshot` → `"Cannot access contents of url. Extension
manifest must request permission to access this host."` — izin host MV3 harus disetujui lewat UI
browser, dan itu tidak mungkin headless. **Audit karena itu berbasis pengukuran DOM, bukan
gambar.** (Pengganti: alat `browser_exec` kita bisa mengambil tangkapan layar.)

## 1. Yang sudah benar (dikonfirmasi, bukan diasumsikan)

| Kriteria | Hasil (11 halaman) |
|---|---|
| `lang` | ✅ `id-ID` di semua |
| Satu `<h1>` per halaman | ✅ |
| Urutan judul tanpa lompatan | ✅ (tidak ada `h2→h4`) |
| Elemen tanpa nama aksesibel | ✅ **0** di semua halaman |
| `meta viewport` | ✅ |
| Skip link ("Lompat ke konten") | ✅ ada |
| Landmark `main` | ✅ 1 per halaman |

## 2. Cacat yang **diperbaiki** — kontras (WCAG 1.4.3 AA)

**Temuan:** `.label-mikro` (dipakai badge "WARISAN" di `MoneyStrip`, tampil di **setiap** halaman)
memakai `--color-inherit: #6b7280` → **3,69:1** pada `--color-surface-2`, di bawah ambang
**4,5:1** untuk teks 11px.

Diukur di keempat latar, ternyata gagal di **semuanya**:

| Warna | bg #05070c | surface #0c1017 | surface-2 #111823 | surface-3 #16202f |
|---|---|---|---|---|
| `text-2 #a7b2c4` | 9,41 ok | 8,90 ok | 8,32 ok | 7,65 ok |
| `text-3 #7c8aa0` | 5,76 ok | 5,44 ok | 5,09 ok | 4,68 ok |
| **`inherit #6b7280` (lama)** | **4,17 GAGAL** | **3,94 GAGAL** | **3,69 GAGAL** | **3,39 GAGAL** |
| `inherit #8b93a1` (baru) | 6,51 ok | 6,16 ok | 5,76 ok | 5,29 ok |

**Perbaikan:** `--color-inherit` dan `--inherit` → `#8b93a1` (tetap redup/abu, lulus AA dengan
margin di semua latar). Dua definisi diperbaiki sekaligus karena keduanya memuat nilai sama.

**Verifikasi ulang setelah perbaikan (diukur lagi, bukan diasumsikan):**

```
/         kontras gagal: 0   (sebelumnya 1)
/bandar   kontras gagal: 0   (sebelumnya 1)
/lp       kontras gagal: 0   (sebelumnya 1)
```

## 3. Temuan yang **TIDAK** saya ubah (keputusan desain, bukan compliance)

| Temuan | Skala | Catatan |
|---|---|---|
| Teks 11px (`text-11`) | **51 pemakaian** | WCAG tidak menetapkan ukuran minimum font, jadi ini **bukan** pelanggaran. Tetapi 29–55 elemen per halaman di bawah 12px adalah beban baca nyata, terutama di ponsel. Menaikkan ke 12px akan mengubah kepadatan tata letak — itu keputusan pemilik, bukan saya. |
| `text-10` (10px) | 2 pemakaian | Paling kecil; kandidat pertama kalau ingin dinaikkan. |
| Tanpa landmark `<footer>` | 11 halaman | Bukan kegagalan, tapi pembaca layar kehilangan titik navigasi penutup. |
| 2 tautan tinggi 13–14px | `/` | **Dikecualikan** WCAG 2.5.8 (pengecualian *inline*: tautan di dalam kalimat). Tidak dianggap cacat. |
| Skip link 1×1 px | `/` | Normal — tersembunyi sampai difokus keyboard. Bukan cacat. |

## 4. Koreksi atas pengukuran saya sendiri

Laporan pertama saya menyebut `/gmgn`, `/polymarket`, `/sistem` "angkanya identik → halaman
kosong". **Itu salah, dan penyebabnya cara saya mengukur**: saya membaca `document.body.innerText`
yang dipotong 600 karakter, sehingga yang terukur adalah **chrome bersama** (nav + status bar),
bukan isi halaman.

Diukur ulang pada `<main>`:

```
/gmgn        1.528 karakter konten   (bukan kosong)
/polymarket  3.637 karakter konten
/sistem        420 karakter konten
```

Juga: sub-rute seperti `/gmgn/radar`, `/crypto/cockpit` mengembalikan **404** — desainnya memang
satu halaman per area dengan tab di dalam halaman, bukan rute terpisah. Itu pilihan yang sah.

## 5. Catatan metode

- Audit ini **mengukur**, tidak mengira-ngira: rasio kontras dihitung dari warna terhitung +
  latar efektif (menelusuri pohon induk sampai latar tidak transparan).
- Keterbatasan: tidak ada tangkapan layar (izin host ekstensi, lihat §0), tidak menguji keyboard
  secara nyata (hanya elemen terlihat), tidak menguji pembaca layar.
- Yang belum diuji: **responsif** (audit dijalankan pada 1440×900), **fokus terlihat**, dan
  **kontras pada keadaan hover/focus**.
