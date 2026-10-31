# Matriks keputusan vendor EA — 31 Okt 2026

Sumber angka: `docs/rencana-scrum-20261030.md` (backtest 3 tahun, lot tetap 0,01).
Tidak ada track record live. Status keduanya **trial**.

| EA | Backtest 3 tahun | PF/DD | Track record live | Status | Rekomendasi |
|---|---:|---|---|---|---|
| FomoFX Galaxius | +$7.348 | tidak tersimpan di repo | tidak ada | trial | **paper/demo saja**; jangan live |
| FomoFX GoldenBall | +$3.709 | tidak tersimpan di repo | tidak ada | trial | **paper/demo saja**; jangan live |
| WarRoom Reaper v3 | +13,48% ($1k), PF 1,13, DD 9,11% | ada | demo, 0 trade tertutup | live demo | lanjut forward test |

## Syarat sebelum naik ke uang nyata

1. Backtest dengan biaya realistis (spread/slippage/komisi) dan laporan PF/DD tersimpan.
2. Forward test **20 trade tertutup** atau 30 hari di demo, dengan deal tertrack.
3. Batas risiko per trade dan max DD disepakati; lot tidak naik sebelum lulus.
4. Cek masa berlaku/lisensi trial; jangan mengakali proteksi vendor.

## Catatan

- Angka +$7.348/+$3.709 adalah **backtest**, bukan hasil live; tidak boleh dipakai
  sebagai janji profit.
- Kedua EA tidak dijalankan di akun live; file ada di `/home/admin/mt5-experts/`.
- Jika owner ingin menguji, gunakan akun demo terpisah dan lot minimum; jangan campur
  dengan Reaper di akun yang sama.
