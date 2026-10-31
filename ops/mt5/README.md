# Bridge telemetri MT5 (akun kedua / cent)

`WarRoom_TelemetryBridge.mq5` adalah EA **telemetri-saja**. Ia tidak membuka,
menutup, atau mengubah order. Fungsinya hanya mengirim tiga hal ke War Room:

1. `POST /api/v1/tencent/mt5/telemetry` — saldo, ekuitas, posisi, order pending,
   statistik hari ini, dan jam server tiap 5 detik.
2. `POST /api/v1/tencent/mt5/deal` — deal tertutup (`DEAL_ENTRY_OUT`) untuk jurnal.
3. Tidak ada endpoint lain; tidak ada perintah yang dieksekusi dari server.

## Kapan dipakai

- Akun Reaper (Exness demo `416510164`) memakai EA `WarRoom_AutoTrader_v3.1` yang sudah
  mengirim telemetri sendiri — **jangan** pasang bridge ini di akun itu.
- Akun cent HSFX (`HSFX OnePiece`) hanya untuk uji saldo kecil. Pasang bridge di chart
  akun itu. Ini bukan EA trading; posisi dibuka manual atau oleh EA lain.

## Pemasangan

1. Salin `WarRoom_TelemetryBridge.mq5` ke `MQL5/Experts/` terminal akun tujuan,
   lalu compile di MetaEditor (F7).
2. Terminal → **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**:
   `https://0xgunsl1ng3r.xyz`
3. Tempel EA di satu chart (mis. XAUUSDm M5), isi:
   - `InpApiBase = https://0xgunsl1ng3r.xyz`
   - `InpToken` = token EA (`WARROOM_EA_SYNC_TOKEN` di `/etc/warroom/*.env`, 600).
     Jangan simpan token di repo, chat, atau screenshot.
   - `InpStrategyVersion = hsfx-onepiece`
   - `InpNormalizeCent = true` untuk akun `USC`/`EUC` (nilai uang dibagi 100 agar
     dashboard menampilkan USD, bukan sen).
4. Aktifkan AutoTrading. Log Expert harus menunjukkan tidak ada `HTTP 401`.

## Verifikasi

```bash
# daftar akun (butuh cookie sesi operator)
curl -sS -b /tmp/wr.cookie https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/accounts | jq

# status akun kedua
curl -sS -b /tmp/wr.cookie \
  'https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/status?account=<nomor>' | jq \
  '{account,currency,cent_factor,balance,equity,positions,seconds_ago}'

# kurva ekuitas akun itu (503 berarti belum ada riwayat, bukan nol)
curl -sS -b /tmp/wr.cookie \
  'https://0xgunsl1ng3r.xyz/api/v1/journal/performance?market=forex&account=<nomor>' | jq
```

UI: `/forex?sub=ringkas` → panel **Akun MT5**. Kartu akun menampilkan balance,
equity, floating, posisi, umur telemetri; klik akun untuk detail posisi, kurva, dan
deal tertutupnya.

## Batas jujur

- Bridge ini **belum dikompilasi/diuji di terminal MT5** pada sesi 31 Okt 2026.
  Yang sudah diuji: endpoint API multi-akun (tes + live), pemisahan fakta
  `ringkas:<account>`, panel UI, dan build web.
- Sumber kebenaran tetap statement broker. `deals.csv` adalah laporan EA; selisih
  wajib direkonsiliasi dengan `tools/rekonsiliasi_forwardtest.py`.
- `open_time`/`open_price` pada deal penutup tidak tersedia dari MT5 tanpa lookup
  posisi; bridge sengaja mengosongkannya daripada mengarang. `close_time`,
  `close_price`, dan `net` tetap diisi.
- Akun cent dinormalisasi di bridge. Bila EA lain mengirim saldo sen mentah, dashboard
  akan menampilkan angka 100×; kirim `cent_factor` dan nilai USD yang sudah dinormalisasi.
