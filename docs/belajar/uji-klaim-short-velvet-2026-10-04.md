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

## 6. Sinyal ketiga (CVD) diuji sungguhan — dan hasilnya lebih buruk

Awalnya dicatat "CVD tidak tersedia". Ternyata bisa dihitung dari klines: kolom 9
(`takerBuyBaseAssetVolume`) dan kolom 5 (`volume`) memberi delta agresi beli/jual per bar —
`delta = 2·takerBuyBase − volume`. Itu CVD sungguhan, bukan proksi, dan riwayatnya panjang
(berbeda dari `aggTrades` yang cuma beberapa menit terakhir).

`uji_kehabisan_pembeli()` mencari divergensi bearish: **harga membuat puncak lebih tinggi,
tapi CVD pada puncak itu lebih rendah** — persis "buyer exhaustion" yang dia klaim.

| Aturan yang diuji | 6 jam | 12 jam | 24 jam | Verdict |
|---|---|---|---|---|
| OI + FR | −1,05% (43%) | −0,19% (49%) | −5,00% (26%) | **tidak terbukti** |
| **Divergensi CVD** | **−1,57% (41%)** | **−2,90% (36%)** | **−7,42% (26%)** | **tidak terbukti** |

Divergensi CVD menyala di **81 dari 168 jam** — dan di ketiga horizon hasilnya **lebih buruk
daripada sinyal OI/FR**, juga lebih buruk daripada short asal-asalan. Kontrol BTCUSDT: 13 sinyal,
winrate 8–23%, juga lebih buruk di ketiga horizon.

**Jadi sinyal yang paling dia banggakan ("buyer exhaustion") justru yang paling buruk.**

### Kelemahan alat sendiri yang ketemu di sini

Putusan pertama terlalu longgar: **4 dari 6 koin besar terbaca "ada-keunggulan"** — padahal
seluruh pasar sedang turun, jadi short menang *apa pun* sinyalnya. Itu beta pasar, bukan edge.
Diperketat:

- perlu **≥2 horizon** lebih baik (bukan 1),
- verdict baru **`perlu-uji-tambahan`** saat dasar pembanding positif di **semua** horizon
  ("pasar sedang turun, jadi short menang apa pun sinyalnya"),
- setiap hasil membawa catatan **"diuji pada N jam — satu rezim pasar; bukti lemah"**.

## 7. 🔴 Akar sebenarnya kenapa `bagian` terus kehilangan isi

Ini ditemukan saat menyambungkan panel ke UI. Gejala: `state/snapshot.json` hanya punya **7
bagian** (macro, lp, overextended hilang) **tanpa error apa pun**, padahal job melaporkan `ok`.

Dua perbaikan sebelumnya (timeout 300→900 s, `observed_at` WIB) **hanya menutupi gejala**. Akarnya:

> `_jalankan_lt()` mengambil biner `lt` dari **`WARROOM_DOMAIN_HOME/.venv/bin/lt`** —
> dan `/home/admin/live-trading/.venv` adalah **venv LAMA** yang meng-import dari
> `/home/admin/live-trading/src` (source sebelum merge).

Jadi **semua job worker yang memanggil `lt` menjalankan kode sebelum merge** — termasuk
`refresh-snapshot` dan `collect`. Venv yang benar (`/home/admin/warroom/.venv`) meng-import dari
`packages/live-trading/src`, dan jalan manual memakai venv itu — itu sebabnya uji manual selalu
"berhasil" sementara job produksi diam-diam memakai kode lama.

**Perbaikan:** `_lt_bin()` memakai venv tempat worker berjalan (`sys.executable`), bukan venv di
domain home. Dikunci 3 tes.

Bukti sesudah perbaikan — snapshot **dari job**, bukan manual:

```
bagian: 10 ['crypto','dex','forex','hyperliquid','idx','idx616','idx_tv','lp','macro','overextended']
  macro: ADA   lp: ADA   overextended: ADA
```

Pelajaran yang layak diingat:

1. **Venv yang salah = kode yang salah, tanpa error.** "Job ok" dan "kode benar" adalah dua
   pernyataan berbeda.
2. **Uji manual harus memakai jalur yang SAMA dengan produksi.** Uji manual di sini memakai venv
   berbeda dari job — itu yang menyembunyikan bug selama beberapa siklus.
3. **Kalau bagian hilang tanpa error, curigai biner/lingkungan, bukan logika.**

---

## 8. Yang dibangun: panel `/overextended`

`apps/web/src/routes/overextended/+page.svelte` + nav `⟰ Overextended`.

Aturan halaman: **label "overextended" tidak pernah tampil sendirian.** Setiap baris wajib
membawa hasil uji edge + tabel dasar pembanding per horizon.

Contoh isi nyata (4 Okt):

```
LINKUSDT  pump +20,2%  cvd-div False  OI/FR perlu-uji-tambahan  CVD tidak-terbukti
SUIUSDT   pump +18,3%  cvd-div True   OI/FR perlu-uji-tambahan  CVD tidak-terbukti
SOLUSDT   pump  +6,5%  cvd-div True   OI/FR ada-keunggulan      CVD ada-keunggulan
BNBUSDT   pump  +6,0%  cvd-div False  OI/FR tidak-terbukti      CVD tidak-terbukti
BTCUSDT   pump  +5,8%  cvd-div False  OI/FR tidak-terbukti      CVD tidak-terbukti
ETHUSDT   pump  +5,5%  cvd-div True   OI/FR ada-keunggulan      CVD ada-keunggulan
```

Perhatikan LINKUSDT: pump terbesar (+20,2%) tapi veredictnya **`perlu-uji-tambahan`** — karena
pasar sedang turun, keunggulannya belum bisa dinilai. Justru itu gunanya halaman ini.

---

## 9. Kesimpulan

1. **Tradenya untung — itu fakta.** Yang tidak benar adalah **alasan yang dia tulis**.
2. **Tiga sinyal yang dia sebut: dua bertentangan dengan data** pada jam yang dia klaim
   (OI di puncak dan naik; FR tidak pernah ramai).
3. **Sebagai aturan, polanya tidak punya keunggulan** — 26–49% winrate, rata-rata negatif, dan
   tidak lebih baik daripada short asal-asalan. **Sinyal CVD-nya yang paling buruk.**
4. **Yang bisa dipakai dari post itu:** daftar **apa yang harus diukur** (OI, FR, CVD) — bukan
   arah tradingnya. War Room kini mengukur ketiganya, plus menguji apakah pengukurannya berguna.
5. **Pelajaran yang sejalan dengan klaim LP BAGSPAY:** angka di media sosial biasanya nyata,
   tapi **alasannya** yang tidak bisa diaudit. Alat ukur kita menutup celah itu.

## Langkah berikutnya

- Uji edge pada **beberapa rezim pasar** (bukan 168 jam tunggal) supaya `ada-keunggulan` punya
  bobot lebih dari "bukti lemah".
- **MEXC API key** (menunggu pemilik) untuk eksekusi crypto nyata.

