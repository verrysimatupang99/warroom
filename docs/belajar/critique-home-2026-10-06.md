# Critique Home War Room — 6 Okt 2026

**Method:** degraded — dua asesmen dijalankan subagent terpisah, tetapi **pembungkusan
keluaran keduanya gagal** (`invalid_output_contract_schema`): skema output contract tidak
tersedia di konteks anak. Kerja mereka **selesai dan substansinya terselamatkan** dari
transkrip di `~/.hermes/cache/delegation/live/deleg_82400085/`, plus `temuan.json` dari ruang
kerja anak A. Tidak ada temuan yang dikarang ulang di sini.

**Dasar penilaian (dari anak A, dipertahankan apa adanya):** kode sumber asli
(`apps/web/src/routes/+page.svelte`, `KartuSinyalPasar.svelte`, `SubNav.svelte`, `app.css`)
**plus render nyata** memakai CSS ter-scope hasil build (`svelte-1uha8ag` = Home,
`svelte-m7c1ms` = Kartu) dengan data 7 pasar realistis. Semua angka kontras/ukuran
**diukur dari DOM ter-render**. Dashboard live di `:3100` di balik login; password tidak
ditebak.

---

## 1. Verdict desain-spesifisitas

**Cukup khas, tapi belum sepenuhnya memisahkan diri.**

Yang membuatnya khas: **catatan kejujuran sebagai elemen kelas satu**. Tidak ada dashboard
trading lain yang mencetak "skor ini BUKAN edge terbukti" di dalam kartunya sendiri. Ditambah
kartu kosong yang menampilkan `—` beserta alasan (bukan `0`), ini komposisi yang tidak bisa
dipakai produk lain tanpa membawa seluruh filosofinya.

Yang masih generik: kartu bertumpuk satu kolom dengan header + strip metrik + daftar kartu
adalah tata letak dashboard yang bisa dipakai apa pun.

## 2. Skor Nielsen (diukur, bukan diperkirakan)

| # | Heuristik | Skor | Isu kunci |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Strip kesegaran + umur per kartu baik; tidak ada indikator saat snapshot sedang dimuat |
| 2 | Match System / Real World | 2 | `STRONG`/`ARA` tanpa penjelasan; "edge", "break-even", "V/L" diasumsikan dipahami |
| 3 | User Control and Freedom | 3 | Tab di URL (Back berfungsi), tema bisa diganti |
| 4 | Consistency and Standards | 3 | Baik; `—warn` dipakai untuk dua makna berlawanan (lihat bawah) |
| 5 | Error Prevention | 3 | Kartu kosong jujur; tidak ada aksi destruktif di Home |
| 6 | Recognition Rather Than Recall | 2 | Skor tanpa skala; badge tier tanpa acuan; pengguna harus mengingat artinya |
| 7 | Flexibility and Efficiency | n/a | Home adalah layar baca, bukan layar kerja — pintasan keyboard tidak berlaku di sini |
| 8 | Aesthetic and Minimalist | 2 | ~13 blok vertikal sebelum satu keputusan; sorotan menduplikasi kartu (sudah diperbaiki) |
| 9 | Error Recovery | n/a | Tidak ada alur input di Home |
| 10 | Help and Documentation | 2 | Ada paragraf penjelasan, tidak ada legenda istilah |

**Total: 20/32** (dua n/a) = **63% → Acceptable**, di ambang bawah "Good". Setelah perbaikan
hari ini (duplikasi, kontras, skala) dua isu P1/P2 tertutup, jadi angka sebenarnya naik —
tapi tabel di atas adalah **hasil pengukuran sebelum perbaikan**, dan gue tidak mengubahnya
supaya bisa dibandingkan lain kali.

## 3. Cognitive load — 4 dari 8 gagal

| # | Item | Lulus? | Bukti |
|---|---|---|---|
| 1 | Fokus tunggal | ✅ | Satu halaman, satu tujuan |
| 2 | Chunking | ✅ | Kartu 5 blok, masih wajar |
| 3 | Keputusan tanpa scroll di layar kecil | ❌ | Sebelum 1 keputusan: banner + 5 chip + sorotan + kartu = **~13 blok vertikal**. Di 390px kartu pertama muncul setelah ±4 blok |
| 4 | ≤7±2 per kelompok | ✅ | Strip 5 chip; 7 pasar |
| 5 | Tidak ada duplikasi di viewport sama | ❌ | **Sorotan = kartu crypto kata-per-kata** (terbukti di DOM, sudah diperbaiki) |
| 6 | Angka punya satuan/konteks/skala | ❌ | Skor `72` tanpa `/100`; `STRONG`/`ARA` tanpa penjelasan (sudah diperbaiki sebagian) |
| 7 | Minimal pilihan | ✅ | Kartu bukan pilihan, hanya bacaan |
| 8 | Progressive disclosure | ❌ | Semua metrik tiap kartu ditampilkan penuh; tidak ada tahap |

## 4. Kontras — diukur dari CSS asli

**Normal (lolos):** label mikro 11px 8,39:1 · nama 13px 8,08:1 · alasan 12px 12,14:1 ·
catatan jujur 11px 13,16:1 · skor 28px 16,09:1 — semua ≥ AA.

**Kartu kosong dengan `opacity: 0.6` (GAGAL):** alasan `--text-3` 12px → **3,77:1**, di bawah
ambang AA 4,5:1. Dua lain di ambang: `--text-2` 4,80:1, warn 4,63:1.

**Sudah diperbaiki:** opacity dihapus, latar/border yang dilemahkan.

## 5. Yang bekerja baik

- **Catatan kejujuran sebagai elemen kelas satu** — "belum terverifikasi" tidak bisa
  disembunyikan tanpa menghapusnya dari kartu.
- **Kartu kosong jujur** — `—` + alasan, bukan `0`; tiga kartu kosong diuji dan tetap
  menyebutkan kenapa.
- **Selera warna terkendali** — semua token diukur dulu (catatan di `app.css` menyebut
  `#ff3b5c` dan `#9d78ff` ditolak karena 3,88 dan 4,22), dan `!` vs `✓` dibedakan **bentuk**,
  bukan warna saja.

## 6. Masalah yang ditemukan dan sudah diperbaiki (70b8b06)

| P | Masalah | Perbaikan |
|---|---|---|
| P1 | Sorotan menduplikasi kartu kata-per-kata | Pasar yang jadi sorotan dibuang dari daftar (6 kartu → 5) |
| P1 | Kontras kartu kosong 3,77:1 (gagal AA) | Hapus `opacity`, lemahkan latar/border |
| P2 | Skor tanpa skala | `72/100` |
| P3 | "11 venue" padahal 7 area | Diganti "7 area" |

## 7. Persona

**Alex (Power User):** tidak ada pintasan keyboard sama sekali di Home. 11 dari 14 elemen
interaktif < 44px (rail nav 38px). Untuk operator yang membukanya berkali-kali sehari,
memindahkan tangan ke mouse setiap kali adalah biaya nyata.

**Sam (Accessibility):** temuan utama sudah ditutup (kontras kartu kosong, bentuk membedakan
`!`/`✓`). Sisa: hanya **satu `<h1>`, tidak ada `h2`/`h3`** untuk section (strip / sorotan /
daftar) — pembaca layar tidak bisa melompat antar bagian.

## 8. Belum diperbaiki (perlu keputusan atau kerja lanjutan)

- **Hierarki heading datar** — perlu `h2` untuk tiap section.
- **Target sentuh < 44px** di rail nav.
- **`--warn` dua makna** — kuning yang sama untuk "Terverifikasi" dan "Fakta basi"; warna
  sama untuk makna berlawanan.
- **`STRONG`/`ARA` tanpa penjelasan** di halaman.
- **~13 blok sebelum keputusan pertama** di layar 390px.

---

## Catatan proses (jujur)

Dua subagent **bekerja dengan baik** dan menghasilkan pengukuran nyata — anak A bahkan
membangun harness dengan CSS ter-scope asli untuk mengukurnya. Yang gagal adalah
**pembungkusan keluaran di akhir**, dan itu kesalahan gue: gue memberi `output_schema`
tanpa memastikan anak menerima definisinya. Kerjanya terselamatkan, tapi pelajarannya:
**skema keluaran tidak boleh jadi satu-satunya jalan pulang sebuah temuan.**
