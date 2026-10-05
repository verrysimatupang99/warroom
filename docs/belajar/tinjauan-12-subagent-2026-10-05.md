# Tinjauan 12 subagent — 5 Okt 2026

Dijalankan oleh 12 subagent berperan (masing-masing model berbeda: qonek ×3, kiyara ×5,
nutaraline ×4) dengan repo `/home/admin/warroom` **baca-saja**. Dokumen ini mencatat apa
yang ditemukan, apa yang sudah diperbaiki, dan apa yang **belum** — supaya tidak ada
temuan yang hilang atau diam-diam dianggap selesai.

Artefak mentah tiap agen: `~/.hermes/cache/scratch/team/hasil/<id>/`.

## Sudah diperbaiki (commit menyusul di bawah)

| # | Temuan | Berkas | Perbaikan |
|---|--------|--------|-----------|
| 1 | **Biaya LLM selalu NULL → anggaran harian tak pernah jalan** (fail-open). `/etc/warroom/llm.json` tak punya `pricing`, jadi `_cost()` → `None`, `SUM(cost_usd)=0`, dan `$3/hari` tak pernah memblokir apa pun. LLMConsole selalu menampilkan `$0`. | `services/llm/.../config.py`, `gateway.py` | `pricing` ditambahkan ke bentuk baku + berkas produksi; penjaga fail-closed (`budget.failClosedOnMissingPricing`) saat harga tak lengkap & anggaran > 0. |
| 2 | **Kill switch AI fail-open.** `kill_switch_aktif()` mengembalikan `False` saat baris `ai.kill_switch` hilang → AI boleh menulis justru saat status tak terbaca. | `packages/core/.../autonomy.py` | Hanya `false` eksplisit yang membuka tulisan; baris hilang = aktif. Pagar kedua di `usulkan()`. Fakta `learner/ringkas` membaca saklar, bukan hardcode `False`. |
| 3 | **Runner TP1 tak pernah bisa ditutup.** Setelah TP1, `stop` digeser ke break-even → `compute_r` melempar `ValueError` → `evaluate` berhenti di tengah loop; posisi nyangkut selamanya. | `packages/live-trading/.../execution/paper.py` | `stop_init` menyimpan stop asli; `compute_r_exit` dipakai saat close (tidak melempar); error per-posisi diisolasi agar posisi lain tetap dievaluasi. |
| 4 | **N+1 di `GET /api/v1/areas`.** `latest_facts` dijalankan ulang per area (8 statement/permintaan). | `services/api/.../areas.py` | `latest_facts` dijalankan sekali untuk semua area. |
| 5 | **Snapshot separuh lolos penjaga.** Snapshot yang kehilangan sub-bagian tetap diterbitkan `status="ok"`. | `services/worker/.../facts_publish.py` | `BAGIAN_WAJIB` (12 kunci) + status `separuh` + event `warning` + Alert ber-dedupe. |
| 6 | **Subperintah `lt` arbitrer** via `/live/dry-run` (operator, tanpa grant/gate) — `snapshot` menimpa `state/snapshot.json`. | `services/api/.../live.py`, `app.py` | Allowlist `{depth}`; subperintah lain → **422**. |
| 7 | **Biner `lt` di API menunjuk venv yang sudah hilang** → endpoint selalu balas `tidak-ada`. | `services/api/.../live.py` | `_lt_bin()` memakai venv proses (pola yang sama dengan worker). |
| 8 | **Badge risiko `AMAN` dipatok literal** di KPI Home. | `apps/web/.../format.ts`, `+page.svelte`, `RiskMeter.svelte` | Helper bersama `statusRisikoDari`; `—` saat data tak ada. |
| 9 | **Desinkronisasi state URL ↔ sub-nav** ($effect tanpa cabang else) + `aria-current` pada tombol. | `apps/web/.../AreaView.svelte`, `SubNav.svelte` | `sub` diturunkan langsung dari URL (SSOT); pola tab ARIA (`role="tablist"`/`tab`/`aria-selected`); riwayat Back/Forward hidup. |
| 10 | **`deploy-web.sh` tanpa health gate** — bad build dilaporkan "ok". | `ops/deploy-web.sh` | Verifikasi aset `/_app/...` benar-benar tersaji (menangkap kelas kegagalan manifest-basi), timeout, dan rollback otomatis. |
| 11 | **Unit systemd tanpa batas resource.** | `/etc/systemd/system/warroom-*.service.d/limits.conf` | `MemoryMax=1G`, `CPUQuota=200%`, `TasksMax=256` (drop-in, unit utama tak diubah). |

## BELUM diperbaiki — dan kenapa

### A. Bias seleksi cross-section pada angka backtest (temuan paling berkonsekuensi)

Angka andalan repo, `total_r = +228R` (`backtest-300d.jsonl`), **tidak dapat direproduksi
maupun direkonstruksi**: daftar pair backtest dibekukan dari snapshot volume hari
penjalanan, dan tak ada satu artefak pun yang merekam daftar itu. Ketika berkas yang sama
diuji dengan alat keras yang **sudah ada di repo** (`uji_klaster_nol`), tandanya berbalik:
**−0,037 R/pair, t = −2,77 → "rugi nyata"**.

Selisih "trading R" vs "investable R" ≈ 9,7 R/pair (~320 R). Artinya angka yang terlihat
paling meyakinkan justru yang paling lemah dasarnya.

**Kenapa belum diperbaiki:** ini bukan bug kode, melainkan cara mengukur. Perbaikannya
menuntut keputusan pemilik (mekanisme split beku + daftar pair yang tak bisa diubah) —
persis prioritas P1 di roadmap TPM. Sampai itu ada, **jangan pakai +228R sebagai bukti
bahwa strategi ini punya edge.** Sumber lengkap: `hasil/01-quant-dev/DELIVERABLE.md`.

### B. Roadmap lanjutan (TPM) — 5 prioritas

1. **P1** Mekanisme split beku + buka kunci learner (menutup bias di atas).
2. **P2** Fee + slippage **terukur saat order** (bukan diasumsikan).
3. **P3** Dana terverifikasi + batas pilot diuji ulang (syarat keras terakhir sebelum GO).
4. **P4** Cutover merge F3 ke produksi dalam jendela terencana.
5. **P5** Retensi + partisi `facts` + hygiene keamanan tertunda (tunnel publik tanpa auth).

Detail + definisi "selesai" yang bisa diuji: `hasil/11-tpm/DELIVERABLE.md`.

### C. Catatan cakupan

Beberapa temuan agen lain belum diverifikasi ulang oleh orkestrator (status di
`~/.hermes/cache/scratch/team/INDEX.md`). Yang **sudah** diverifikasi langsung: #1
(`llm.json` tanpa `pricing`), #2 (`autonomy.py:284`), #3 (traceback repro), #4, #5
(struktur), #6/#7 (jalur kode). Yang belum: usulan frontend yang lebih luas, saran SRE
lain (journald rate-limit, rotasi), dan detail roadmap TPM per-item.
