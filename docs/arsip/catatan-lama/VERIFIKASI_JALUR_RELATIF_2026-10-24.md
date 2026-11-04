# Verifikasi jalur EA relatif — berhasil, dan menemukan 1 bug (24 Okt 2026)

## Tujuan
Membuktikan jalur R4 (engine kirim jarak -> EA susun level dari broker) benar-benar
bekerja di EA, bukan hanya di engine. Dilakukan saat **pasar tutup** supaya tidak
mungkin ada posisi terbuka.

## Cara uji (tanpa menyentuh cache produksi)
1. Berkas verdict UJI terpisah: `/var/lib/warroom/uji_verdict.json` berisi
   `EXECUTE 0.95` untuk LONG & SHORT, ditandai `"uji": true`.
2. API diarahkan ke berkas itu lewat drop-in systemd:
   `WARROOM_LAYA_VERDICT_PATH=/var/lib/warroom/uji_verdict.json`
   (catatan: `PrivateTmp=yes` membuat `/tmp` tidak terlihat oleh service, jadi
   berkas harus di `/var/lib/warroom`).
3. Amati log EA di VM.
4. Setelah selesai: drop-in dihapus, berkas uji dihapus, API restart.

Cache produksi (`laya_verdict.json`) **tidak pernah** ditimpa data uji.

## Hasil percobaan pertama: BUG

```
Level relatif dihitung dari broker: entry=3996.057 SL=3998.757 TP=3991.197
Sinyal SHORT DITOLAK (penjaga R:R): harga sudah bergerak 36% menuju TP (batas 30%)
```

### Penyebab
Pada mode RELATIF, SL/TP dibangun DARI harga fill. Maka:

```
risk / (risk + reward) = 1 / (1 + RR)
```

Untuk RR 1,8 -> **35,7%**, selalu di atas batas 30%. Pemeriksaan "drift" itu
dirancang untuk mode ABSOLUT (membandingkan harga snapshot API vs harga fill), dan
tidak bermakna pada mode relatif. Tanpa perbaikan, **semua** sinyal relatif akan
ditolak selamanya.

### Perbaikan
```cpp
bool ValidasiRRFill(..., const bool cekDrift = true)
```
Pemanggil mengirim `!modeRelatif`. Pemeriksaan **rasio** R:R tetap berlaku di kedua
mode.

## Hasil setelah perbaikan: LULUS

```
Level relatif dihitung dari broker: entry=3996.057 SL=3998.757 TP=3991.197 (risk=2.7 reward=4.86)
Sinyal War Room Diterima: SELL XAUUSDm Entry: 3996.057 SL: 3998.757 TP: 3991.197 | R:R pada fill = 1:1.80
CTrade::OrderSend: market sell 0.05 XAUUSDm sl: 3998.757 tp: 3991.197 [market closed]
Gagal Order SELL: market closed
```

Rantai penuh terbukti:
1. API kirim `side` + `risk`/`reward` + `generated_at`
2. EA menyusun level dari **harga broker** (3996.057 = bid, bukan 4008 futures)
3. Penjaga R:R lolos (1:1.80)
4. Order dikirim dengan lot **0.05** (sesuai keputusan owner)
5. Broker menolak karena **market closed** — sesuai harapan, tidak ada posisi

## Pembersihan (sudah dilakukan)
| Item | Status |
|---|---|
| drop-in `laya-test.conf` | dihapus |
| `/var/lib/warroom/uji_verdict.json` | dihapus |
| API | restart, kembali ke cache produksi |
| Verifikasi pasca-bersih | `Laya SKIP p=0.197 (ambang 0.60, umur 6s)` |

## Verifikasi
| Cek | Hasil |
|---|---|
| compile EA | **0 errors, 0 warnings**, `.ex5` 62.958 B |
| EA reload | MT5 id=2348 session 2 |
| jalur relatif | **terbukti** (log di atas) |
| commit / push | `5770e1d` / `976848f..5770e1d` |

## Sisa
1. **Ambang Laya** tetap menunggu data pasar buka. Sekarang terbukti bahwa
   penghalangnya adalah `choice = SKIP`, bukan sekadar confidence rendah —
   menurunkan ambang TIDAK bisa mengubah SKIP menjadi EXECUTE (memang by design).
2. Pantau sebaran verdict Senin lewat `ops/laporan-forex.py`.
3. `exec_powershell` pada respons telemetri masih ada (mati, tidak dieksekusi EA).
