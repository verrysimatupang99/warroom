# Snapshot broker di telemetri + hasil ukur ATR (24 Okt 2026)

## Yang dikerjakan
Opsi A langkah 1 dari riset: EA kini mengirim snapshot BROKER di setiap telemetri,
dan API menyimpannya. Belum ada keputusan yang memakai nilai baru ini.

## Field baru di telemetri (terverifikasi live)

| Field | Nilai |
|---|---|
| `bid` | 3996,057 |
| `ask` | 3996,317 |
| `spread_pts` | 260 |
| `digits` | 3 |
| `atr_m5` | **2,452** |
| `ema9_m5` | 3996,104 |
| `ema21_m5` | 3996,771 |
| `high_12` | 3999,978 |
| `low_12` | 3992,074 |

Handle `iATR`/`iMA` M5 dibuat sekali di `OnInit` dan dilepas di `OnDeinit`.

## Hasil ukur: ATR broker vs futures

| Sumber | ATR14 |
|---|---|
| Broker (XAUUSDm M5) | **2,452** |
| Yahoo `GC=F` (futures) | **2,371** |
| Selisih | **3,4%** |

Menurut aturan keputusan pada riset (<10% -> prioritas turun), ATR dari `GC=F`
**masih layak** dipakai untuk menghitung jarak SL. Tidak perlu ganti sumber ATR.

Catatan kejujuran: pengukuran ini dilakukan saat **pasar tutup**, sehingga kedua
ATR dihitung dari data yang sebagian beku. Angka 3,4% cukup untuk menyimpulkan
"tidak ada perbedaan drastis", tetapi pengukuran ulang saat pasar buka tetap
disarankan sebelum menutup topik ini.

## Dua cacat yang ditemukan sambil mengerjakan ini

### 1. Angka hardcode di payload telemetri (dihapus)
Payload lama berisi literal:
```
"total_trades_today":6,"win_rate_pct":66.7
```
Tidak pernah dihitung, tetapi tampil sebagai data di `/mt5/status`. Diganti
`HitungStatistikHariIni()` yang membaca `HistoryDealsTotal` / `HistoryDealGetDouble`
(profit + swap + commission, hanya `DEAL_ENTRY_OUT` untuk simbol ini).

### 2. Tabrakan nama field (diperbaiki)
`/mt5/status` melakukan `data.update(_statistik_forex(...))`, sehingga
`wins`/`losses` dari telemetri tertimpa statistik jurnal all-time. Hasilnya status
menampilkan `wins=4` di samping `total_trades_today=0` - dua jendela waktu berbeda
memakai nama sama.

Field hari-ini sekarang dinamai berbeda:
`wins_today`, `losses_today`, `win_rate_today_pct`, `net_pnl_today_usd`.
Statistik jurnal all-time tetap memakai nama lama.

Status setelah perbaikan:
```
hari_ini : trades 0  wins_today 0  net_today 0.0
jurnal   : wins 4  losses 2
```
Konsisten dan tidak lagi menyesatkan.

## Cacat ketiga: EA aktif tidak ter-versioning (diperbaiki)
```
/srv/private/WarRoom_AutoTrader.mq5     36.337 B  (aktif, TIDAK dilacak git)
apps/web/static/WarRoom_AutoTrader.mq5  20.573 B  (dilacak, BASI)
```
Sumber yang disajikan `/mt5/source.raw` adalah berkas di `/srv/private` yang tidak
masuk repo, sehingga kesalahan edit tidak bisa dipulihkan. Salinan repo sudah
disinkronkan (md5 sama) dan di-commit.

## Verifikasi
| Cek | Hasil |
|---|---|
| compile EA | **0 errors, 0 warnings**, `.ex5` 60.958 B |
| EA reload | MT5 id=6140 session 2, telemetri heartbeat 1 detik |
| field baru tersimpan | semua tampil di `/mt5/status` |
| pytest API | 58 lulus |
| ruff | bersih |
| commit | `0972f4a` (snapshot), `ec4a1dd` (pisah statistik), `4d0c26a` (sinkron EA) |
| deploy | `ec4a1dd-20261024T085930Z` |

## Catatan tambahan
`POST /mt5/telemetry` mengembalikan `exec_powershell` berisi perintah yang menulis
ulang `.mq5` di seluruh `C:\` lalu mengompilasinya. EA **tidak** mengeksekusinya
(tidak ada `shell32`/`ShellExecute` di sumber), jadi saat ini mati. Berisiko bila
kelak ada komponen yang menjalankannya tanpa verifikasi hash.

## Sisa pekerjaan
1. Ukur ulang ATR saat pasar buka untuk menutup topik sumber ATR.
2. Keputusan ambang Laya (0,60 vs verdict ~0,14) setelah pasar buka.
3. Pertimbangkan memakai `atr_m5`/`ema*_m5` broker sebagai sumber indikator,
   menggantikan `GC=F` sepenuhnya (data sudah tersedia, tinggal dipakai).
4. Verifikasi live jalur EA relatif ("Level relatif dihitung dari broker") -
   belum muncul karena belum ada sinyal OK dari produksi.
