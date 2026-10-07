# Audit Kesiapan Dashboard — 7 Okt 2026

*Diminta pemilik: "rechek ulang kesiapan dashboard". Ini hasil periksa menyeluruh.*

## 1. Infrastruktur — SEHAT

| Layanan | Status | Uptime (dari) |
|---|---|---|
| warroom-web (:3100) | active | 07 Okt 03:30 UTC |
| warroom-api (:8800) | active | 06 Okt 21:44 UTC |
| warroom-worker | active | 06 Okt 21:26 UTC |
| nginx (:80/:443) | active | — |

- **26 job terjadwal, 0 gagal.** Tidak ada job overdue.
- Port 80/443/3100/8800 semua listen; API memori 227 MB (batas 1 GB).

## 2. Fakta & kesegaran — SEHAT

- **Semua 19 fakta kritis SEGAR** (umur 18 menit vs TTL 30 menit): bagian, crypto_sinyal,
  forex_sinyal, idx_sinyal, pasar_akurasi, dompet, bandarmologi_skor, lp_verifikasi,
  equity, ledger, radar, kandidat, pengukuran, backtest, pod_llm, dst.
- Siklus `refresh-snapshot` (15 mnt) → `publish-facts` (5 mnt) berjalan tepat waktu.

## 3. Integritas data — DITEMUKAN 2 MASALAH, SUDAH DIPERBAIKI

### 3a. Posisi ghaib: satu sinyal dibuka berkali-kali (BUG NYATA)
Timeline event membuktikan, 07 Okt 01:19–01:30 UTC:
```
01:19:40 AAVE opened → 01:20:12 closed (32 dtk)  ← entry basi 3 jam, langsung SL
01:23:04 AAVE opened → 01:23:44 closed (40 dtk)
01:26:23 AAVE opened → 01:26:55 closed (32 dtk)
01:29:42 AAVE opened → 01:30:13 closed (31 dtk)
```
**Penyebab:** `paper-scan` berjalan tiap 3,5 menit dan membuka posisi baru setiap kali
selama sinyal masih `allowed` dalam jendela 6 jam. Dedup yang ada hanya mencegah
duplikat DALAM SATU pemindaian — tidak melihat posisi yang sudah ada. AAVE punya 7
sinyal `allowed` berulang (3× dalam 1,5 jam pada 5 Okt).

**Perbaikan:** `_pair_sudah_dipakai()` — satu pair = satu posisi, plus jeda 12 jam
setelah posisi ditutup. Terverifikasi: dari 6 kandidat yang dulu akan dibuka berulang,
**6/6 sekarang dilewati**.

**Koreksi data:** 6 baris duplikat diarsipkan (bukan dihapus) ke
`crypto_equity_koreksi.jsonl`. Dampak: **−1,156R → +0,844R** (ledger 17 → 11 baris).

### 3b. Posisi menggantung (kemarin, sudah diperbaiki)
OP/LIT "still_open" padahal SL → `rekonsiliasi.py` + job `rekonsiliasi-crypto` (jam-an).

## 4. Angka setelah koreksi — konsisten

| Market | PnL dompet Rp 10 jt | Trade |
|---|---|---|
| Crypto | **+0,844%** | 11 |
| Polymarket (arm B) | +2,631% | 179 |
| Forex | −1,000% | 4 |
| GMGN/LP | −3,166% | 22 |
| IDX | −112,102% | 278 |

Ledger crypto: tidak ada lagi pair dengan >1 baris eksekusi berulang (LINK_USDT 2 baris
itu SAH — dua setup berbeda: TP2 22 Sep & close manual 26 Sep).

## 5. UI & tes — SEHAT

- **Rute API: 10/10 return 200** (5 area + sinyal/per-pasar, pasar/ringkas, freshness, docs, health).
- **E2E: 19/19 hijau** (perbaikan UX, 5 market, langkah IDX, Home).
- **pytest: 100% hijau, 0 gagal.** ruff bersih. lint token bersih (52 berkas).

## 6. Tindakan lanjutan yang tersisa

1. **IDX −112%** — ARA_HUNTER (−139%, 198 trade) menghabiskan dompet; BSJP positif.
   Keputusan pemilik: matikan ARA_HUNTER atau kecilkan risikonya per trade.
2. **350 sinyal IDX CREATED** tidak akan tertutup selama mesin Tencent beku — ditampilkan
   apa adanya dengan umur ("nyangkut").
3. **Forex sampel 4 trade** — INSUFFICIENT. Jangan dijadikan dasar keputusan besar.
