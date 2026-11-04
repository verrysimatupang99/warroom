# Analisa Penuh — Planetx Trading Journal (200 trade) + Sistem Crypto Sendiri

Tanggal: 24 Okt 2026
Sumber data:
- Planetx: database publik `My Trades`, 200 baris diekstrak via browser (`planetx_200.csv`)
- Milik sendiri: database `Trades` + `Snapshots` via Notion connector

---

# BAGIAN A — Planetx Trading Journal

## Cakupan data
- 200 baris; **175 punya nilai P/L**, 25 kosong (kemungkinan masih terbuka)
- Rentang: Feb 2025 – Sep 2026, tapi **95% data ada di Apr–Sep 2026**
- Dua akun: `disqi` (98) dan `minra` (72), plus 4 tanpa akun
- Kolom `Followed rules`, `BE`, `Rating`, `WIN` **kosong semua** (checkbox tak terbaca / tidak diisi)
- **Satuan P/L tidak konsisten**: kerugian maksimal hanya −143, tapi kemenangan ada yang
  +13.876 dan +36.339. Kemungkinan campuran spot vs perp dengan ukuran posisi berbeda.

> **Konsekuensi:** profit factor dan total P/L **tidak bisa dipercaya**.
> Yang bisa dipercaya: **win rate** dan perbandingan relatif antar kelompok.

## Hasil keseluruhan
| Metrik | Nilai |
|---|---|
| Trade dengan P/L | 175 |
| Menang | 131 (**74,9%**) |
| Kalah | 44 (25,1%) |
| Median P/L | +57 |
| Median menang | +87 |
| Median kalah | −25,5 |
| Kerugian terbesar | −143 |
| Kemenangan > 500 | 13 trade |
| Kemenangan > 1.000 | 6 trade |

Bentuk distribusinya **asimetris ekstrem**: kerugian dipotong cepat (mayoritas −20 s/d −50),
sementara pemenang dibiarkan jalan sampai ratusan/ribuan.

## Per Model
| Model | n | Win% | Median |
|---|---|---|---|
| Model 2 | 72 | **79,2%** | **+74** |
| Model 1 | 89 | 74,2% | +48 |
| (kosong) | 14 | 57,1% | +2 |

## Per Sesi
| Sesi | n | Win% | Median |
|---|---|---|---|
| Asian | 55 | **78,2%** | +45 |
| New York | 53 | 75,5% | +58 |
| London | 53 | 75,5% | **+77** |

## Per Arah
| Arah | n | Win% | Median |
|---|---|---|---|
| LONG | 140 | 76,4% | +58 |
| SHORT | 21 | 76,2% | +76 |

Catatan: sampel SHORT hanya 21 — **tidak cukup** untuk menyimpulkan SHORT lebih baik.
Journal ini sangat bias LONG (80%).

## Per Akun
| Akun | n | Win% | Median |
|---|---|---|---|
| minra | 72 | **79,2%** | **+76** |
| disqi | 98 | 70,4% | +44 |

Selisih 8,8 poin persentase. Bisa disiplin, bisa juga beda jenis koin/sizing.

## Per Entry Window (jam New York)
| Window | n | Win% | Median |
|---|---|---|---|
| **6-7am** | 19 | **84,2%** | **+178** |
| 11-12pm | 26 | 80,8% | +51 |
| 8-9am | 25 | 80,0% | +57 |
| 3-4pm | 19 | 78,9% | +67 |
| 7-8am | 29 | 72,4% | +69 |
| 10-11am | 18 | 72,2% | +54 |
| **2-3pm** | 8 | **50,0%** | **+20** |

Jam **06:00–09:00 NY** = jendela terbaik (73 trade, win 80%+).
Jam **14:00–15:00 NY** = terburuk.

## Tag — ini temuan paling tajam
| Tag | Ada tag | Tanpa tag | Selisih |
|---|---|---|---|
| `perfect-entry` (positif) | n=91, **94,5%** | n=84, 53,6% | **+40,9 pp** |
| `well-managed` (positif) | n=156, 77,6% | n=19, 52,6% | +25,0 pp |
| `early-exit` (negatif) | n=46, 89,1% | n=129, 69,8% | +19,3 pp |
| `sl-placement` (negatif) | n=32, **3,1%** | n=143, 90,9% | **−87,8 pp** |
| `revenge` (negatif) | n=6, **0,0%** | n=169, 77,5% | −77,5 pp |

**Peringatan metodologis:** tag diisi **setelah** trade selesai (hindsight).
`perfect-entry` 94,5% hampir pasti sebagian akibat bias ini — trade yang sudah jelas
menang baru diberi label "entry sempurna". Jadi jangan dibaca sebagai prediktor.

Yang **tetap valid**: `sl-placement` (3,1% win, n=32) dan `revenge` (0% win, n=6).
Keduanya menandai trade yang **sejak awal** cacat. Kalau tag ini diisi **sebelum** entry,
keduanya bisa jadi filter veto yang kuat.

## Bulanan
| Bulan | n | Win% |
|---|---|---|
| 2026-04 | 14 | 71,4% |
| 2026-05 | 29 | 69,0% |
| 2026-06 | 35 | 68,6% |
| 2026-07 | **56** | 73,2% |
| 2026-08 | 26 | **80,8%** |

Tren membaik: 68,6% (Jun) → 73,2% (Jul) → 80,8% (Agu).

---

# BAGIAN B — Sistem Crypto Anda Sendiri (4 panel)

Snapshot terakhir: 22 Okt 2026 12:04 (nilai identik sejak 10:04 — job snapshot menulis ulang angka sama).

| Panel | Ekuitas | Realized | Win rate | Trade ditutup |
|---|---|---|---|---|
| SMC | 10.173,10 | **+174,93** | 56,4% | 55 |
| Fib GP | 9.797,54 | −202,46 | **58,3%** | 36 |
| Squeeze | 9.542,53 | −457,47 | 54,6% | 22 |
| **Break&Retest** | **8.911,12** | **−1.088,88** | 53,1% | 32 |

Modal awal 4 panel = 40.000 → sekarang 38.424,29 = **−1.575,71 (−3,94%)**.

**Break&Retest menyumbang 69% dari seluruh kerugian** (−1.088,88 dari −1.575,71)
padahal hanya 32 dari 145 trade (22%).

Dari sampel 5 trade terakhir: R tercatat −1,10 / −1,10 / −1,20 / −1,14 dan +0,25.
**R negatif konsisten di bawah −1,0** → ada slippage/biaya di luar jarak SL murni
(sekitar 10–20% dari risk per trade). Ini bocor halus tapi pasti.

## Perbandingan dua sistem
| Aspek | Planetx | Sistem Anda |
|---|---|---|
| Normalisasi risiko | **tidak ada** (P/L campur) | **ada** (kolom R + SL %) |
| Jumlah trade | 200 | 145 |
| Win rate | 74,9% | 53–58% |
| Panel/strategi dilacak | Model 1 / Model 2 | 4 panel + versi |
| Kill switch | tidak terlihat | `btc_killswitch`, `sl>2.5%` |
| Tag proses | ada, tapi hindsight | belum ada |

Ironi: **schema Anda lebih baik** (R, SL%, versi, alasan skip), tapi win rate jauh lebih rendah.
Selisih 75% vs 55% itu terlalu besar untuk diabaikan — kemungkinan besar bukan karena
Planetx lebih hebat, tapi karena **cara hitung menang berbeda** (Planetx menghitung
"exit di atas nol" sebagai menang; sistem Anda menghitung BE sebagai menang juga,
tapi SL yang kena setelah partial bisa tercatat sebagai loss penuh).

**Ini yang perlu diverifikasi lebih dulu sebelum menyimpulkan apa pun tentang edge.**

---

# Kesimpulan & Rekomendasi

## Untuk Planetx (kalau mau ditiru)
1. **Jangan tiru kolom P/L-nya.** Tanpa normalisasi R, seluruh statistik finansialnya
   tidak bisa dipakai. Tiru **strukturnya**, bukan angkanya.
2. **Adopsi `sl-placement` dan `revenge` sebagai tag veto.** Win rate 3,1% dan 0%
   → dua tag ini praktis berarti "trade ini sudah gagal sebelum dimulai".
3. **Adopsi Entry Window.** Jam 06:00–09:00 NY konsisten terbaik; 14:00–15:00 terburuk.
   Ini murah diterapkan dan langsung terukur.
4. **Jangan adopsi `perfect-entry` sebagai filter** kecuali diisi **sebelum** entry.
   Nilai 94,5%-nya adalah artefak hindsight.
5. **`early-exit` 89,1% menang** → mereka memotong pemenang. Kalau mau meniru,
   tiru kebalikannya: biarkan pemenang jalan lebih lama.

## Untuk sistem Anda (prioritas lebih tinggi)
1. **Audit Break&Retest atau matikan sementara.** −1.088,88 dari total −1.575,71.
   Panel dengan kontribusi kerugian 69% pada 22% trade adalah tempat kebocoran utama.
2. **Selidiki R < −1,0.** Rata-rata −1,14 berarti setiap loss 14% lebih besar dari
   yang direncanakan. Pada 145 trade, itu setara ~20R hilang murni dari eksekusi.
   Cek: slippage entry, spread saat entry, atau SL yang dipasang terlalu rapat.
3. **Tambah kolom tag proses** (perfect-entry, sl-placement, early-exit) tapi isi
   **saat entry**, bukan setelah. Baru setelah itu bisa dipakai sebagai filter.
4. **Tambah kolom Entry Window** (jam WIB atau UTC) — sudah ada `Buka`/`Tutup`,
   tinggal diturunkan jadi bucket jam.
5. **Perbaiki job snapshot.** Nilai identik sejak 10:04 → 11:06 → 12:04 menunjukkan
   penulisan berulang tanpa perubahan, bukan snapshot baru.

## Keterbatasan analisa ini
- 25 dari 200 trade Planetx tanpa P/L (tidak dihitung)
- 14 trade tanpa Model/Sesi/Window
- Tag Planetx diisi setelah trade (hindsight) — korelasi ≠ sebab
- Satuan P/L Planetx tidak konsisten → PF/expectancy tidak valid
- Data sistem Anda: hanya 5 trade individual + snapshot agregat; analisa per-trade
  penuh belum dilakukan (butuh tarik ~145 baris, payload besar)
