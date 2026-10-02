# Baseline P0 — angka sebelum migrasi

Diukur: **2026-10-02** (WIB: 2026-10-03 dini hari) · Host: Webdock `polywarroom` · Fase: P0-T4
Semua angka di bawah berasal dari perintah yang tertulis; tidak ada yang dikira-kira.

## 1. Lingkungan

| Item | Nilai | Perintah |
|---|---|---|
| OS / kernel | Linux 6.8.0-139-generic (Ubuntu noble) | `uname -r` |
| CPU | 6 vCPU | `nproc` |
| RAM | 9.160 MB total · 6.078 MB available | `free -m` |
| Disk `/` | 38 GB, terpakai 28 GB (73%), sisa 11 GB | `df -h /` |
| Python | 3.12.3 | `python3 --version` |
| uv | 0.12.19 | `uv --version` |
| Node | v24.21.0 | `node --version` |
| npm | 11.19.0 | `npm --version` |
| Redis | 7.0.15 (terpasang) | `apt list --installed \| grep redis` |
| Postgres | **belum terpasang** | `apt list --installed \| grep postgresql` |
| Docker | terpasang (`/usr/bin/docker`), tanpa container jalan | `docker ps` |
| gh CLI | login sebagai `verrysimatupang99` | `gh auth status` |

## 2. Snapshot domain (`lt snapshot`)

| Metrik | Nilai | Perintah |
|---|---|---|
| Waktu bangun (dingin, terukur) | **35,97 s** | `/usr/bin/time -f "elapsed=%e s \| max RSS=%M KB" uv run lt snapshot` |
| Puncak memori | **71.528 KB (≈70 MB)** | idem |
| Waktu bangun (hangat, dari journal timer) | 16–18 s (01:18:26→01:18:42 WIB; 03:03:26→03:03:44 WIB) | `journalctl -u live-trading-snapshot.service` |
| Keluaran | `state/snapshot.json`, **87.889 byte** | `stat -c '%s %y' state/snapshot.json` |
| Jalur data | crypto, idx, forex, hyperliquid, idx_tv, dex, idx616 — semua `ok` | keluaran `lt snapshot` |

Implikasi untuk P1: job `snapshot` di worker butuh timeout ≥ 120 s (3× pengukuran dingin) dan
harus idempoten; 7 jalur berarti 7 fakta turunan minimum per snapshot.

## 3. State & backup

| Metrik | Nilai | Perintah |
|---|---|---|
| Ukuran state | **29.347.836 byte (≈28 MiB)**, 47 berkas | `du -sb state`, `find state -type f \| wc -l` |
| Arsip backup | 14 berkas, **51.858.738 byte (≈49 MiB)**, rotasi 14 | `du -sb backups`, `ls backups \| wc -l` |
| Irama backup | tiap 6 jam (`live-trading-backup.timer`) | `systemctl list-timers` |
| Ledger | 5 trade, +3.844R (**warisan**, bukan hasil sistem ini) | keluaran `lt snapshot` |

Implikasi untuk P1: uji restore (P0-T5) memakai arsip `state-*.tar.gz` yang sudah ada; tidak perlu
membuat mekanisme backup baru di P0.

## 4. Kuota Arjum (IDX)

| Metrik | Nilai | Perintah |
|---|---|---|
| Limit harian | 6.000 | `cat state/arjum_quota.json` |
| Terpakai hari ini | **6** (sisa 5.994) | idem |
| Pengaman minimum | 500 (`arjum_min_remaining`) | `src/live_trading/config.py:43` |

Implikasi untuk P1/P2: halaman IDX tidak boleh memicu panggilan Arjum per render; fakta dibaca
dari DB, pengambilan data tetap lewat worker berjadwal.

## 5. Jaring pengaman (jangan sampai rusak)

| Metrik | Nilai | Perintah |
|---|---|---|
| Tes domain | **219 lulus, 1,42 s** | `cd ~/live-trading && uv run pytest` |
| Lint domain | bersih | `cd ~/live-trading && uv run ruff check .` |

## 6. Unit & timer yang berjalan sekarang (Webdock)

| Unit | Irama | Fungsi |
|---|---|---|
| `live-trading-dashboard.service` | terus | dashboard lama `127.0.0.1:8799` (tetap hidup sampai parity UI P2 hijau) |
| `live-trading-snapshot.timer` | 15 mnt | bangun `state/snapshot.json` |
| `live-trading-collect.timer` | 30 mnt | `lt scan` — kumpulkan kandidat |
| `live-trading-watchdog.timer` | 30 mnt | cek kesegaran berkas |
| `live-trading-backup.timer` | 6 jam | arsip state lokal, rotasi 14 |
| `war-room-git-sync.timer` | 6 jam | sinkronisasi git |
| `war-room-backup.timer` | 6 jam | backup GMGN + live-trading |

Catatan P1-T4: timer `snapshot`/`collect` akan dipindahkan ke jadwal worker; `dashboard`
**tidak** dimatikan sampai dual-run P2-T8 hijau.

## 7. Catatan kejujuran

- Waktu snapshot dingin (35,97 s) jauh di atas waktu hangat dari journal (16–18 s) — kemungkinan
  cache DNS/koneksi dan cache proses. Untuk ukuran kapasitas, pakai **35,97 s** sebagai batas atas.
- `snapshot.json` diukur pada 20:19:17 UTC; angka Arjum pada hari yang sama. Keduanya bergerak
  tiap 15 menit — dokumen ini adalah potret, bukan nilai hidup.
- Postgres belum ada: P1-T1 mencakup pemasangan/pengadaan, itu memang di luar P0.