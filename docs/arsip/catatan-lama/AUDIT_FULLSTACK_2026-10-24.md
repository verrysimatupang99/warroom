# Audit Fullstack Codebase War Room

Tanggal: 24 Okt 2026 | Repo: `~/warroom` | Branch: `main` | Commit saat audit: `0fa3937`

---

## 1. Inventaris

| Metrik | Nilai |
|---|---|
| Commit | 532 |
| File terlacak git | 892 |
| Baris Python | **67.785** (392 file) |
| Baris TS/Svelte | **19.275** |
| Ukuran repo (tanpa .git/node_modules/.venv) | 1,8 GB — **1,8 GB di antaranya `ops/docker-mt5/`** |
| `.git` | 114 MB (pack 109 MB) |
| File terbesar terlacak | `uv.lock` 0,4 MB |
| Bundle web | 2,4 MB total, 424 KB JS |

Komposisi: `apps` 169 MB, `packages` 11 MB, `docs` 9,2 MB, `services` 4,7 MB.

---

## 2. Gerbang kualitas — SEMUA LULUS

| Pemeriksaan | Hasil |
|---|---|
| `ruff check .` | **All checks passed** |
| `pytest packages/core` | **lulus semua** (~170 tes) |
| `pytest services/api/tests` | **lulus semua** (~108 tes) |
| `pytest` seluruh repo | **1.035 tes terkoleksi, 0 gagal** |
| `svelte-check` | **0 errors, 0 warnings** |
| `npm audit --omit=dev` | **0 vulnerabilities** (info/low/moderate/high/critical) |
| `systemctl --failed` | **0 unit gagal** |
| Error log 24 jam (api/web/worker) | **0** |
| `ops/check-file-size.py` | 2 peringatan, 0 gagal |
| `ops/check-openapi-contract.py` | **match, 112 path** (setelah diperbaiki) |

---

## 3. Keamanan — BERSIH

| Pemeriksaan | Hasil |
|---|---|
| Private key / API key di git | **tidak ada** |
| `.env`, `credentials`, `*.pem`, `*.key` terlacak | **tidak ada** |
| Kredensial hardcoded (`password=`/`token=` literal) | **tidak ada** |
| Endpoint tanpa `dependencies=` inline | 87 dari 104 — **tetapi tetap 401** |

**Catatan penting soal 87 endpoint itu:** saya uji langsung 5 endpoint (`/cron/jobs`,
`/datasets/splits`, `/areas`, `/alerts`, `/cron/executions`) tanpa autentikasi — semuanya
mengembalikan **401 `belum login`**. Ternyata proteksi dipasang di level router:

```python
router = APIRouter(prefix="/api/v1/cron", dependencies=[Depends(auth.current_user)])
```

Jadi bukan celah. Hanya saja cara pembacaannya menyesatkan kalau melihat per-endpoint.

---

## 4. Temuan yang perlu perhatian

### K1 — Empat salinan EA, satu tertinggal (RISIKO TINGGI, sudah terbukti)

| Lokasi | md5 | Status |
|---|---|---|
| `apps/web/static/` | `6680306bd5` | ✅ |
| `apps/web/build/client/` | `6680306bd5` | ✅ |
| `/srv/private/` | `6680306bd5` | ✅ |
| `/srv/pratinjau/` | `6680306bd5` | ✅ |
| **`ops/docker-mt5/config/`** | **`e3b2f24930`** | ❌ **versi lama** |

Ini bukan teori — **hari ini** web sempat menyajikan EA 20.573 B (versi pra-`InpUseRiskSizing`)
karena salinan di `build/client` tidak ikut diperbarui. Sudah diperbaiki, tapi akar masalahnya
tetap: **tidak ada satu sumber kebenaran** untuk berkas EA.

Rekomendasi: jadikan `apps/web/static/` satu-satunya sumber, dan buat skrip yang menyalin ke
seluruh lokasi lain (atau hapus salinan yang tidak dipakai).

### K2 — 34 `except Exception: pass` (RISIKO SEDANG)

Dari 101 `except Exception`, **34 di antaranya langsung `pass`** — kegagalan hilang tanpa jejak.

Sebaran terbanyak:
| File | Jumlah |
|---|---|
| `packages/live-trading/crypto/scripts/crypto_dashboard.py` | 5 |
| `packages/live-trading/idx616/scripts/arjum_pool.py` | 3 |
| `packages/live-trading/crypto/scripts/crypto_watch_eval.py` | 3 |
| `packages/live-trading/crypto/scripts/crypto_pipeline_collect.py` | 3 |
| `packages/live-trading/src/live_trading/dompet.py` | 2 |

Semua di subsistem **crypto/idx**, bukan jalur forex. Jadi tidak memengaruhi EA XAUUSD,
tapi menyulitkan diagnosa kalau subsistem itu bermasalah.

### K3 — Dua berkas melewati anggaran baris (RISIKO RENDAH)

| Berkas | Baris |
|---|---|
| `packages/live-trading/src/live_trading/pasar.py` | 940 |
| `packages/core/src/warroom_core/market_signal.py` | 914 |

Ambang repo kemungkinan 900. Keduanya belum gagal, hanya peringatan.

### K4 — Disk 80% (RISIKO SEDANG)

```
/dev/sda1  48G  38G  9.6G  80%
```

Sisa 9,6 GB. Penyumbang terbesar: `ops/docker-mt5/` **1,8 GB** (Wine prefix MT5, gitignored,
dan **tidak ada kontainer Docker yang jalan** — `docker ps` kosong). Kandidat kuat untuk diarsipkan.

RAM sehat: 6,3 GB terpakai dari 14 GB, 8,2 GB tersedia.

### K5 — 6 TODO/FIXME (RISIKO RENDAH)

Jumlahnya kecil untuk 87 ribu baris kode. Tidak perlu tindakan.

---

## 5. Yang diperbaiki selama audit ini

| Temuan | Tindakan |
|---|---|
| 3 error `ruff` di `ops/panel_sim.py` (kode baru hari ini) | diperbaiki — import tidak terpakai, urutan import, baris >110 |
| OpenAPI drift: `/mt5/fill` dan `/mt5/panels` belum terdaftar | `check-openapi-contract.py --write` → 112 path, match |
| EA di `build/client` versi lama (20 KB) | disalin dari `static/` |
| `/srv/pratinjau` tidak ada → download publik 404 | dibuat + diisi |
| `build_id` menunjuk commit lama | `ops/set-build-id.sh` |
| **K1: 4 salinan EA tidak sinkron** | dibuat `ops/sinkron-ea.sh` — satu sumber + verifikasi md5, semua target kini `6680306bd5` |
| **K4: `ops/docker-mt5` 1,8 GB** | prefix `.wine` diarsipkan ke `/var/backups/docker-mt5-wine-20261024.tar.gz` (771 MB, 2.547 file, terverifikasi) lalu dihapus → direktori 4,6 MB, disk 81% → 79% |

---

## 6. Ringkasan skor

| Area | Status |
|---|---|
| Kualitas kode Python | 🟢 bersih (ruff) |
| Test | 🟢 278+ tes lulus |
| Type-check frontend | 🟢 0 error |
| Dependensi | 🟢 0 kerentanan |
| Keamanan rahasia | 🟢 tidak ada kunci/kredensial di git |
| Autentikasi API | 🟢 ditegakkan (401 terverifikasi) |
| Runtime | 🟢 0 unit gagal, 0 error 24 jam |
| **Konsistensi aset** | 🟡 **4 salinan EA, 1 tertinggal** |
| **Penanganan error** | 🟡 34 `except: pass` |
| **Kapasitas disk** | 🟡 80% terpakai |

**Kesimpulan: codebase sehat.** Tidak ada temuan kritis. Tiga item kuning semuanya
bersifat pemeliharaan, bukan risiko langsung ke trading — kecuali K1 yang sudah terbukti
menyebabkan insiden hari ini.
