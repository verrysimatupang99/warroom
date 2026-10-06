# Rombak total UI/UX — "Algentis gelap" (6 Okt 2026)

Pemilik: *"rombak total bukan modifikasi yang ada doang"*, arah **algentis.xyz**, **gelap saja**,
font dipertahankan, tujuan 3 detik **"langsung tahu ada peluang atau tidak"**.

## 0. Kenapa rombak, bukan tambal

Audit sebelum rombak menemukan akar "belum sesuai" — dan semuanya **terukur**, bukan selera:

| Temuan | Angka |
|---|---|
| Skala tipografi rusak | **18 ukuran font** di satu layar Home (panduan: maks 4–6) |
| Sumbernya | **12 nilai `rem` liar** di app.css bertabrakan dengan token px |
| Terlalu lapang | gap grid **16px** (panduan 8), padding kartu **16–18px** (panduan 12), rail **320px** (panduan 240) |
| Dua sistem tata letak | Home (rail+grid) vs halaman area (konten penuh) = terasa dua produk |
| Enam aksen bersaing | cyan, hijau, merah, violet, emas, oranye di satu layar |

Karena itu arah lama **diganti**, bukan ditambal.

## 1. Arah baru — apa yang diambil dari algentis

Algentis dibedah langsung (HTML/CSS publik, bukan tebakan). Menariknya, yang kupakai dulu
adalah versi *panel*-nya; situsnya sendiri **terang krem**. Terjemahan ke gelap:

| Aspek | Algentis (terang) | War Room (gelap) |
|---|---|---|
| Latar | `#F3F1EA` krem | `#0A0C0B` warm-dark |
| Permukaan | `#FFFFFF` | `#111514` berlapis |
| Tinta | `#0E1110` | `#F2F0E9` (krem, bukan putih) |
| Aksen | mint `#34E39A` | sama |
| Peringatan | `#F5B83D` | sama |
| Font | Unbounded/Jakarta/Mono | **dipertahankan**: Space Grotesk/Inter/JetBrains Mono |

**Pembagian makna (satu warna satu arti):** mint = aksi/untung · merah = rugi/stop ·
kuning = peringatan/target. Aksen lama dipensiunkan.

Kontras diukur dulu: mint 11,0–11,8:1 · kuning 8,9–11,0:1 · merah 5,7–7,1:1 ·
teks krem 13,9–17,2:1 · redup 4,9–6,1:1 — semua lolos AA.

## 2. Yang dirombak

**Fondasi**
- Token 3 lapis diisi palet baru; **tema terang dihapus** (gelap saja). `TemaToggle`
  dihapus, `app.html` disederhanakan, `color-scheme: dark`.
- **29 ukuran `rem`** dinormalkan ke token → Home dari 18 ukuran font jadi **12**,
  halaman area **9**.
- Kerapatan data-dense: gap grid 8px, padding kartu 12px, rail 240px.

**Cangkang**
- **Rail kiri 240px dihapus** → **NavBar horizontal** (sticky) + konten terpusat 76rem.
- **TopBar ditulis ulang**: satu baris status padat (mode · aliran · fakta · alert · jam).
  MoneyStrip besar di header dihapus.
- Satu navigasi per lebar: horizontal ≥768px, BottomNav <768px.

**Home**
- Ticker pasar → **satu verdikt besar** ("4 PELUANG") → **setup entry** (masuk/stop/target/
  risiko) → baris per pasar. Pratinjau dipromosikan jadi Home sungguhan.

**Kode mati dibuang**
- Komponen: `KolomPasar`, `KartuSinyalPasar` (+test), `MoneyStrip` (+test), `RailNav`,
  `TemaToggle`.
- CSS: seluruh blok cangkang warisan beebots (`.app`/`.top`/`.bee*`/`.cap-banner`/`.rail`/
  `.board-*`/`.toast*`) — 0 pemakaian. **app.css 820 → 332 baris.**

## 3. Verifikasi (semua dijalankan)

| Uji | Hasil |
|---|---|
| lint-token | bersih (39 berkas) |
| svelte-check | 0 error |
| vitest | 35 lulus |
| pytest | 663 lulus |
| ruff | bersih |
| detektor impeccable | 0 pelanggaran |
| Responsif 4 lebar × 7 rute | **0 overflow** (28 kombinasi) |
| Kontras | **0 gagal** (terburuk 5,44:1) |
| a11y | 0 elemen tanpa nama · 1 `<h1>`/rute |
| Ukuran font/layar | Home 12 · area 9 (dari 18) |

## 4. Commit

`78c7be8` pratinjau + perbaikan linter · `371edfc` **rombak total** · `d89cb8d` dedup navigasi mobile.

## 5. Catatan jujur

- **Halaman area belum dirombak strukturnya** seperti Home — mereka sudah ikut palet,
  tipografi, kerapatan, dan cangkang baru lewat token, tapi tata letak internal
  (AreaView 1.700 baris) masih susunan lama. Bila mau, langkah berikutnya menyusun ulang
  tiap area dengan pola yang sama seperti Home (verdikt → setup → rincian).
- **`--rail-w` masih ada** sebagai token meski rail kiri dihapus — dipakai halaman area
  untuk kolom sampingnya.
