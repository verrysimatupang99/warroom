# Gelombang 3 — Eksekusi (A/B/C) + Cek LP Agent

Tanggal: 2026-10-10 · Status: **dieksekusi atas persetujuan pemilik** ("D: semua").
Semua paper/virtual — **tidak ada uang nyata**. Gerbang live tidak disentuh.

---

## Yang dijalankan (D = semua)

### A. IDX — **ARA_HUNTER dimatikan** ✅

- `systemctl --user disable --now idx616-ara.timer`
- Verifikasi: `idx616-ara.timer -> inactive/disabled`
- **Tetap hidup:** `idx616-bsjp.timer` (active), `idx616-grader.timer` (active), `idx616-drift.timer` (active)
- Dasar: membuang ARA membalik total **−126,08R → +26,77R** (ekspektasi −0,293 → +0,315).
- **Reversibel:** `systemctl --user enable --now idx616-ara.timer`.

### B. Polymarket — **arm E baru (band 0,55–0,75)** ✅

- **Arm lama TIDAK disentuh** (B kandidat 0,70–0,95 tetap jalan; D favorit tetap jalan).
- Arm baru: `polymarket-paper-cheap.service` → `active`.
  - Data: `/var/lib/poly-paper-cheap/` · config `cheap-config.json` (ENTRY_LO 0,55 · ENTRY_HI 0,75 ·
    ahead · size $5 · jendela 45–240s · fee receipt).
  - Log boot: `band=[0.55,0.75] sides=Up/Down size=$5 window=45-240s side=ahead`.
- Dasar: BE-WR ≈ harga beli; di band 0,55–0,75 BE-WR turun → WR yang sama bisa untung.
- **Reversibel:** `sudo systemctl disable --now polymarket-paper-cheap.service` (+ hapus unit/config).

### C. GMGN — **jalur arah dimatikan, LP tetap** ✅

- `systemctl --user disable --now gmgn-paper-cycle.timer gmgn-fast-exit.timer`
- Verifikasi: keduanya `inactive/disabled`.
- **Tetap hidup:** `gmgn-dashboard.timer` (active) — hanya menampilkan; LP lewat cron
  `5 17 * * * /home/admin/gmgn-scan/lp_mark_daily.sh` (**tetap**).
- Dasar: semua grup negatif (−6% s/d −20%); gate tidak terbukti menambah nilai.
- **Reversibel:** `systemctl --user enable --now gmgn-paper-cycle.timer gmgn-fast-exit.timer`.

### D. CRYPTO / FOREX

- **CRYPTO:** tidak ada perubahan (jaga apa adanya, +0,672R expectancy).
- **FOREX:** menunggu data terisi; belum dinilai.

---

## Cek LP Agent (app.lpagent.io) — baca-saja

**Apa itu:** "LP Agent — The fastest multi-chain LP Terminal & Copy LP". Terminal likuiditas
multi-chain + fitur **Copy LP** (menyalin posisi LP orang lain).

| Aspek | Temuan |
|---|---|
| Teknologi | SPA **Next.js**, di balik **Cloudflare Turnstile** |
| Rute terbuka | `/`, `/pools` → 200 · `/api/*` → 404 |
| API publik | **Tidak ada yang terbuka** (semua di balik app + Turnstile) |
| Fitur (dari bundle) | wallet · position · pool · liquidity · LP fees · LP Terminal · Copy LP |
| Manifest | `display: standalone`, kategori finance/business |

**Relevansi untuk kita:** fitur **Copy LP**-nya sejalan dengan jalur LP yang sudah kita ukur
(`gmgn-scan` + LP Robinhood vs Meteora). Berguna sebagai **pembanding eksternal** untuk data
pool/LP. **Namun** API-nya tertutup (Turnstile), jadi tidak bisa dijadikan sumber data otomatis
tanpa kerja sama mereka. Tidak ada yang saya ubah di sana — murni pengamatan.

---

## Gerbang live (tidak tersentuh)

- `live.start` → **404/409**, `armed=false`. Tidak ada perubahan pada jalur uang nyata.

## Catatan jujur

1. Ketiga perubahan **reversibel** dengan satu perintah (tertulis di tiap bagian).
2. Arm B Polymarket **baru**, bukan penimpaan — perbandingan lama vs baru tetap bersih.
3. LP Agent: yang bisa dinilai hanya dari luar (nama, rute, manifest); isinya terkunci Turnstile.
