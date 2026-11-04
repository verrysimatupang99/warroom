# Review: Planetx Trading Journal (Notion) — relevansi untuk crypto

Sumber: https://app.notion.com/p/Planetx-Trading-Journal-e4fcf2e7353f8341a0ca81e797061a3e
Diakses: 24 Okt 2026, via browser (sesi tanpa login).

## Status akses
| Bagian | Bisa dibaca? |
|---|---|
| Struktur utama (My Trades, Review, Resource Library, Education, Quick Actions) | ya |
| Education — daftar isi (10 topik) | ya, **isi per bagian TIDAK** (preview saja) |
| Pre-Trade Checklist | hanya **STEP 1** (macro/BTC context) |
| **Database My Trades** | **ya — 15 baris pertama terbaca** |
| Review / Resource Library | belum diperiksa |

Halaman memakai gerbang "sign up to start building" sehingga isi panjang terpotong.
Untuk materi Education lengkap perlu login (Notion connector) atau ekspor dari pemilik.

## Struktur journal (19 kolom) — ini bagian paling berguna
```
Name, Date, Pairs, Session, Direction, Profit/Loss, Followed rules, BE,
Entry Window (New York Time), Model, Positive tags, Negative tags,
Account, Rating(1-5), WIN, DOW, Month, Year, Place
```
Catatan: ada `Account` terpisah (contoh "disqi", "minra") -> journal mendukung
beberapa akun/trader dalam satu database.

## Ringkasan 15 trade yang terbaca
P/L total +498, 9 menang / 4 kalah (2 baris tanpa P/L).
**Satuan P/L tidak diketahui** (bisa poin, %, atau $) — jangan diasumsikan.

### Per model
| Model | n | Total P/L | Win |
|---|---|---|---|
| Model 1 | 8 | **+592** | **8/8** |
| Model 2 | 4 | **-62** | 1/4 |
| (kosong) | 1 | -32 | 0/1 |

### Per sesi
| Sesi | n | Total | Win |
|---|---|---|---|
| Asian | 4 | **+468** | 4/4 |
| London | 6 | +62 | 4/6 |
| New York | 2 | 0 | 1/2 |

### Per arah
| Arah | n | Total | Win |
|---|---|---|---|
| SHORT | 4 | +425 | 4/4 |
| LONG | 8 | +105 | 5/8 |

### Tag
- positif: `well-managed` 12, `perfect-entry` 7
- negatif: `early-exit` 6, `sl-placement` 1

**Peringatan sampel**: 15 baris, kemungkinan hanya halaman pertama, periode Jul-Sep 2026,
dan satuan P/L tidak diketahui. Angka di atas **tidak** cukup untuk klaim edge —
hanya menunjukkan bentuk data yang mereka pakai.

## Yang layak diadopsi untuk crypto di War Room

1. **Pemisahan per "Model"** (Model 1 vs Model 2) dengan statistik terpisah.
   Di War Room kita punya registry strategi, tetapi tidak menghitung P/L per strategi.
   Ini yang membuat mereka bisa melihat Model 2 merugi sementara Model 1 untung.
2. **Tag taksonomi tetap** — `perfect-entry`, `well-managed`, `early-exit`,
   `sl-placement`. Ini bisa otomatis: `early-exit` bila posisi ditutup jauh sebelum TP,
   `sl-placement` bila SL kena tepat di zona rawan, `well-managed` bila BE/trailing aktif.
3. **Entry Window per jam** (mis. `8-9am`, `1-2pm` New York). Murah ditambahkan
   (kita sudah punya timestamp) dan langsung memberi tahu jam mana yang merugi.
4. **Followed rules + BE** sebagai kolom boolean terpisah — bukan sekadar P/L.
   Mengukur kepatuhan proses, bukan hasil.
5. **Rating 1-5** untuk kualitas eksekusi, terpisah dari hasil.
6. **Multi-akun** dalam satu journal (kolom `Account`).

## Yang relevan untuk strategi crypto
Pre-Trade Checklist STEP 1 (satu-satunya yang terbaca) berisi urutan bias:
1. cek kalender macro (CPI/Fed) — tidak ada event besar dalam 30 menit
2. cek arah & struktur BTC (trend, key level)
3. tentukan risk-on / risk-off
4. cek BTC dominance (BTC.D)
5. pastikan likuiditas masuk/keluar crypto
6. bias harus selaras arah pasar

Ini **BTC-first, liquidity-driven** — pendekatan yang masuk akal untuk crypto dan
berbeda dari pendekatan kita di forex (yang berbasis sesi + ATR).

## Langkah lanjut yang disarankan
1. Hubungkan Notion (connector) supaya Education + Review + seluruh database terbaca.
2. Kalau tidak, minta pemilik mengekspor halaman ke Markdown/PDF lalu kirim.
3. Setelah isi lengkap terbaca, petakan kolom journal mereka ke skema kita
   (`data_forex_history.json` / tabel trade) dan tambahkan 4 kolom termurah dulu:
   `model`, `entry_window`, `tag_pos`, `tag_neg`.

## Berkas
- `~/wr_notes/planetx_trades_raw.json` — 15 baris mentah (12 kolom terlihat)
- `~/wr_notes/planetx_pretrade.txt` — teks checklist (hanya STEP 1)
