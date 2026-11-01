# Runbook trading — batas risiko dan kill-switch

Ditulis 1 Nov 2026 dari aturan verbal owner yang sebelumnya hanya tersimpan di vault
laptop. Dokumen ini menjadikannya acuan yang bisa dibaca agen di Webdock.

## Ruang lingkup

- Akun live: `36525553` (Vantage Markets Live 21, Cent ECN), `BTCUSD.sc` H1.
- EA: `Fomofx_Satrion_BTC_v1.00`, preset `Satrion BTC Fix lot.set`.
- Host: `mt5-trader-vm2` (`FOREX-MT5-RG`, `20.212.109.170`).
- Larangan tetap: jangan restart/stop/mengubah konfigurasi VM, jangan menyentuh
  `terminal64.exe`, jangan memasang EA lain. Lihat `HOLD_DO_NOT_TOUCH_AZURE_VM.md`.

## Batas risiko

| Batas | Nilai | Dasar |
|---|---|---|
| Drawdown harian maksimum | **3%** dari ekuitas awal hari | aturan owner |
| Drawdown total maksimum | **5%** dari ekuitas puncak | aturan owner |
| Aksi saat batas tersentuh | hentikan EA, tanpa posisi baru | aturan owner |

Catatan yang belum terdokumentasi dan perlu keputusan owner:

- Jam reset "harian" mengikuti waktu broker atau WIB.
- Ukuran risiko per posisi pada akun cent ini.
- Apakah batas 3%/5% dihitung dari ekuitas atau saldo.

## Kriteria kill-switch

Hentikan EA dan eskalasi ke owner bila salah satu terjadi:

1. Drawdown harian menyentuh 3%.
2. Drawdown total menyentuh 5%.
3. Slippage lebih dari 50 poin berturut-turut.
4. Berita high-impact tak terduga (black swan) yang mengubah asumsi posisi.

Keputusan menghentikan EA adalah milik owner. Agen hanya boleh mendeteksi, mencatat,
dan mengirim alert. Agen tidak mengirim order, menutup posisi, atau menyentuh VM.

## Jalur bukti dan alert

- Alert Telegram: `/usr/local/sbin/warroom-alert-push.py` (symlink ke
  `tools/warroom-alert-push.py`), dedupe 6 jam, jendela baca 45 menit.
- Status layanan: `systemctl status warroom-api warroom-worker warroom-web`.
- Fakta War Room: `/api/v1/areas/crypto`, `/api/v1/freshness`, `/api/v1/cron/jobs`.
- Telemetri live belum terhubung. `/var/lib/warroom/fills.csv` masih header saja,
  dan `/api/v1/telemetry/push` belum ada di kode.

## Prosedur saat kill-switch

1. Catat waktu, ekuitas, posisi terbuka, dan pemicunya.
2. Kirim alert ke owner dengan bukti angka, bukan opini.
3. Owner menghentikan EA dari sisi yang diizinkan (bukan agen Webdock).
4. Setelah pasar tenang, tulis postmortem singkat di `docs/` dan tinjau batasnya.

## Tinjauan

Batas dan kriteria ditinjau setiap review bulanan arsitektur platform. Perubahan
hanya sah bila dicatat di dokumen ini dan disetujui owner.

## Riwayat

- 1 Nov 2026: dokumen dibuat dari aturan verbal owner; belum ada perubahan angka.
