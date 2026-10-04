# Uji klaim short $VELVET — 4 Okt 2026

Sumber: postingan `@liabilitrees` di Threads — **permukaan publik saja**.
Label: **[verified]** = dicek langsung ke Binance futures & bertanggal.

## Klaim yang diuji

> Saya suka sekali short koin-koin yang sudah overextended… Pertama kali saya coba Short $VELVET
> langsung kena SL. Tapi apa saya menyerah? Tidak. Saya tunggu hingga derivative activitiesnya
> mulai mereda (OI, FR, CVD Spot). Hari Sabtu kemarin sekitar jam 7 pagi sudah mulai muncul
> tanda-tanda buyer exhaustion, saya CMP Short dan masih keep sampai sekarang.

Yang benar lebih dulu: **tradenya memang untung.** Itu tidak dibantah di sini.

---

## 1. Fakta pasar (VELVETUSDT, Binance futures, 168 jam)

| Ukuran | Nilai |
|---|---|
| Dasar (low) | 30/09 19:00 WIB @ 0,05522 |
| Puncak (high) | **03/10 07:00 WIB @ 0,09569** |
| Pump low → high | **+80,2%** |
| Harga sekarang | 0,07065 → **−26,5% dari puncak** |
| Puncak OI | **7,85 juta USD @ 03/10 07:00 WIB** |
| OI sekarang | 5,21 juta → **−33,6% dari puncak** |
| Funding maks | **+0,0381% per 8 jam** (median +0,0124%) |
| Funding "ramai"? | **TIDAK PERNAH** (ambang 0,05%) |

**"Overextended" itu benar** — naik 80% dalam ~2,5 hari. Sejauh ini klaimnya sah.

## 2. Tapi tiga sinyal yang dia sebut tidak mendukung masuknya

Dia bilang masuk saat *"derivatif mulai mereda (OI, FR, CVD)"*. Pada jam yang dia sebut
(03/10 07:00), data justru berkata sebaliknya:

| Sinyal yang dia sebut | Kenyataan pada 03/10 07:00 |
|---|---|
| OI mulai mereda | **OI di PUNCAK sepanjang window, dan +10,7% pada jam itu** — menguat, bukan mereda |
| FR (long crowded) | **Tidak pernah ramai sama sekali** — maks +0,0381%, ambang 0,05% |
| CVD / buyer exhaustion | tak tersedia di Binance dalam bentuk itu; taker B/S jam itu 0,89 (condong jual tipis) |
| Harga | **+6,34% pada jam itu**, dan harga buka jam itu hanya **−1,52% dari puncak sesi** |

👉 **Dia short tepat di tick teratas.** Titik itu nyata — tapi baru tampak sebagai puncak
**setelah** jam berikutnya runtuh −14,7%.

## 3. Uji yang menentukan: apakah polanya pernah membayar?

Menjalankan aturan yang **bisa dia amati saat itu** (harga naik + OI naik + FR netral) ke
**seluruh** 168 jam, lalu membandingkannya dengan short asal-asalan:

| Tahan | Sinyal | Winrate | Dasar pembanding | Selisih |
|---|---|---|---|---|
| 6 jam | **−1,05%** | 43% (n=37) | −0,50% | **−0,55 pp** (lebih buruk) |
| 12 jam | **−0,19%** | 49% (n=37) | −1,28% | +1,10 pp (lebih baik, tapi tetap negatif) |
| 24 jam | **−5,00%** | **26%** (n=35) | −4,02% | **−0,98 pp** (lebih buruk) |

**Verdict: TIDAK-TERBUKTI** — 1 dari 3 horizon lebih baik, dan **tidak ada satu pun** yang
sekaligus positif *dan* lebih baik.

**Kontrol BTCUSDT** (tidak overextended, +5,8%): pola yang sama → **0 dari 3** horizon lebih baik.
Jadi hasilnya bukan kebetulan satu simbol.

Artinya: 38 jam di window itu memenuhi tanda tangan sinyalnya. **37 di antaranya kalah.** Yang dia
pamerkan adalah satu-satunya yang menang — dan itu jam puncak.

## 4. Cacat metode yang sama seperti klaim LP sebelumnya

1. **Ditulis setelah tahu hasilnya.** "Buyer exhaustion" terlihat jelas di belakang; saat itu data
   menunjukkan uang baru masih masuk (OI +10,7%).
2. **Sinyal yang disebut tidak menyala.** FR tidak pernah ramai; OI sedang naik. Dua dari tiga
   alasannya bertentangan dengan data.
3. **Percobaan pertama kena SL** — konsisten dengan short ke arah momentum, bukan ke arah sinyal.
4. **Tanpa stop, ukuran posisi, R, atau n.** "Masih hold" = belum terealisasi.
5. **Seleksi hasil.** Satu trade dipamerkan dari 38 kesempatan.

---

## 5. Yang dibangun dari pelajaran ini

`packages/live-trading/src/live_trading/collectors/overextended.py`

| Fungsi | Guna |
|---|---|
| `ukur_kelebihan()` | Fakta yang bisa dilihat **sekarang**: pump %, posisi harga vs puncak, OI vs puncak, apakah OI sudah mereda, FR maks/median, apakah funding pernah ramai |
| `uji_edge_short()` | Menjalankan aturan ke **seluruh** data + **dasar pembanding** → keputusan `ada-keunggulan` / `tidak-terbukti` / `tidak-ada-sinyal` |

Aturan yang dipegang:

- **`overextended` adalah fakta harga, BUKAN sinyal short.** Itu tertulis di setiap keluaran.
- **Dasar pembanding selalu dilaporkan** — termasuk saat tidak ada sinyal sama sekali.
- **Satu trade yang berhasil tidak membuktikan apa pun**; yang membuktikan adalah menjalankan
  aturan ke seluruh data.

**Uji:** 12 tes baru · **491 tes lulus** · ruff bersih.

### Keluaran nyata

```
================ VELVETUSDT ================
  pump +80,2%  |  turun dari puncak -26,5%  |  overextended: True
  OI puncak 7,85jt @ 03/10 07:00  |  OI sekarang 5,21jt  (-33,6% dari puncak)
  funding maks +0,0381% / median +0,0124%  |  pernah ramai: False
    · funding tidak pernah ramai — jadi 'long crowded' tidak terlihat di sini
  --- uji edge short (n sinyal 38 dari 168 jam) ---
    tahan  6j: sinyal -1,05% (menang 43%) | dasar -0,50% | selisih -0,55pp
    tahan 12j: sinyal -0,19% (menang 49%) | dasar -1,28% | selisih +1,10pp
    tahan 24j: sinyal -5,00% (menang 26%) | dasar -4,02% | selisih -0,98pp
  VERDICT: TIDAK-TERBUKTI
```

---

## 6. Kesimpulan

1. **Tradenya untung — itu fakta.** Yang tidak benar adalah **alasan yang dia tulis**.
2. **Tiga sinyal yang dia sebut: dua bertentangan dengan data** pada jam yang dia klaim
   (OI di puncak dan naik; FR tidak pernah ramai).
3. **Sebagai aturan, polanya tidak punya keunggulan** — 26–49% winrate, rata-rata negatif, dan
   tidak lebih baik daripada short asal-asalan.
4. **Yang bisa dipakai dari post itu:** daftar **apa yang harus diukur** (OI, FR, taker) — bukan
   arah tradingnya. War Room sudah mengumpulkan ketiganya.
5. **Pelajaran yang sejalan dengan klaim LP BAGSPAY:** angka di media sosial biasanya nyata,
   tapi **alasannya** yang tidak bisa diaudit. Alat ukur kita menutup celah itu.

## Langkah berikutnya

- Sambungkan `ukur_kelebihan` + `uji_edge_short` ke `bagian` snapshot supaya kelihatan di UI
  (perlu cache 1 jam; 3 panggilan API per simbol).
- Tambah **CVD sungguhan** dari data aggTrade — sinyal ketiga yang dia sebut tapi tidak kita punya
  dalam bentuk itu; saat ini hanya `taker` (taker buy/sell) sebagai proksi.
