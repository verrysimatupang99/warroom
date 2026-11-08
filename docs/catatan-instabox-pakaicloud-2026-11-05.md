# Catatan Perubahan InstaBox & Pakaicloud — 5 Nov 2026

Oleh: CodeBuddy (agent Hermes) atas permintaan owner, sesi pengecekan
InstaBox pasca VM Azure `mt5-trader-vm2` mati (subscription disabled).

## 1. Kondisi ditemukan

- 5 mesin InstaBox, semua `state=running`:
  `testing`, `box-2aacb3`, `sshjump`, `mt5-paper-1`, `mt5-paper-2`.
- Semua mesin free plan: `autoSuspendAfterSeconds=1800` (30 mnt idle),
  `maxRunMinutes=480` (8 jam/run) — TETAP, tidak bisa diubah di free tier.
- Hermes gateway di `sshjump` sempat polling Telegram macet (hang ~3,5 jam,
  `stuck probe`); gateway di-restart 05 Nov 02:23 UTC → PID 35542, sehat.
  Catatan: gateway jalan via nohup, BUKAN systemd → tidak auto-start jika
  mesin restart.
- Azure `mt5-trader-vm2` (akun Vantage Cent live + EA orang): subscription
  `26bb0358-...` DISABLED → VM deallocated, tidak bisa dinyalakan via CLI.
  Owner putuskan: biarkan mati, cari pengganti.

## 2. Percobaan perubahan (SEMUA GAGAL — free plan)

Dijalankan dari Pakaicloud (`api-01`, CLI `/usr/local/bin/instabox` v0.8.147,
`INSTABOX_API_KEY` dari owner) terhadap KELIMA mesin:

- `instabox auto-suspend <mesin> 0`  → **spec_not_allowed**: free plan
  terkunci 1800 dtk; butuh Pro (300–1800 dtk atau 0).
- `instabox max-run <mesin> 0`       → **permission_denied**: free machines
  maxRunMinutes固定 480; hanya admin session yang bisa override.

TIDAK ada setting yang berubah di sisi InstaBox. Tidak ada mesin yang
di-stop/created/deleted. API key hanya dipakai read (get/usage) + 10 call
gagal di atas.

## 3. Implikasi & peringatan

- Karena auto-suspend 30 mnt & max-run 8 jam tidak bisa dimatikan di free
  tier: MT5/EA yang butuh jalan 24/7 **tidak cocok** di mesin InstaBox
  free ini. Proses bisa hilang tiap 8 jam atau saat 30 mnt idle.
- Solusi: upgrade workspace ke Pro (`instabox workspace subscribe
  <ws> --plan pro`) ATAU pindahkan MT5 ke VPS Windows biasa.

## 4. Perubahan di sisi Pakaicloud (api-01, 31.58.103.2:20271)

- TIDAK ada perubahan konfigurasi: tidak ada cron/unit/berkas baru.
- CLI `instabox` sudah ada sebelumnya (bukan instalasi baru; versi
  0.8.147, update-check ke 0.8.156).
- Berkas `/root/.config/instabox/update-check.json` hanya di-update oleh
  CLI sendiri saat dipanggil (bukan tindakan manual).
- API key TIDAK disimpan permanen di Pakaicloud — hanya dipakai lewat env
  `INSTABOX_API_KEY` per-sesi SSH pada perintah di atas.

## 5. Mesin lain yang dicek (read-only, tanpa perubahan)

- `warroom` server (Webdock): MT5 tidak terinstall; compose lama
  `ops/docker-mt5/` ada tapi container tidak jalan.
- `instabox-testing`: tidak ada MT5/proses hermes.
