# Jam buka/tutup pasar XAUUSD (24 Okt 2026)

## Jawaban singkat
- **Sekarang tutup** (Sabtu 24 Okt).
- Buka kembali **Minggu 22:00 UTC = Senin 05:00 WIB**.
- Klaim awal saya "Senin 01:00 UTC" **kurang tepat**; secara UTC pembukaannya
  terjadi hari Minggu malam.

## Bukti bahwa sekarang tutup
```
bid 3996.057  (identik sejak Jumat ~21:00 UTC, ~18 jam tanpa tick)
spread 260 pts
```
Log EA 23 Okt: bid mulai beku 20:58, spread melebar 240 pts pada 21:02, lalu tetap
3996.057 sampai sekarang. Pola khas penutupan sesi mingguan.

## Jadwal umum spot gold
| Peristiwa | UTC | WIB |
|---|---|---|
| Tutup mingguan | Jumat 21:00 | Sabtu 04:00 |
| Buka mingguan | Minggu 22:00 | Senin 05:00 |
| Jeda harian | 21:00-22:00 | 04:00-05:00 |

Jam ini **bisa berbeda per broker** dan bergeser saat DST. Sumber paling pasti:
MT5 -> klik kanan XAUUSDm -> **Specification** -> **Sessions**.

## Deteksi empiris (dipasang)
Daripada mengandalkan jadwal teoretis, `ops/pantau-tick.py` (timer 5 menit)
mencatat peristiwa buka sebenarnya:

- baca `bid` dari telemetri EA
- bila berubah saat status TUTUP -> tulis ke `/var/lib/warroom/pasar_log.csv`
  (UTC + WIB + bid sebelum/sesudah)
- status awal TIDAK_DIKETAHUI ditetapkan dari pergerakan agar peristiwa BUKA
  pertama tidak terlewat

Kondisi awal terverifikasi: `status=TUTUP bid=3996.057 spread=260`.
Timer aktif, `Result=success`.

## Konsekuensi untuk rencana pengumpulan data
Jendela data verdict Laya yang bermakna mulai **Senin 05:00 WIB**, bukan Senin pagi
lebih awal. Sebelum itu Laya masih menilai harga beku.

## Catatan lain
Saat pasar tutup, ini juga teramati: EA sempat mengirim order dan ditolak broker
dengan `market closed` (saat verifikasi jalur relatif). Karena itu
`InpFailCooldownSec=120` penting - tanpa jeda, EA akan mencoba tiap 5 detik.
