# Laporan e2e CI — apa yang gagal dan kenapa (3 Nov 2026)

Dokumen ini jujur tentang status suite Playwright di CI. Ditulis supaya tidak ada
yang mengira "70 gagal = CI rusak" atau "sudah diperbaiki" padahal belum.

## Ringkas

| | Sebelum | Sesudah sesi ini |
|---|---|---|
| Berjalan di CI | tidak pernah (job belum ada) | **berjalan**, 30m35s |
| Hasil | — | **52 lulus / 70 gagal** |
| Penyebab utama | — | **komponen UI yang diuji sudah tidak di-render** |

## Yang sudah diperbaiki sesi ini

1. **Probe kesiapan API** — dulu `curl -f` ke `/api/v1/health` yang selalu 401
   (butuh sesi), sehingga job menunggu 80 detik lalu gagal padahal API hidup.
   Sekarang probe menerima status apa pun selain `000`.
2. **`vite preview` bind IPv4** — tanpa `--host 127.0.0.1`, vite hanya listen di
   `[::1]`; Playwright ke `127.0.0.1:4173` kena ECONNREFUSED.
3. **Seed user e2e** — `ops/e2e-seed-user.py` membuat user dengan scrypt + TOTP
   mati, menolak host non-loopback.
4. **Seed fakta e2e** — `ops/e2e-seed-fakta.py` menyemai `pasar_akurasi`,
   `idx_akurasi`, `dibuat`, `forex_sinyal`, `crypto_sinyal` dengan bentuk yang sama
   seperti produksi (`kind="snapshot"`, `key=<nama>`).
5. **Proxy API bisa diarahkan** — `vite.config.ts` membaca `WARROOM_API_TARGET`
   supaya suite bisa dijalankan terhadap DB tes, bukan DB produksi.
6. **Timeout 50 menit + advisory** — suite penuh butuh ~30 menit; 25 menit
   membunuh job sebelum menghasilkan apa pun.

Hasil nyata: `cek_home.spec.ts` yang dulu gagal **sekarang 2/2 lulus**, karena
fakta pasar tersemai.

## Temuan utama: 33 komponen yatim

`src/lib/components/` berisi **33 komponen yang tidak diimpor siapa pun** dan
tidak masuk bundle build:

```
AkurasiPasar, AreaLoader, BentoMetrics4Box, Block, CockpitCrypto,
DataProvenanceCard, DecisionFeed, DompetLintasMarket, EquityCurve, EventFeed,
ExportLedgerCsv, ForexPair, GateBlok, KalenderDampak, KartuGateSetup,
KartuNarasi, KepalaVerdict, KinerjaBukti, MacroFundamentalLab, MarketSignal,
MarketToolsTabs, NilaiFakta, PasarCrypto, PasarForex, PasarGmgn, PasarIdx,
PasarPolymarket, Penjelasan, PolyAltBtc5m, RiskMeter, StatisticalEdgeCard,
UnderConstruction, ZonaAktif
```

Diverifikasi: `grep -c ZonaAktif build/index.js` → **0**. Komponennya memang tidak
pernah ter-render.

### Akibatnya

Tujuh spec menguji teks/panel dari komponen yatim itu:

| Spec | Menguji |
|---|---|
| `cek_zona_forex.spec.ts` | "Zona & Sinyal Mesin (Forex)" |
| `cek_home.spec.ts` | "Akurasi & PnL per Market" |
| `cek_home_revisi.spec.ts` | panel Home lama |
| `cek_lipatan_home.spec.ts` | lipatan Home lama |
| `cek_perbaikan.spec.ts` | panel perbaikan |
| `cek_rombak.spec.ts` | panel rombak |
| `cek_bukti.spec.ts` | tabel tujuh kolom riset |

Ini **bukan** masalah infrastruktur CI. Ini utang teknis: UI-nya pernah ada, lalu
diganti/dilepas, tapi test-nya tidak ikut dipensiunkan.

## Dua pilihan yang tersedia (butuh keputusan owner)

**A. Pensiunkan test yang menguji UI yang sudah pergi.**
Cepat dan jujur: tandai `test.skip` dengan alasan `komponen sudah dilepas`, atau
hapus spec-nya. Suite jadi hijau dan bermakna. Risiko: kalau komponen itu
sebenarnya **akan dikembalikan**, kita kehilangan penjaganya.

**B. Kembalikan komponennya ke halaman.**
Kalau `ZonaAktif`, `AkurasiPasar`, `PolyAltBtc5m` dkk memang masih diinginkan,
pasang kembali ke route yang tepat. Test langsung hijau **karena fiturnya ada**,
bukan karena assert dilonggarkan.

Yang **tidak boleh** dilakukan: melonggarkan assert sampai hijau. Itu membuat test
kehilangan nilainya.

## Status saat ini

- Job `e2e` **advisory** (`continue-on-error: true`) — tidak memblokir merge.
- Empat check wajib `main` tetap: `domain`, `platform`, `secrets`, `web`.
- Artefak `playwright-report` diunggah tiap run untuk diagnosa.
- **Jangan** naikkan `e2e` jadi required check sebelum 70 kegagalan ini
  diselesaikan dengan salah satu opsi di atas.
