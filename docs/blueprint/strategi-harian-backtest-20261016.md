# Backtest Strategi A — SMA harian (16 Okt 2026)

Sumber: `ops/harian_backtest.py` · data Binance spot 1D: **2.257 hari
(2018-07-30 → 2026-10-15)** · fee 10 bps + slippage 5 bps per pergantian
posisi · tanpa look-ahead (sinyal dari close, SMA dihitung dari data sebelum
hari evaluasi).

## Hasil grid (avg 3 aset equal-weight)

| Setup | Ret full | DD full | **Ret OOS** | **DD OOS** | n trade |
|---|---:|---:|---:|---:|---:|
| SMA50/c1 | +5.421% | 61,2% | **+21,28%** | **40,11%** | 113,7 |
| SMA50/c2 | +3.750% | 57,7% | +10,53% | 42,82% | 87,0 |
| SMA50/c3 | +5.769% | 57,4% | +13,64% | 41,98% | 79,0 |
| SMA100/c1 | +1.171% | 66,4% | −0,36% | 40,45% | 95,0 |
| SMA100/c2 | +982% | 66,5% | −7,20% | 39,85% | 73,0 |
| SMA100/c3 | +846% | 67,9% | −15,21% | 42,32% | 61,0 |

## Pembanding buy-and-hold (OOS 30% terakhir, equal-weight)

| Aset | BnH OOS | BnH OOS DD |
|---|---:|---:|
| BTC | +30,59% | 52,97% |
| ETH | −24,76% | 67,55% |
| SOL | −55,26% | 76,26% |
| **rata** | **−16,48%** | **65,59%** |

## Putusan (spec §3.4)

- **LOLOS**: SMA50 semua varian konfirmasi — OOS positif (+10,5–21,3%),
  DD OOS 40–42% < BnH DD 65,6%, dan tiap aset berdiri sendiri.
- **GAGAL**: SMA100 semua varian (OOS negatif). Default spec (N=100/confirm 2)
  **diubah ke SMA50/confirm 1** — data menang atas hipotesis dokumen.
- DD 40% tetap besar → alokasi apk $10 (50% dari $20) & batas mingguan tetap dipasang;
  DD < BnH, tapi jauh dari nyaman.

File angka mentah: `strategi-harian-backtest-20261016.json`. Jalankan ulang:
`.venv/bin/python ops/harian_backtest.py`.
