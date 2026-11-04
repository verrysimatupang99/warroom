# Uji Sistem Grid + Averaging pada XAUUSD

Tanggal: 24 Okt 2026 | Data: 13.435 candle M5 (60 hari) | Commit: `uji_grid.py`

---

## 1. Yang disimulasikan

Versi **paling jinak** dari grid+avg:

| Parameter | Nilai |
|---|---|
| Arah | LONG saja (gaya spot: beli saat turun) |
| Lot per level | **0,01 tetap** — tidak ada eskalasi martingale |
| Jarak antar level | 0,5 × ATR |
| Maks level | 8 |
| TP per posisi | +0,5 × ATR dari entry masing-masing |
| Modal awal | $500 |

Poin penting: **ini bukan martingale.** Lot tidak berlipat saat rugi. Kalau versi
paling jinak ini saja gagal, versi dengan lot berlipat jauh lebih buruk.

---

## 2. Hasil

| Skenario | Ekuitas akhir | Return | Max DD | Stop paksa | Bangkrut |
|---|---|---|---|---|---|
| Tanpa hard stop | −$11,79 | **−102,4%** | 100% | 0 | **31 Agu** |
| Hard stop 10% | −$1,28 | **−100,3%** | 100% | 200 | **23 Sep** |
| Hard stop 5% | −$8,84 | **−101,8%** | 100% | 385 | **21 Sep** |
| Hard stop 2% | −$8,44 | **−101,7%** | 100% | 756 | **28 Sep** |

**Semua skenario menghabiskan akun dalam 60 hari.**

Hard stop hanya **menunda** kebangkrutan (31 Agu → 21–28 Sep), tidak mencegahnya.
Setelah stop-out, grid dibuka lagi dan kalah lagi — 200 sampai 756 kali.

---

## 3. Kenapa gagal

Gold bergerak **3.989 → 4.211 → turun lagi** dalam periode uji. Grid long-only
membeli setiap penurunan, menumpuk 8 level, lalu harga terus turun.

Matematika sederhananya:
- 8 level × 0,01 lot = 0,08 lot = 8 oz
- Setiap $1 turun = −$8 floating
- Drawdown $50 (10% dari $500) tercapai saat harga turun **$6,25** dari level teratas
- Dengan ATR M5 ≈ $2,45, itu hanya **2,5 ATR** — beberapa jam saja

Sementara TP tiap posisi hanya 0,5 ATR (~$1,2). Jadi risikonya **~5× lebih besar
daripada reward**, dan itu baru dihitung dari satu level.

---

## 4. Batasan simulasi (jujur)

| Aspek | Status |
|---|---|
| Biaya swap/komisi | ❌ tidak dihitung (hasil nyata akan **lebih buruk**) |
| Slippage | ❌ tidak dihitung (lebih buruk) |
| Filter rezim (hanya sideways) | ❌ belum diuji |
| Arah dua sisi | ❌ hanya LONG |
| Eskalasi lot | ❌ tidak (versi jinak) |

Artinya: angka di atas adalah **batas atas** — versi terbaik yang mungkin dari
konfigurasi ini. Kenyataannya lebih buruk.

---

## 5. Yang belum diuji: versi dengan filter rezim

Steel-man yang adil untuk grid adalah **hanya jalankan grid saat pasar sideways**.
Itu belum saya uji. Kalau mau dilanjutkan, itu satu-satunya varian yang punya
alasan teoretis untuk bertahan.

Tapi perhatikan: klaim pemasaran "avg+grid" hampir selalu **tidak** menyebut filter
rezim, dan screenshot 10 jam mereka justru diambil dari jendela sideways — persis
kondisi di mana grid terlihat sempurna.

---

## 6. Kesimpulan

Pada XAUUSD dengan data 60 hari:

- Grid + averaging **tanpa filter rezim** = akun habis, dengan atau tanpa hard stop
- Hard stop memperlambat, tidak menyelamatkan
- Versi yang diuji sudah versi paling konservatif (lot tetap, bukan martingale)

**Rekomendasi:** jangan jalankan di akun nyata. Kalau tetap ingin dieksplorasi,
urutannya: (1) uji dengan filter rezim, (2) kalau lolos, uji dengan biaya
swap+komisi, (3) baru pertimbangkan akun demo terpisah.

Cara menjalankan ulang:
```bash
cd ~/warroom &&.venv/bin/python ops/uji_grid.py 60d
```
