# Pakem bukti + LP terukur (6 Okt 2026)

Arahan owner: *"bantu gw bangun ini agar tidak hanya bagus secara tampilan tapi juga teruji
secara hasil, utamanya sinyal dan paper trade … akurasi sinyal, PnL paper per market …
semua yang dibutuhkan ditampilkan di website harus selaras dengan apa yang ada di balik layar"*.

Keputusan owner yang mengikat sesi ini:
1. **Prioritas**: Meteora/LP + GMGN dulu, lalu Polymarket.
2. **Kunci MEXC Tencent milik kawan** — jangan disentuh; eksekusi nyata bukan urusan kita.
3. **Mark LP**: `gmgn-cli` (dipakai bila lookup per alamat tersedia; sekarang DexScreener
   per alamat pool — lihat catatan di bawah).
4. **Pakem bukti** (diangkat dari Tencent `signal-performance-validation`):
   `<10` INSUFFICIENT · `10–29` DIRECTIONAL · `≥30` PRELIMINARY · `≥100` TUNING;
   wajib expectancy bersih + biaya + **koreksi klaster hari**.

---

## 1. Pakem bukti — `packages/live-trading/src/live_trading/pakem.py`

- `nilai_pakem(closes)`: satu fungsi untuk SEMUA market. Menghitung n tuntas,
  **n hari independen**, win rate + interval Wilson 90%, expectancy, profit factor,
  max drawdown, lalu menetapkan tingkat.
- Aturan yang dikodekan: win rate tinggi tidak pernah cukup; sampel nol → INSUFFICIENT
  (bukan "0%"); tanggal tidak ada → dicatat jujur, bukan diasumsikan.
- 3 tes ambang + koreksi klaster + "WR tinggi tapi expectancy negatif ditolak".

## 2. Mark LP terukur — `lp_mark.py` + `lp_mark_run.py` + `lt lp-mark`

Rangkaian penuh, read-only pasar:

1. baca posisi LP terbuka (`~/gmgn-scan/lp_paper_state.json` — mesin GMGN yang sudah ada);
2. tarik harga & V/L **nyata per alamat pool** (`collectors/dexscreen.mark_pool`);
3. hitung **fee taksiran + IL + LP vs hold** (rumus IL 50/50 yang sama dengan
   `lp_paper.il_5050` dan `lp_positions._hitung` — satu rumus, bukan tiga);
4. tulis jejak append-only `state/lp_ledger.jsonl`;
5. nilai jejak terhadap pakem bukti (**n = hari unik**, bukan jumlah baris);
6. simpan `state/lp_mark_terakhir.json` untuk panel (tanpa panggilan pasar saat render).

**Bukti jalan (6 Okt, posisi UBI nyata):**

```
$ lt lp-mark
  LP mark: 1 posisi → /home/admin/live-trading/state
    UBI  dinilai  px 5.8210954e-06→2.85e-06  fee* 1.300299  IL -6.0535%  pnl* -0.515737
         vs-hold 1.300299
  total pnl* $-0.515737 (fee = taksiran; V/L hari ini × tier × hari)
  pakem: INSUFFICIENT (n=1 trade, 1 hari)
    - sampel kurang: 1 < 10 (hari/trade efektif)

job worker: lp-mark ok  →  gmgn-sync: lp_mark=ok
```

Catatan penting yang **tidak** disembunyikan:
- `fee` adalah **taksiran** (V/L hari ini dipakai untuk seluruh umur posisi; V/L berubah);
- posisi UBI di chain `arc` — DexScreener mengembalikan `pairs: null` untuk lookup pair
  langsung, jadi `mark_pool` mencoba `pairs/{rantai}/{alamat}` → `pairs/{alamat}` →
  `tokens/{alamat}` dan memilih pool **terlikuiditas terbesar**. Alamat di state LP
  ternyata token address, bukan pair address — inilah mengapa fallback itu wajib.
- Owner menyebut `gmgn-cli`; yang dipakai sekarang DexScreener karena `gmgn-cli` mencari
  pool per rantai+trending, sedangkan kita butuh lookup **per alamat**. Bila `gmgn-cli`
  menyediakan lookup alamat, cukup ubah `lp_mark_run._harga_pool` (satu titik).

## 3. Yang menyala sekarang (production)

| Bagian | Status |
|---|---|
| Job `lp-mark` (setiap 1 jam) | aktif, `last_status=ok` |
| Job `radar-update` (30 mnt) | aktif, radar lokal |
| Fakta `gmgn/lp_mark` | diterbitkan oleh `gmgn-sync` (TTL 2 jam) |
| Panel GMGN → LP | blok "Mark Terukur — Fee, IL, LP vs Hold" + label pakem |
| `lt lp-mark` | perintah CLI manual untuk verifikasi |

## 4. Yang belum (jujur)

- **n masih 1 hari** → pakem INSUFFICIENT. Jejak akan tumbuh setiap jam; tingkat naik
  sendiri saat ambang tercapai. Tidak ada yang boleh mengklaim "terbukti" sebelum itu.
- **Porsi in-range tidak tersedia** — pool ber-range (DLMM) butuh itu untuk fee nyata;
  sekarang dilabeli taksiran.
- **Market lain belum disambungkan ke pakem**: crypto (measure.py sudah punya n & win rate,
  tinggal dibungkus pakem), IDX & Forex (ledger Tencent belum diangkat — lihat
  `peta-market-dan-bukti-2026-10-06.md`), Polymarket (gate sudah punya deff; tinggal label).
- **UI lain**: halaman per-market yang menampilkan akurasi & PnL paper per market
  (nilai owner: "semua yang ada di website selaras dengan balik layar") menyusul setelah
  LP stabil — jangan menampilkan label pakem di tempat yang angkanya belum mengalir.
