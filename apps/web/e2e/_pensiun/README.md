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

## Kalau mau dihidupkan lagi

1. Pasang kembali komponennya ke route yang tepat.
2. Pindahkan spec dari folder ini kembali ke `e2e/`.
3. Jalankan `npx playwright test <spec>` dan pastikan lulus **karena fiturnya ada**,
   bukan karena assert dilonggarkan.

Spec di sini tidak dijalankan (`playwright.config.ts` memakai `testDir: 'e2e'` dan
tidak merekursif ke folder ini), jadi tidak menambah waktu CI.
