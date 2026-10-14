# ADR: Normalisasi Penamaan Kode — Bahasa Inggris

Status: ditetapkan 14 Okt 2026.
Pengambil keputusan: owner (arahan: "Inggris konsisten").

## Konteks

Repo mencampur dua bahasa pada nama modul & simbol:

- Inggris: `adapters`, `autonomy`, `gate`, `outcome`, `paper`, `research`, `splits`,
  `strategy`, `verdict`, `signal`, `forward`, `specs`.
- Indonesia: `sinyal`, `retensi` (+ istilah domain yang lazim: "sinyal", "kejujuran").

Nama `signal.py` (kontrak paper-signal generik) dan `sinyal.py` (sinyal terbaik per
pasar untuk UI) hanya berbeda SATU huruf tetapi **maknanya berbeda** — sumber
kebingungan nyata saat menelusuri kode.

## Keputusan

**Nama modul & berkas kode memakai Bahasa Inggris.** Istilah domain yang sudah baku
dalam percakapan produk (mis. kata "sinyal" di teks UI/dokumen) TIDAK dipaksa
diterjemahkan — yang dinormalisasi adalah **identifier kode**.

### Pemetaan (fase 1 — nama modul)

| Sebelum | Sesudah | Catatan |
|---|---|---|
| `warroom_core/sinyal.py` | `warroom_core/market_signal.py` | `signal.py` (kontrak paper) dipertahankan |
| `warroom_core/retensi.py` | `warroom_core/retention.py` | |
| `live_trading/lp_verifikasi.py` | `live_trading/lp_verification.py` | |
| `tests/test_sinyal.py` | `tests/test_market_signal.py` | |
| `tests/test_retensi.py` | `tests/test_retention.py` | |

`verdict.py` dipertahankan (sudah Inggris, dan maknanya jelas: verdict per pasar).

## Yang TIDAK diubah (sengaja)

- **Kunci data / nama fakta**: `"lp_verifikasi"` sebagai kunci fakta & field JSON
  (`snap["lp_verifikasi"]`, `areas.py`) — mengubahnya = memutus UI & data lama.
  Normalisasi **tidak** menyentuh nama fakta; itu kontrak data, bukan nama kode.
- **Nama job worker**: `"retensi"`, `"verdict-sync"`, dst. — identifier runtime di
  tabel `jobs`. Mengubahnya butuh migrasi data; di luar cakupan fase ini.
- **Istilah domain di teks** (docstring, pesan UI "sinyal", "kejujuran").

## Fase berikutnya (belum dikerjakan)

Normalisasi **nama fungsi/simbol** (mis. `sinyal_terbaik_per_pasar`,
`verdict_pasar`, `_contoh_*`) dan **nama variabel** campuran. Ini jauh lebih luas &
menyentuh output API; dikerjakan setelah fase 1 stabil, dengan jaminan AST + tes.

## Jaminan

Fase 1 diverifikasi: `ruff check .` bersih, 815 tes lulus, `ops/ci-local.sh` hijau,
dan **tak ada sisa referensi** nama modul lama (`grep` bersih).
