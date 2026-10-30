# Perbandingan sinyal DeepSeek (chat) vs jurnal sinyal War Room

**Tanggal:** 30 Okt 2026  
**Sumber DeepSeek:** ekspor Telegram “Hermes DeepSeek Nicolas”, 1 Sep–31 Okt 2026
(10.125 pesan). **Bukan** War Room.  
**Sumber War Room:** `/var/lib/warroom/jurnal_sinyal.json` (job `jurnal-sinyal`, 450 sinyal
terkirim, dihitung dari candle sejak jam setelah kirim).

CSV hasil ekstraksi: `artifacts/perbandingan-sinyal/deepseek_jurnal.csv`.

## Metode

- Ekstrak klaim jurnal yang eksplisit dari chat: entry/SL/TP/outcome/R, plus ringkasan
  agregat yang disebut bot.
- **Tidak ada file jurnal mentah** (`xauusd_journal.xlsx`, `crypto-watchlist.json`) di
  dalam ekspor Drive — yang tersedia hanya teks chat. Jadi CSV berisi baris yang bisa
  dibuktikan dari pesan, bukan rekonstruksi semua trade.
- Backtest dan simulasi **tidak** dicampur ke metrik live.
- R yang tidak disebut eksplisit dikosongkan, bukan diisi nol.
- Koreksi di chat dipakai sebagai nilai final (contoh: BE dikoreksi menjadi SL).

## Hasil DeepSeek yang bisa diukur

| Sumber | n | Hasil |
|---|---:|---|
| XAUUSD awal Sep (8–9 signal) | 8–9 | WR 20–25%, total **+0,32R**, praktis flat (±+0,04R/signal) |
| Crypto 18 item closed (13 Okt) | 18 | 10 SL · 2 TP2 · 1 TP1 · 2 expired · 2 manual · 1 cancelled |
| Estimasi crypto dari distribusi | 18 | sekitar **−5R** jika TP2=2R/TP1=1R → **−0,28R/signal** |
| Trade dengan R eksplisit di chat | 9 | 3 menang / 6 kalah, total **−3,67R**, expectancy **−0,408R**, WR **33,3%** |
| Simulasi 21 trade scalping | 21 | SL lama −3,87R; SL ATR +0,25R (simulasi, bukan live) |
| Backtest 444 trade | 444 | klaim +56R/+57R/+28R crypto, +41R/+39R/+3R forex — **backtest, bukan live** |

## Jurnal War Room (pembanding)

| Kelompok | n terkirim | n terisi | WR | Gross | Net (fee 5 bps) |
|---|---:|---:|---:|---:|---:|
| Semua | 450 | 334 | 54,5% | +0,163R | **+0,102R** |
| PREMIUM | 213 | 157 | 58,6% | +0,286R | **+0,230R** |
| STANDAR | 237 | 177 | 50,8% | +0,054R | **−0,012R** |

Sejak 30 Okt, Telegram War Room hanya mengirim PREMIUM; STANDAR tetap diukur.

## Perbandingan langsung

| Aspek | DeepSeek (chat) | War Room |
|---|---|---|
| Sampel live | 8–9 XAU + 18 crypto closed; tidak ada seri penuh | 450 sinyal, 334 terisi |
| WR | XAU 20–25%; subset eksplisit 33,3% | 54,5% (PREMIUM 58,6%) |
| Expectancy | XAU ±+0,04R/signal; crypto estimasi −0,28R; subset eksplisit −0,41R | gross +0,163R; net +0,102R |
| Konsistensi jurnal | pernah reset 21 Sep & 9 Okt; bug parser R/status; angka berubah | satu seri as-sent, dedupe, dihitung ulang dari Binance |
| Biaya | tidak konsisten disebut | fee 5 bps/sisi + stres 10 bps |
| Backtest | positif besar (+650R, +1.571R) tetapi tidak live | bukan klaim utama; fokus bukti live |

## Putusan

1. **Secara live, jurnal DeepSeek belum menunjukkan expectancy positif.** XAU praktis
   flat; crypto dari distribusi 18 closed cenderung negatif; subset R eksplisit −0,41R.
2. **Backtest DeepSeek tidak bisa dipakai membandingkan edge live** — itu in-sample,
   berbeda periode, dan beberapa hasil langsung diubah setelah evaluasi (PD dicabut).
3. **War Room lebih auditable**, tetapi edge-nya tipis (+0,102R net) dan baru 15 hari;
   PREMIUM yang layak, STANDAR tidak.
4. **Tidak apple-to-apple**: DeepSeek mayoritas XAU/crypto dengan strategi yang berubah
   berkali-kali; jurnal War Room yang dibandingkan adalah sinyal crypto. War Room forex
   belum punya trade tertutup, jadi XAU tidak bisa dibandingkan langsung.

## Batas

- Angka DeepSeek berasal dari klaim bot di chat, bukan verifikasi independen.
- Beberapa trade tidak punya R eksplisit; CSV menandai `kepastian`.
- Ekspor berisi kredensial OKX; folder Drive sebaiknya dibatasi/dihapus dan key dirotasi.
- CSV tidak memuat kredensial; salinan mentah ekspor sudah dihapus dari host ini setelah
  ekstraksi.
