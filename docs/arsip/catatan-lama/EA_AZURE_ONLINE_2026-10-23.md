# EA Azure kembali online — akar masalah sebenarnya (23 Okt 2026)

## Hasil akhir
```
EA connected : True
heartbeat    : 0-4 detik
balance      : $456.98
posisi       : 0
```

## Rangkaian temuan (berurut)

### 1. Anda benar: sesi traderadmin memang ada
`query session` menunjukkan:
```
traderadmin   2   Disc     <- sesi RDP Anda, tetap hidup walau disconnect
```
Jadi tidak perlu "login RDP sekali" seperti yang saya sarankan sebelumnya —
sesinya sudah ada.

### 2. Tapi MT5 tidak jalan, karena task tidak punya trigger
```
Task   : LaunchMT5GUI
User   : traderadmin  (LogonType: Interactive)
Action : terminal64.exe /config:"...\traderadmin\...\config\startup.ini"
Trigger: 0            <- tidak ada pemicu otomatis
LastRun: 22/10/2026 05:20:20
```
Task ini hanya jalan bila dipicu manual. Setelah reboot VM, tidak ada yang
memicunya -> MT5 mati sejak 14:06 hari ini.

Perbaikan: `schtasks /run /tn LaunchMT5GUI` -> MT5 hidup di session 2
(`id=1656 session=2`).

### 3. MT5 berhasil login ke Exness
```
'416510164': authorized on Exness-MT5Trial14 through Access Point #1 (ping 2.25 ms)
'416510164': terminal synchronized: 0 positions, 0 orders, 355 symbols
'416510164': trading has been enabled, demo account - hedging mode
```
Jadi kekhawatiran "akun belum login" TIDAK benar — login berjalan otomatis
dari kredensial tersimpan.

### 4. BUG UTAMA: EA tidak pernah attach karena `startup.ini` salah

Ternyata `startup.ini` punya DUA kesalahan:

| Salah | Benar | Akibat |
|---|---|---|
| `[Start]` | `[StartUp]` | MT5 tidak membaca section -> EA tidak di-load |
| `Expert=Experts\WarRoom_AutoTrader` | `Expert=WarRoom_AutoTrader` | MT5 menambah `Experts\` sendiri -> jadi `Experts\Experts\...` |

Bukti dari log MT5:
```
MQL5 | expert 'Experts\Experts\WarRoom_AutoTrader' not found from start config
```

Setelah kedua bug diperbaiki:
```
MQL5 | expert WarRoom_AutoTrader (XAUUSDm,M5) loaded successfully
```

**Penting:** EA terakhir menulis log 21 Okt 14:09 — artinya EA memang TIDAK
pernah jalan lagi setelah itu, walau MT5 hidup. Semua trade 21 Okt berasal dari
sesi yang masih berjalan saat itu.

### 5. Trigger ditambahkan agar tidak terulang
```
LaunchMT5GUI -> MSFT_TaskLogonTrigger, delay=PT30S, user=traderadmin (Interactive)
```
Sekarang setiap `traderadmin` login, MT5 otomatis menyala 30 detik kemudian.

## Yang dibatalkan (pekerjaan salah saya)
Sempat menyalin EA ke folder profil SYSTEM
(`C:\Windows\system32\config\systemprofile\...`) karena salah membaca log.
Sudah DIHAPUS semua:
- `MQL5\Experts\WarRoom_AutoTrader.{mq5,ex5,log}`, `ea.b64`
- `config\startup.ini` di folder SYSTEM
- shortcut Startup di profil traderadmin
- proses MT5 di session 0

Folder yang BENAR adalah profil `traderadmin`:
`C:\Users\traderadmin\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075`

## Kondisi EA sekarang
```
WarRoom_AutoTrader.mq5   24.205 B   (InpUseRiskSizing = false)
WarRoom_AutoTrader.ex5   52.570 B   compile 0 errors, 0 warnings
startup.ini              [StartUp] Expert=WarRoom_AutoTrader, XAUUSDm, M5
```

## BELUM dikerjakan (tetap berisiko)
1. **R1** — EA tidak validasi R:R setelah memakai `ask` (penyebab loss $91.52)
2. **R2** — tidak ada penolakan sinyal basi (tidak ada `generated_at`)
3. **R3** — Laya fail-OPEN (`return True, 0.85` saat model mati)
4. **Lot** — EA sekarang `InpFixedLot = 0.10`, sedangkan 6 trade kemarin 0.05
   -> risiko per trade BERLIPAT DUA selama R1 belum diperbaiki.
