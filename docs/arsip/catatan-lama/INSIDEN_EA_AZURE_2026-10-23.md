# Insiden 23 Okt 2026 — EA Azure, lock run-command, dan trade cacat

## Ringkasan
1. Lock `az vm run-command` (`Conflict`) terlepas dengan **restart VM**.
2. **EA di Azure ternyata versi lama** (20.573 B, tanpa `InpUseRiskSizing`).
   Versi benar sudah dikirim + **compile 0 errors, 0 warnings**.
3. **Restart VM mematikan MT5**, dan MT5 **tidak auto-start** karena tidak ada
   sesi user yang login. EA kini OFFLINE.
4. Analisa 6 trade: **satu trade cacat (R:R 1:0,03) menyebabkan seluruh kerugian.**

---

## 1. Lock run-command

Gejala: `ERROR: (Conflict) Run command extension execution is in progress`.
Bukti: activity log menunjukkan run-command menggantung sejak **13:06:08Z**.

Yang TIDAK berhasil:
- `az vm extension delete -n RunCommandWindows`
- `az vm extension list` (kosong, tak bisa dibatalkan dari CLI)

Yang BERHASIL:
```bash
az vm restart -g FOREX-MT5-RG -n mt5-trader-vm     # Succeeded
az vm run-command invoke ... --scripts "Write-Output 'ALIVE'"   # -> ALIVE
```

Prasyarat sebelum restart: dipastikan **0 posisi terbuka, 0 pending order**.

---

## 2. EA di Azure adalah versi lama

| | Server ini (`/srv/private`) | Di VM (sebelum) |
|---|---|---|
| Ukuran `.mq5` | 24.205 B | **20.573 B** |
| `InpUseRiskSizing` | 3 kemunculan | **0 (tidak ada)** |

Artinya pekerjaan `InpUseRiskSizing=false` **tidak pernah sampai ke VM**.

Cara pengiriman (tanpa SSH; port 22 tertutup):
- base64 file -> dipecah 5 bagian 7.000 B (`split -b 7000`)
- dikirim satu per satu via `az vm run-command invoke --scripts @file.ps1`
  (`Set-Content` / `Add-Content -NoNewline`)
- decode: `[IO.File]::WriteAllBytes(..., [Convert]::FromBase64String($raw))`

Verifikasi setelah decode: **size=24205, risksizing=3** (identik dengan lokal).

Compile:
```
MetaEditor64.exe /compile:"...\WarRoom_AutoTrader.mq5" /log
Result: 0 errors, 0 warnings, 1409 ms
```
`.ex5` baru: **52.570 B** (sebelumnya 49.870 B), timestamp 14:23.

Lokasi data MT5 (dicatat agar tidak dicari lagi):
```
C:\Users\traderadmin\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075
```
(`startup.ini` sudah benar: Login=416510164, Server=Exness-MT5Trial14,
Expert=WarRoom_AutoTrader, Symbol=XAUUSDm, Period=M5)

---

## 3. MASALAH BARU: MT5 mati setelah restart dan tidak auto-start

### Fakta
- Log terminal berakhir: `14:06:52 System terminal stopped due to system shutdown`
- `AutoAdminLogon` **tidak diset**, `query session` -> hanya `services` (session 0)
  dan `console` **Conn** tanpa user
- Tidak ada shortcut di folder Startup, tidak ada entry MT5 di Run key
- `Start-Process terminal64.exe` dari run-command berjalan (PID ada) tetapi
  **tidak login** — run-command berjalan di **session 0** (tanpa GUI), sehingga
  terminal MT5 tidak bisa menyelesaikan login dan EA tidak pernah attach
- Telemetri War Room: `connected:false`, heartbeat berhenti

### Mitigasi yang sudah dipasang
Shortcut autostart dibuat:
```
C:\Users\traderadmin\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MetaTrader5.lnk
-> C:\Program Files\MetaTrader 5\terminal64.exe
```

### YANG HARUS DILAKUKAN OWNER (tidak bisa dikerjakan dari CLI)
MT5 butuh **sesi desktop interaktif**. Pilih salah satu:

1. **RDP ke VM** (138.91.35.65, user `traderadmin`), login, lalu:
   - jalankan MT5, pastikan login akun 416510164 / Exness-MT5Trial14
   - pastikan EA `WarRoom_AutoTrader` ter-attach di XAUUSDm M5 dengan AutoTrading ON
   - setelah itu menutup RDP **jangan log off** (disconnect saja) agar sesi hidup
2. **Aktifkan AutoAdminLogon** (butuh password, sengaja TIDAK disimpan/diketik
   oleh agen). Setelah itu VM akan login otomatis dan shortcut Startup bekerja.
3. Pertimbangkan **scheduled task "At startup"** yang menjalankan MT5 di sesi
   user — hanya efektif bila ada sesi user.

**PENTING**: selama EA offline, tidak ada proteksi trailing/BE/daily-ratchet yang
berjalan. Jangan biarkan posisi terbuka tanpa pengawasan.

---

## 4. Analisa 6 trade — akar kerugian

Data: `/api/v1/tencent/mt5/history` (akun 416510164, XAUUSDm, volume **0,05**)

| # | Arah | Risk | Reward | R:R | Tercapai | PnL |
|---|---|---|---|---|---|---|
| 1 | BUY | 6,50 | 7,50 | 1:1,15 | 49% | **+18,50** |
| 2 | SELL | 5,20 | 7,80 | 1:1,50 | 56% | **+22,00** |
| 3 | BUY | 6,10 | 7,90 | 1:1,30 | 44% | **+17,50** |
| 4 | BUY | 6,20 | 5,80 | 1:0,94 | 50% | **+14,50** |
| 5 | SELL | 4,80 | 7,40 | 1:1,54 | 65% | −24,00 |
| 6 | BUY | **9,17** | **0,23** | **1:0,03** | — | **−91,52** |

```
4 win  : +72,50
2 loss : -115,52     <- $91,52 dari trade #6 saja
net    : -43,02

Tanpa trade #6: +48,50 (PROFIT)
```

### Kesimpulan
- **Rasio exit strategi sehat**: 4 trade menangkap 44–56% jarak TP; partial TP
  (+1.0R) dan trailing bekerja sesuai desain. Hipotesis "TP terlalu dekat" SALAH.
- **Trade #6 adalah anomali**: TP hanya **2,3 poin** dari entry sementara SL
  **91,7 poin**. Untuk peluang menang $0,23, risiko $9,17.
  Ditutup oleh `Daily Max Loss Cut` -> −$91,52 = **18,3% akun** dalam satu trade.
- SL trade #6 = `close_price` (4122.98), 9,17 di bawah entry — jauh lebih lebar
  dari trade lain (4,8–6,5). Indikasi **SL dimundurkan setelah entry** atau
  **TP dihitung dari harga yang sudah bergerak**, bukan dari entry aktual.

### Yang perlu diperbaiki di EA (belum dikerjakan)
- Tolak order bila `reward/risk` di bawah ambang minimum (mis. < 0,8).
- Hitung TP dari **harga entry aktual** (fill price), bukan harga sinyal.
- Validasi ulang SL/TP setelah entry; jangan biarkan SL melebar melebihi rencana.
- Pertimbangkan menolak entry bila jarak SL > N x ATR pada saat itu.

---

## 5. Status akhir

| Cek | Hasil |
|---|---|
| warroom-api/worker/web/nginx | **active** |
| API & publik | **200 / 200** |
| Swap | **0 MB** (OpenClaw sudah di-stop+disable) |
| VM Azure | **running** |
| run-command | **berfungsi** |
| EA `.mq5`/`.ex5` di VM | **versi baru, compile bersih** |
| **EA telemetri** | **OFFLINE** — butuh login sesi desktop |
