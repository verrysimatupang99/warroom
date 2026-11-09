# Menyambungkan EA box-2aacb3 ke War Room — status 9 Nov 2026

## Temuan dasar

`GOLD_Reaper_Hexa` (EA yang jalan di box-2aacb3, akun REAL `452009427`) **tidak punya
`WebRequest` sama sekali** — murni indikator lokal (EMA 20/50/200 + VWAP + RSI).
Jadi ia tidak pernah, dan tidak bisa, melapor ke War Room tanpa perubahan kode.

Yang punya jalur War Room adalah EA lain: `WarRoom_AutoTrader` (v2.00) yang jalan di
Azure `mt5-trader-vm` — dan VM itu sudah mati sejak 31 Okt (subscription disabled).

## Yang sudah dikerjakan (siap, belum aktif)

1. `MQL5/Include/WarRoomTelemetry.mqh` di box-2aacb3 — modul pelapor telemetri,
   **read-only** (tidak pernah membuka/menutup posisi).
2. `GOLD_Reaper_Hexa.mq5` dipatch 4 titik: `#include`, `WarRoomInit()` di OnInit,
   `WarRoomDeinit()` di OnDeinit, `OnTimer()` pemanggil `WarRoomPush()`.
3. Build dengan telemetri tersimpan sebagai
   `GOLD_Reaper_Hexa.ex5.with-telemetry-20261109` (85.922 byte).
   Backup asli: `GOLD_Reaper_Hexa.ex5.bak-20261109` (69.416 byte).
4. Token dibaca dari `MQL5/Files/warroom_token.txt` (mode 600), bukan ditanam di sumber.
5. `config/common.ini`: `[Experts] WebRequest=1`, `WebRequestUrl=https://polywarroom.vps.webdock.cloud`
6. Kontrak payload mengikuti `MT5TelemetryPayload` (`warroom_api/routers/tencent.py:316`):
   wajib `account, broker, balance, equity, margin, free_margin, floating_pnl`;
   opsional `positions[], bid, ask, spread_pts, digits, server_time`.

## Blocker: MT5 menolak WebRequest dengan error 4014

Diuji langsung di box: modul aktif, timer jalan tiap 5 detik, tetapi setiap kiriman
gagal `err=4014` (`ERR_FUNCTION_NOT_ALLOWED`) dan **tidak ada satu pun request yang
sampai ke nginx Webdock** (`grep -c "mt5/telemetry" /var/log/nginx/access.log` = 0).

Yang sudah dicoba dan tidak menyelesaikan:
- edit `common.ini` `[Experts] WebRequest=1` + `WebRequestUrl` (satu URL, lalu dua URL
  termasuk path penuh) — nilai bertahan setelah restart, tetap 4014
- menyederhanakan header jadi satu literal (curiga format header) — tetap 4014
- restart terminal penuh (3x) dengan allowlist sudah terpasang — tetap 4014

Kesimpulan: MT5 build 6286 tidak menghormati allowlist dari `common.ini`; izin
WebRequest harus dikonfirmasi lewat **GUI**: Tools → Options → Expert Advisors →
centang "Allow WebRequest for listed URL" → tambahkan
`https://polywarroom.vps.webdock.cloud`.

## Kondisi akhir sesi ini (dipulihkan)

- EA di box-2aacb3 **dikembalikan ke build asli** (md5 identik dengan backup
  `67fb7c50…`), karena akun ini REAL dan telemetri belum bisa jalan.
- Terminal MT5 jalan: `authorized on Exness-MT5Real48`, `trading has been enabled`,
  `expert GOLD_Reaper_Hexa (XAUUSDc,M5) loaded successfully`, 0 positions.
- Tidak ada perubahan pada logika trading EA.

## Langkah berikutnya (urutan)

1. Buka desktop box-2aacb3 (tab Computer / VNC), jalankan MT5 GUI.
2. Tools → Options → Expert Advisors → centang Allow WebRequest, tambahkan
   `https://polywarroom.vps.webdock.cloud`, OK.
3. Tukar biner:
   `cp GOLD_Reaper_Hexa.ex5.with-telemetry-20261109 GOLD_Reaper_Hexa.ex5`
4. Restart terminal di luar sesi trade (EA trading 15:00–15:59 WIB).
5. Verifikasi: `MQL5/Files/warroom_debug.txt` berisi `push: OK http=200`,
   lalu di Webdock: `GET /api/v1/tencent/mt5/status` → `connected: true`,
   `account: 452009427`.

## Catatan lain

MT5 di box ini juga menyalakan MCP internal di `127.0.0.1:22346`
(`Server: MetaTrader5-MCP`), dengan ApiKey di `config/assistant.ini`. Semua varian
auth (Bearer / X-API-Key / Api-Key) dijawab 401, jadi jalur sidecar lewat MCP
belum bisa dipakai.
