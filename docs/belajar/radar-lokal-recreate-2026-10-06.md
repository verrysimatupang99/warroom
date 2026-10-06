# Radar pindah lokal — Azure dilepas (6 Okt 2026)

Keputusan owner: **server Azure akan dimatikan**, jadi radar rantai tidak boleh lagi
bergantung pada SSH ke VM `20.212.52.5`. Arah owner: *"poin satu harusnya bukan memunculkan
basi, tapi recreate di lokal Webdock saja"* — jadi bukan sekadar badge "basi", melainkan
radar-nya sendiri dijalankan di host ini.

## 1. Apa yang dipindah

| | Sebelum | Sesudah |
|---|---|---|
| Mesin | VM Azure (`azureuser@20.212.52.5`), cron `*/30` menjalankan `run_radar.sh` | Host ini, job worker `radar-update` (30 mnt) |
| Cara ambil | SSH `stat` + `cat /opt/gmgn-radar/radar_state.json` (timeout 20 s) | `gmgn-cli market trending` + `gas-price` via `lt radar-update` |
| State | `state/radar_cache.json` (cache hasil SSH) | `state/radar_state.json` (**sumber kebenaran**, ditulis lokal) |
| Panel dashboard | `_radar_panel` SSH → cache → `n/a` | `_radar_panel` baca state lokal → `n/a` + alasan |
| Label | `sumber: "cache"` / `"live"` | `sumber: "lokal"` |

Algoritma radar **tidak diubah**: `chain_radar.py` dari `~/gmgn-scan` (identik byte-per-byte
dengan yang di VM — sha256 dibandingkan langsung) diport ke
`packages/live-trading/src/live_trading/collectors/radar.py`. Diuji ulang di Webdock:
5 chain, ~12 detik, `gmgn-cli` sudah ada di host (`/usr/bin/gmgn-cli`).

## 2. Yang berubah di kode

| Berkas | Perubahan |
|---|---|
| `collectors/radar.py` | **Baru** — port `chain_radar.py`: scan 5 chain, klasifikasi PRIME/OPEN/CLOSING/DRY/CLOSED, diff & alert, tulis state lokal. Aturan "gagal ≠ kosong": semua chain gagal → state lama tidak ditimpa |
| `cli.py` | Subperintah baru `lt radar-update [--chains] [--limit]` |
| `dashboard.py` | `_radar_panel` **tanpa SSH**: baca `radar_state.json`, umur dari `diambil_epoch` (bukan mtime — salinan/restore bisa memperbarui mtime tanpa data baru). Kartu: "Radar Rantai", badge segar/basi/n/a |
| `ops/watchdog.py` | `radar_azure` → `radar_lokal` (pantau `radar_state.json`, ambang 3600 s) |
| `services/worker/jobs.py` | Handler `radar-update` (job terpisah, timeout 900 s — gmgn-cli bisa menunggu rate-limit) |
| `services/worker/schedule.py` | `JobSpec radar-update` interval 1800 s |
| `adapters/gmgn.py` | `RADAR_CACHE` → `RADAR_STATE`; `sumber: "lokal"`, bawa `diambil_epoch` |
| `apps/web/src/lib/nav.ts` | Catatan sub Radar: "lokal Webdock" |

## 3. Bukti (semua dijalankan)

```
$ lt radar-update --chains robinhood,arc,hyperevm,stable,base --limit 60
  radar lokal: 5 chain → /home/admin/live-trading/state/radar_state.json
    robinhood  window=CLOSED   age=  97 pools= 60 avg_vl= 6.943 hp=14
    arc        window=OPEN     age=  20 pools= 60 avg_vl= 1.564 hp=0
    hyperevm   window=CLOSED   age= 595 pools= 22 avg_vl= 0.361 hp=0
    stable     window=CLOSED   age= 302 pools=  2 avg_vl=   0.0 hp=0
    base       window=CLOSED   age= 1154 pools= 60 avg_vl= 4.106 hp=0

$ systemctl ... journalctl -u warroom-worker | grep radar
  {"job": "radar-update", "status": "ok", ...}
  {"job": "gmgn-sync", "status": "ok", "detail": "gmgn=ok berkas=24 radar=ok sumber=lokal"}

$ GET /api/v1/areas/gmgn  (sesi)
  radar fact: segar | age_s: 421.8 | sumber: "lokal"
  chains: robinhood/CLOSED, arc/OPEN, hyperevm/CLOSED, stable/CLOSED, base/CLOSED
```

- `pytest services packages` → **hijau** (termasuk `test_radar.py` baru: klasifikasi window,
  gerbang keamanan, fallback volume, "gagal ≠ kosong", diff/alert).
- `ruff check .` → bersih · `vitest` 35 lulus · `svelte-check` 0 error · `deploy-web.sh` health gate lolos.

## 4. Yang TIDAK dilakukan (disengaja)

- **Tidak** menampilkan "basi" sebagai solusi — atas arahan owner. Badge basi hanya muncul
  kalau radar lokal memang tidak jalan > ambang; itu pengawasan, bukan pengganti.
- **Tidak** menyentuh VM Azure (masih hidup; cron `*/30` di sana masih berjalan sampai
  owner mematikannya). Kami juga tidak menghapus kunci SSH dari host ini — itu keputusan
  owner saat shutdown.
- **Tidak** memakai MCP/kuota Arjum: radar ini murni `gmgn-cli`, tanpa dampak kuota.

## 5. Saat Azure dimatikan (checklist owner)

1. Tidak ada aksi darurat: radar, worker, API, web tetap jalan tanpa VM itu.
2. Setelah shutdown, hapus kunci/known_hosts Azure dari host ini (key lama masih bisa
   masuk ke VM selama VM hidup — risiko yang sebaiknya ditutup saat mematikan).
3. Arsipkan `~/gmgn-scan/deploy_radar.py` (alat push ke Azure, tidak dipakai lagi).

## 6. Sisa yang belum dipindah (tencent-like)

Radar rantai hanya salah satu beban yang dulu dioperasikan dari host lain. Yang **belum**
dipindah dan masih bergantung pada VM/lingkungan luar — perlu keputusan owner berikutnya:

| Sumber | Jejak |
|---|---|
| Kuota/penjadwal Hermes (22 job IDX di-pause) | `~/.hermes/cron/jobs.json` (Tencent) |
| Arsip tick Arjum 5 GB | `~/.hermes/cron/state/arjum_trades.db` (Tencent) — dipakai BSJP SMA10 lewat salinan/mirror |
| Arsip `polymarket-migration`, `projects`, `research` | Tencent `~/` |

Detail inventaris: `docs/belajar/inventaris-tencent-2026-10-06.md`.
