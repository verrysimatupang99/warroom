# Keputusan gate — 31 Okt 2026 (untuk owner)

**Pertanyaan:** pakai CI 90% (default platform) atau 95% + koreksi klaster (kebijakan
alat Poly)? **Ini keputusan owner; belum diubah di kode.**

## Bukti sampel

| Kelompok | n terisi | WR | Net expectancy | Butuh n untuk 90% (deff 1) | Butuh n untuk 95% (deff 1,5) |
|---|---:|---:|---:|---:|---:|
| Semua sinyal | 334 | 54,5% | +0,0997R | 345 | 700 |
| PREMIUM | 157 | 58,6% | +0,2298R | 99 | 210 |
| STANDAR | 177 | 50,8% | −0,0117R | — (di bawah/sekitar BE) | — |

Dihitung dengan `warroom_core.gate.required_n(be=0,50, win_rate, ci, deff)`.

## Opsi

**A. CI 90% (default platform sekarang)**
- Kelebihan: PREMIUM sudah lolos secara sampel (157 ≥ 99); keputusan bisa diambil lebih
  cepat; cocok untuk paper/forward test.
- Kekurangan: false positive lebih besar; 334 sampel agregat masih 11 kurang dari 345.

**B. CI 95% + deff 1,5 (kebijakan alat Poly)**
- Kelebihan: lebih konservatif untuk uang nyata; memperhitungkan klaster.
- Kekurangan: PREMIUM butuh 210 sampel (baru 157); agregat butuh 700. Belum ada yang
  lolos sekarang; menunggu berminggu-minggu.

**C. Dua tingkat (rekomendasi teknis, bukan keputusan)**
- PREMIUM: 90% + deff 1,0 untuk paper; naik ke 95% + deff 1,5 sebelum uang nyata.
- STANDAR: tetap tidak dikirim (net negatif); jangan dipromosikan.

## Yang tidak boleh dilakukan

- Menurunkan `deff` < 1 atau memilih CI setelah melihat hasil (peeking).
- Menggabungkan versi strategi berbeda tanpa label (`per_versi` sudah memisahkan).
- Memakai backtest sebagai pengganti sampel live.

**Status:** menunggu keputusan owner. Tidak ada perubahan ambang di kode.
