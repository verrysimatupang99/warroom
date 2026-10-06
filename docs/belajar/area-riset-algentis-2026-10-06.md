# Area Riset — mengikuti arsitektur algentis (6 Okt 2026)

Permintaan pemilik: *"seratus persen ikutin algentis, untuk pemakaian pribadi"*.

## Batas yang dipisahkan (dan alasannya)

Permintaan itu mengandung dua hal berbeda; hanya satu yang bisa diikuti penuh:

| Aspek | Ditiru? | Alasan |
|---|---|---|
| Struktur produk, tata letak, komponen, sistem visual, interaksi | **Ya, penuh** | Meniru desain itu praktik normal; sah. |
| Teks/kalimat algentis | **Tidak** | Yang diatur hak cipta adalah **isi**, bukan tampilan. UU 28/2014 pengecualian pemakaian pribadi itu sempit. Ditulis sendiri. |
| Nama & logo "Algentis" | **Tidak** | Merek dagang. Tetap "War Room". |

Catatan praktis: ini VPS **publik**; yang berisiko bila ada keluhan bukan "niat komersil",
tapi hosting. Karena itu batas ini dipegang meski pemakaiannya pribadi.

## Peta algentis → War Room

Algentis punya 12 tautan nav; **8 relevan** untuk dashboard, sisanya pemasaran
(membership/pricing/why) yang tidak berlaku untuk alat pribadi.

| Halaman algentis | Isi | Padanan War Room | Status |
|---|---|---|---|
| `/performance` | stat + trades + PnL per pair + top winners | **Riset → Kinerja** | ✅ |
| `/calendar` | kalender ekonomi | **Riset → Kalender** | ✅ |
| `/tools` | position size, likuidasi, risk/reward | **Riset → Alat** | ✅ |
| `/system` | cara agen bekerja | — | belum |
| `/news` | berita pasar | — | belum (butuh sumber berita) |
| `/learn` | panduan | `docs/belajar/` sudah ada | sebagian |
| `/faq` | tanya-jawab | — | belum |
| `/membership`, `/pricing` | langganan | — | tidak relevan |

## Yang dibangun

Area baru **`/riset`** (ikon ⌁), tiga tab — URL = sumber kebenaran:

**Kinerja** — statistik dari fakta `equity` (total R, win-rate, trade, expectancy,
max DD), tabel **trade terakhir** dari ledger, dan **PnL per pair** dengan bar proporsi
(dari titik equity nyata: LINK +2,34R, HYPE +1,00R, FET +0,50R, SOL/SUI 0,00R).

**Kalender** — agenda makro dari `bagian.macro`: **82 event nyata**, waktu WIB, dampak
High/Med/Low (pill berwarna), forecast, sebelumnya.

**Alat** — kalkulator position size, likuidasi (perkiraan), risk/reward. Murni hitung,
**tak menyentuh API**. Fee memakai bps yang diisi pengguna, bukan asumsi. Ada catatan
jujur bahwa likuidasi dihitung kasar (isolated, tanpa margin pemeliharaan).

## Verifikasi

| Uji | Hasil |
|---|---|
| lint-token | bersih (40 berkas) |
| svelte-check | 0 error |
| vitest | 35 lulus |
| pytest | 663 lulus |
| ruff | bersih |
| detektor | 0 pelanggaran |
| Overflow | 0 di **9 kombinasi** (3 lebar × 3 tab) |

Tabel dibungkus pembungkus gulir + `min-width` supaya menggulir **di dalam bingkai**,
tidak melebarkan halaman (panduan ux).

Commit `0e85426`.
