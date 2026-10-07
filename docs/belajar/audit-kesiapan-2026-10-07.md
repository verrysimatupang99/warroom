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

### 3c. GMGN/LP: 22 mark dihitung sebagai 22 posisi (BUG, diperbaiki)
`lp_ledger.jsonl` adalah ledger **mark** — satu baris per penilaian. Satu posisi UBI
menghasilkan 22 baris (harga naik-turun). Dompet menjumlahkan semuanya:
- modal terhitung **$660** (22 × $30) padahal nyata **$30**;
- PnL = jumlah mark dari waktu berbeda → angka tak bermakna.

Perbaikan: kelompokkan per posisi (symbol+harga_masuk+notional), ambil **mark terakhir**
sebagai nilai sekarang. Hasil: 1 posisi, PnL −3,512% (dari mark terakhir), dan UI
menampilkan "1 posisi · 22 baris mark (dinilai berkala)" supaya tidak membingungkan.
Catatan teknis: `ts` di ledger itu epoch (float) — membandingkan sebagai string bisa
memilih mark yang salah ("999" > "1000"); sekarang dibandingkan sebagai angka.

### 3d. EURUSD ganda-menit di jurnal Tencent (BUKAN bug kita)
Dua baris EURUSD 2026-09-23T17:00 = dua ZONA berbeda (bearish FVG & bullish iFVG) yang
dipantau bersamaan, keduanya CANCELLED. Sumbernya di Tencent (kita baca-saja) → dicatat,
tidak diubah.

## 4. Angka setelah koreksi — konsisten

| Market | PnL dompet Rp 10 jt | Trade |
|---|---|---|
| Crypto | **+1,844%** | 12 |
| Polymarket (arm B) | +2,631% | 179 |
| Forex | −1,000% | 4 |
| GMGN/LP | −3,512% (1 posisi, mark terakhir) | 1 |
| IDX | −112,102% | 278 |

Ledger crypto: tidak ada lagi pair dengan >1 baris eksekusi berulang (LINK_USDT 2 baris
itu SAH — dua setup berbeda: TP2 22 Sep & close manual 26 Sep).

## 5. UI & tes — SEHAT

- **Rute API: 10/10 return 200** (5 area + sinyal/per-pasar, pasar/ringkas, freshness, docs, health).
- **E2E: 19/19 hijau** (perbaikan UX, 5 market, langkah IDX, Home).
- **pytest: 100% hijau, 0 gagal.** ruff bersih. lint token bersih (52 berkas).

### 3e. Kandidat aktif tidak pernah sampai UI (BUG, diperbaiki)
`AREA_KEYS["crypto"]` memuat "signal" sejak awal — dan komentarnya sendiri mengakui
"kind `signal` bukan bagian snapshot" — tetapi kind itu tidak pernah didaftarkan di
`AREA_EXTRA`, yang hanya menerima pasangan (kind, key) TETAP. Kandidat punya kunci per
pair (`signal/AAVEUSDT`, …). Hasil: job `signal-sync` menerbitkan fakta tiap siklus,
API tidak pernah menyajikannya, dashboard tidak pernah menampilkan kandidat yang hidup.

Perbaikan: `AREA_KIND` (kind yang seluruh faktanya milik satu area) + hanya fakta yang
TTL-nya belum lewat + panel "Kandidat Aktif (ledger gate)" di Cockpit/Setup.

Bug ikutan: harga mikro (1000PEPE 0,0041) dibulatkan jadi "0,00" oleh format 2-desimal.
Sekarang adaptif (2/4/8 desimal).

### 3f. Freshness berbunyi untuk jadwal NORMAL (32 alert palsu, diperbaiki)
Fakta snapshot TTL 600 s dengan penulis tiap 15 menit **selalu** melewati TTL sesaat
sebelum penulisan berikutnya — karena penulis hanya boleh lebih lambat dari TTL. Maka
alert "data basi 13,3 mnt > ttl 600 s" muncul untuk SEMUA kunci sekaligus: derau.

Perbaikan: grace = max(1,5× TTL, TTL + 15 mnt). Jadwal normal diam; penulis yang
benar-benar mati (3 jam dengan TTL 30 mnt) tetap nyaring. Bonus: grace langsung
menemukan kandidat yang benar-benar basi (ENA 45 jam, OP 37 jam, SEI 27 jam, …) —
sekarang otomatis tidak disajikan ke UI.

### 3g. Tabel alerts tidak pernah dibersihkan (diperbaiki)
Retensi menyentuh `facts`/`events`/`llm_calls`, tapi tidak `alerts` → 100 alert
menumpuk (75 belum di-ack sejak 2 Okt). Aturan baru: yang SUDAH di-ack & tua dibuang;
yang BELUM di-ack **tidak pernah** (itu pekerjaan manusia, bukan retensi).
74 alert lama dibereskan berjejak; sisa 1 warning sah (lp_mark basi 2 jam).

## 6. Tindakan lanjutan yang tersisa

1. **IDX −112%** — ARA_HUNTER (−139%, 198 trade) menghabiskan dompet; BSJP positif.
   Keputusan pemilik: matikan ARA_HUNTER atau kecilkan risikonya per trade.
2. **350 sinyal IDX CREATED** tidak akan tertutup selama mesin Tencent beku — ditampilkan
   apa adanya dengan umur ("nyangkut").
3. **Forex sampel 4 trade** — INSUFFICIENT. Jangan dijadikan dasar keputusan besar.
