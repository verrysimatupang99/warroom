# Subproject: MTRB Pro (EA demo)

EA MTRB Pro dari repo `Darkwinter777/mtrb-pro` (private), dijalankan di **akun demo**
`464202979` @ `Exness-MT5Trial17`. Dashboard-nya ada di `/mtrb/` (PIN `7721`).

## Di mana apa

| Hal | Lokasi (webdock) |
|---|---|
| Clone repo (source of truth) | `/home/admin/warroom/subprojects/mtrb-pro` |
| Terminal MT5 demo | `/home/admin/.wine-exness/drive_c/Program Files/MT5-EX-Demo` |
| EA + include | `.../MT5-EX-Demo/MQL5/Experts/` |
| Preset | `.../MT5-EX-Demo/MQL5/Presets/mtrb_demo.set` |
| Status JSON (dibaca dashboard) | `.../AppData/Roaming/MetaQuotes/Terminal/Common/Files/MTRB_Pro_status.json` |
| Backup ex5 | `/home/admin/backup-mtrb/` |
| Service | `mt5-ex-demo` (tmux `mt5demo`) |

## Deploy

```bash
sudo bash /home/admin/warroom/subprojects/mtrb-pro/deploy-ea.sh
# compile saja (tanpa restart):
sudo bash .../deploy-ea.sh --dry-run
```

Script melakukan, berurutan:
1. Ambil `MTRB_Pro.mq5` dari checkout repo.
2. Bikin `MTRB_Fix.mq5` = `MTRB_Pro.mq5` + `DashTick()` tiap 2 detik di `OnTick`.
   **Ini wajib**: `OnTimer` tidak andal di Wine, tanpa patch ini dashboard basi.
3. Copy include `MTRB_SMC.mqh` + `MTRB_SMC_Core.mqh` (v3.08+ butuh keduanya).
4. Compile headless `MetaEditor64.exe /compile:` **sebagai admin** (root → Wine menolak,
   MetaEditor tidak pernah terbuka).
5. Backup ex5, `systemctl restart mt5-ex-demo`, tunggu `v` di status JSON naik.

Gagal compile = tidak ada restart (aman). Rollback manual: copy ex5 dari `/home/admin/backup-mtrb/`
ke `MQL5/Experts/` lalu restart.

## Yang perlu diketahui

- **Init v3.08 makan ~6 menit** (SMC menyiapkan handle M15/M5). v3.07 hanya 1–2 menit.
  Dashboard kosong di 5 menit pertama itu normal — jangan restart, clock-nya mulai dari nol.
- **Mesin SMC JANGAN diaktifkan.** Dokumen repo (`docs/SMC_Gold.md` bagian 9) menyebut
  simulasi 30 hari dengan setelan bawaan **rugi** (49 sinyal, ~1,6/hari). Deteksinya bisa
  diaudit, profitabilitasnya belum terbukti. `InpEnableSMC=false` adalah setelan yang benar.
- Patch `DashTick` disuntik oleh script, jadi **jangan commit `MTRB_Fix.mq5`** ke repo.
- Akun **live terpisah** (Gold Reaper HEXA di `MT5-EX-Live`); telemetrinya lewat
  `/usr/local/bin/wr-bridge.sh` (systemd timer 10 detik), bukan WebRequest MT5 —
  allowlist WebRequest tidak bisa diisi lewat GUI di Wine.
