# Rekomendasi: Posisi Laya AI & Perbaikan Forex
Tanggal: 23 Okt 2026 — **belum ada perubahan sistem** (murni rekomendasi)

---

## A. Posisi Laya AI sekarang (dari kode, bukan asumsi)

```
MT5 EA --GET /forex/levels--> generate_forex_levels()
                                  |
                                  |- fetch_klines_direct (M5)
                                  |- calculate_indicators (ema9/21, atr14)
                                  |- aturan EMA + sesi -> tentukan LONG/SHORT  <-- arah ditentukan di sini
                                  |- evaluate_laya(market_state)               <-- LAYA DI SINI
                                  |     |- SKIP    -> return None (batal)
                                  |     |- EXECUTE -> lanjut
                                  |- sl = entry - risk  (risk <= 3.0)
                                  |- tp1 = entry + risk * 1.8
MT5 EA <-- levels{entry,sl,tp1} --+
     |- trade.Buy(ask, sl, tp1)     <-- pakai ASK, bukan entry dari API
```

### Empat temuan penting

**1. Laya bukan pengambil keputusan — hanya pintu veto.**
Arah LONG/SHORT ditentukan aturan EMA + sesi. Laya hanya boleh/tidak boleh lewat.

**2. Laya tidak melihat akun sama sekali.**
`market_state` = `{symbol, side, session, price, atr, setup}`.
Tidak ada balance, equity, posisi terbuka, floating PnL.

**3. Laya FAIL-OPEN (paling berbahaya).**
```python
if not self.enable_laya or not self._laya_loaded or self._evaluator is None:
    return True, 0.85, "Laya AI Passthrough (Offline/Bypass)"
```
Model mati -> SEMUA sinyal lolos dengan confidence 0.85 palsu.
Verdict tak dikenali -> `return True, 0.0` -> tetap lolos.
Artinya proteksi Laya bisa saja tidak pernah aktif tanpa ada yang tahu.

**4. Laya dimuat di dalam proses API, di jalur panas.**
Ini menjelaskan `/forex/levels` butuh 18,3 detik. Model 421M (~1,1 GB) masuk ke
proses yang melayani dashboard + EA sekaligus -> API bisa membeku.
Saklar `WARROOM_LAYA_ENABLE` yang ada HANYA menjaga endpoint baru `/forex/laya`;
jalur produksi `/forex/levels` masih memuat Laya in-process.

---

## B. Opsi arsitektur Laya

### Opsi A — Laya sebagai gate async  (REKOMENDASI)
Timer 5-15 menit menjalankan `laya_cli.py` di proses terpisah + cgroup ~2 GB,
menilai kondisi pasar + akun, menyimpan verdict ke state.
`/forex/levels` hanya membaca verdict terakhir (instan, tanpa model).
- (+) Tidak bisa membekukan API (terbukti: subprocess + timer)
- (+) Bisa melihat akun karena telemetri tersedia
- (+) Verdict punya jejak waktu, bisa diaudit
- (-) Verdict bisa basi <=15 menit

Mitigasi basi: simpan `umur_detik`; bila terlalu tua -> dianggap TIDAK TERSEDIA,
dan karena R3 (fail-closed) berarti TIDAK ADA TRADE (bukan lolos).

### Opsi B — Laya sebagai reviewer, bukan gate
Keluar dari jalur eksekusi. Dipakai untuk review harian, deteksi regime, laporan pra-sesi.
- (+) Nol risiko ke API, nol risiko memblokir trade
- (-) Tidak menyaring real-time

### Opsi C — tetap gate in-process + cgroup
Paling murah, tapi tetap menaruh beban 1 GB di mesin yang RAM-nya dipakai
OpenClaw, MariaDB, Hermes. TIDAK disarankan.

**Rekomendasi: A + B sekaligus.**
A untuk penyaringan (async, terjadwal), B untuk pembelajaran.

---

## C. Perbaikan trading (urut dampak)

### R1 KRITIS — EA validasi R:R setelah pakai `ask`
Bukti trade #6:
```
API kirim: entry(price)=4126.98  sl=4122.98  tp1=4132.38
EA pakai : ask = 4132.146          (harga sudah melesat 5.2 poin)
EA cek   : ask >= tp1 ? False -> lolos
           ask <= sl  ? False -> lolos
Tidak dicek:
  risk   = 9.17 poin
  reward = 0.23 poin
  R:R    = 1 : 0.026     <- untuk menang $0.23, risiko $9.17
```
Perbaikan: hitung ulang risk/reward dari `ask`. Tolak bila
`reward < 0.8 * risk` ATAU `(ask - price_API) > 0.3 * reward`.

Drift nyata:
| # | risk API | risk aktual | drift | R:R aktual |
|---|---|---|---|---|
| 5 | 3.0 | 4.80 | +1.8 | 1:1.54 (masih ok) |
| 6 | 3.0 | 9.17 | +6.2 | 1:0.026 |

### R2 KRITIS — tolak sinyal basi
Simpan `generated_at` di respons API. EA tolak bila sinyal > ~60 detik.

### R3 KRITIS — Laya fail-CLOSED
`return True, 0.85` -> `return False, 0.0, "Laya tidak tersedia — trade diblokir"`.
Tanpa ini, nilai "middleware Laya" adalah ilusi.

### R4 PENTING — satu sumber kebenaran SL/TP
API menghitung dari `price` snapshot, EA eksekusi di `ask`. Pilih satu:
EA yang menghitung SL/TP dari fill aktual; API hanya kirim arah + ATR.

### R5 PENTING — beri Laya konteks akun
Tambahkan balance/equity/posisi terbuka/floating ke `market_state`.

### R6 SEDANG — log verdict Laya
Setiap verdict (EXECUTE/SKIP, p, alasan) dicatat dan bisa dilihat.

### R7 SEDANG — jadikan min R:R penjaga keras
`min_rrr=1.6` sudah ada di konstruktor registry tapi tidak dipakai untuk menolak
setelah drift.

---

## D. PERINGATAN sebelum EA dinyalakan

| | EA lama (yang trading) | EA baru (sudah di-compile) |
|---|---|---|
| Volume | **0.05** (6/6 trade) | `InpFixedLot = 0.10` |

Lot akan BERLIPAT DUA dari 0.05 -> 0.10 begitu EA baru jalan.
Bug R1 belum diperbaiki; loss $91.52 akan jadi ~$183 dengan lot 0.10.

**Saran:** perbaiki R1-R3 dulu, ATAU set `InpFixedLot=0.05` sementara.

---

## E. Urutan yang disarankan

| Prioritas | Langkah | Alasan |
|---|---|---|
| 1 | R1 + R2 di EA | Menghentikan pendarahan; tanpa ini lot 0.10 memperbesar kerugian |
| 2 | R3 fail-closed | Supaya "Laya" bukan sekadar label |
| 3 | Opsi A (Laya async terjadwal) | Hilangkan risiko API beku + beri Laya konteks akun |
| 4 | R4 sumber kebenaran SL/TP | Menutup celah drift dari akarnya |
| 5 | R6 log verdict | Supaya bisa diaudit |
| 6 | Opsi B (reviewer) | Nilai tambah, bukan penyelamat |

---

## F. Menunggu keputusan owner
1. Setujui R1+R2 (+R3) -> dikerjakan di EA, siap compile saat login
2. `InpFixedLot`: 0.05 sementara atau tetap 0.10
3. Arah arsitektur Laya: Opsi A, A+B, atau lain
4. EA masih OFFLINE — butuh login desktop di VM (RDP 138.91.35.65, user traderadmin)
