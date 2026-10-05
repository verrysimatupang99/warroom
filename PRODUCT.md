# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Pengguna utama (terkonfirmasi dari brief):** satu operator — pemilik proyek, yang menjalankan
dan menilai sendiri sistem ini. Dia bekerja di terminal (SSH ke box), memakai Hermes Agent
sebagai orkestrator, dan punya riwayat panjang menjalankan bot trading (Polymarket, meme coin,
forex, IDX).

**Situasi pakai:** membuka dashboard **berkali-kali sehari**, sering di layar kecil, sering
sebelum/sesudah jam bursa. Yang dicari bukan "menjelajah fitur" melainkan **jawaban cepat**:
pasar mana yang punya sinyal, seberapa layak, dan apa risikonya.

**Pekerjaan yang diselesaikan:** memutuskan **apakah ada sesuatu yang layak dieksekusi** pada
tiap pasar yang dia pantau — lalu menyiapkan keputusan itu lewat paper trade sebelum uang nyata.

> **ASUMSI (belum dikonfirmasi, ditandai karena init hanya boleh mencatat fakta terkonfirmasi):**
> "asesmen cepat sebelum/sesudah sesi bursa" dan "layar kecil" adalah inferensi dari pola kerja
> (SSH, cron jam bursa, Telegram sebagai kanal). Kalau salah, koreksi bagian ini.

## Product Purpose

War Room adalah **satu tempat untuk melihat dan mengoperasikan seluruh sistem trading**:
crypto, Polymarket, meme coin, forex, IDX.

Tujuan: pengguna bisa melihat **semua pasar sekaligus**, tahu mana yang punya sinyal terbaik,
dan menelusuri **kenapa** sampai ke buktinya — tanpa berpindah alat.

**Sukses berarti:** saat pengguna membuka Home, dia tahu dalam beberapa detik pasar mana yang
punya peluang, seberapa kuat, dan seberapa layak dipercaya angkanya — lalu bisa langsung
menelusuri ke detail atau mengeksekusi lewat paper/live.

## Positioning

**Sinyal pertama-tama, bukan bagan pertama-tama.**

Dua hal yang membedakannya dari dashboard trading lain, dan keduanya sudah terpasang di kode:

1. **Satu kartu sinyal terbaik per pasar di Home.** Bukan dinding widget, bukan grid grafik.
   Tiap pasar menyumbang satu kesimpulan, bukan satu panel.
2. **`catatan_kejujuran` wajib di setiap angka.** Sistem ini menandai sendiri mana angka yang
   **terukur** dan mana yang **belum terverifikasi**, dan menolak menampilkan `0` ketika artinya
   "tidak ada data" (kosong ditampilkan `—`, bukan `0`).

Posisi ini bukan hiasan: ia lahir dari temuan nyata di repo ini — win-rate "62,6%" yang ternyata
palsu, angka andalan "+228R" yang tidak bisa direproduksi, dan edge BSJP yang berlabel
`terverifikasi_di_warroom=False`. **Dashboard yang bisa berbohong tidak berguna untuk trading.**

## Operating Context

- **Paper trade dulu, 1:1 dengan live.** Paper dan live harus melewati **jalur keputusan yang
  sama** (`execution/keputusan.py`); yang berbeda hanya sakelar eksekusi. Ini prinsip yang sudah
  dikonfirmasi pengguna.
- **Sistem berjalan sendiri.** Worker + cron menulis snapshot tiap ~15 menit; halaman membaca
  snapshot itu. UI bukan sumber kebenaran, ia **menampilkan** kebenaran yang sudah dihitung.
- **Banyak pasar, sumber berbeda:** Polymarket (Gamma/CLOB), crypto (GMGN/DexScreener),
  forex (agenda makro), IDX (TradingView + arsip tick Arjum), meme coin.
- **Angka datang dengan tingkat kepercayaan berbeda** dan itu bagian normal dari kerja, bukan
  pengecualian.
- **Jalur alternatif:** kanal Telegram (thread 616 untuk IDX), selain dashboard ini.

## Capabilities and Constraints

**Kapabilitas terkonfirmasi:**
- Snapshot produksi dengan **13 bagian**: `bandarmologi`, `bsjp`, `crypto`, `dex`, `forex`,
  `hyperliquid`, `idx`, `idx616`, `idx_tv`, `lp`, `macro`, `memecoin`, `overextended`.
- Konsep sinyal per pasar (`SinyalPasar`) dengan **skor kosong = `None`/`—`, bukan `0`**.
- **BSJP** (beli sore jual pagi, IDX): filter teruji walk-forward — ARA dan subset STRONG;
  mode `bersumber` (angka dari sumber) vs `terukur` (dihitung ulang di sini).
- **Paper trade** dengan jalur keputusan bersama; risk gate; kill switch fail-closed.
- Auth peran (`owner` dll) di API; situs sudah punya tema & token sendiri di `app.css`.

**Batasan:**
- **UI tidak boleh mengarang angka.** Setiap angka yang belum terverifikasi wajib membawa
  catatannya. Ini batasan produk, bukan preferensi visual.
- **Kuota API nyata dan terbatas** (Arjum: `history`/`history_yf` = 99% pemakaian). UI tidak
  boleh menambah panggilan API yang tidak perlu.
- **Snapshot, bukan realtime.** Data bisa setua satu siklus; UI harus menyatakan kesegarannya
  daripada berpura-pura hidup.
- **Satu pengguna.** Tidak perlu multi-tenant, tim, atau onboarding pengguna baru.
- **7 area** (hasil penggabungan dari 11) sudah ditetapkan berdasarkan sumber data, bukan selera.

## Brand Commitments

- **Nama:** "War Room" — pengguna menyebutnya begitu secara konsisten.
- Bahasa antarmuka: **Indonesia** (istilah teknis boleh Inggris: paper trade, snapshot, edge).
- Tema, palet, dan font yang sudah ada di `app.css` **mengikat** — redesign memakai sistem yang
  ada, bukan menggantinya dengan tema baru.

## Evidence on Hand

**Data nyata yang sudah ada (bukan contoh karangan):**
- Snapshot produksi hidup: 13 bagian, termasuk `bsjp` (1 STRONG / 2 ARA pada pemindaian terakhir).
- Riwayat tick IDX: 24,9 juta baris di arsip Tencent (SMA10 dihitung dari sini).
- Angka terukur yang sudah ada nilainya: biaya fee+slippage (BTC 10,0 bps / FET 11,9 bps),
  edge BSJP (+0,86% STRONG / +1,06% ARA, dari walk-forward sumber).
- Audit: 200 resolusi, 47 jendela peluang nyata, win-rate layak-dagang **14,8%** (di bawah
  break-even ~77%), versus **62,6% yang menyesatkan** jika semua alasan dicampur.

**Yang TIDAK boleh dikarang (ketiadaan yang harus dihormati):**
- Jangan mengisi angka placeholder, grafik contoh, atau testimoni.
- Jangan menampilkan `0` untuk "tidak ada data".
- Jangan mengklaim "terverifikasi" untuk angka yang belum dihitung ulang di repo ini.

## Product Principles

1. **Jujur mengalahkan terlihat bagus.** Angka yang belum pasti harus terlihat belum pasti.
   `76,25%` yang belum terverifikasi wajib terlihat berbeda dari `76,25%` yang terukur.
2. **Kosong itu jawaban.** "Tidak ada sinyal" adalah informasi, bukan kegagalan render.
   Tampilkan alasan kosongnya, jangan isi dengan nol.
3. **Satu keputusan per pasar.** Home menjawab "mana yang layak?" dulu; detail menyusul.
   Menumpuk semua metrik di depan = memindahkan kerja ke mata pengguna.
4. **Paper dan live adalah jalur yang sama.** Yang berbeda hanya sakelar. UI tidak boleh
   membuat paper terasa seperti mainan dan live terasa seperti mesin terpisah.
5. **UI tidak menambah beban API.** Menampilkan lebih banyak bukan alasan memanggil lebih banyak.

## Accessibility & Inclusion

- Situs **publik sebagian** (halaman utama bisa diakses), jadi kontras dan keterbacaan harus
  memenuhi standar umum — bukan hanya nyaman untuk pembuatnya.
- Angka adalah isi utama: harus terbaca jelas di layar kecil, dan **tidak boleh bergantung pada
  warna saja** (hijau/merah) untuk menyampaikan untung/rugi — perlu penanda teks atau bentuk.
- Status yang penting bagi keselamatan uang (kill switch, mode live/paper) harus punya penanda
  yang tidak mengandalkan warna saja.
