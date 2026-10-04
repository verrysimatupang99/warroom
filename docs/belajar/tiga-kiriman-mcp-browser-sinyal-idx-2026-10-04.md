# Tiga kiriman: MCP browser, kanal sinyal memecoin, screener IDX — 4 Okt 2026

Sumber: tautan publik yang dikirim pemilik. Label: **[verified]** dicek langsung & bertanggal ·
**[reported]** pihak ketiga · **[assumed]** inferensi.

---

## 1. `rayss868/fastmcp-browser` — MCP server browser tanpa CDP **[verified]**

MCP server (TypeScript) + WebExtension MV3 yang mengendalikan **browser Anda yang sedang
berjalan** lewat WebExtensions API — **tanpa CDP, tanpa `chrome.debugger`, tanpa Playwright**.

| Aspek | Nilai |
|---|---|
| Alat | **32 MCP tools**, seluruh skema ≈ **10k token** |
| Jembatan | WebSocket loopback `127.0.0.1:9229`, token-auth |
| Latensi | median **0,37 ms**, p95 3,15 ms, 1.414 req/s (benchmark internal) |
| Uji | server 54/54, extension 90/90 |
| Lisensi | MIT |
| Pasang | ekstensi + ~0 dependensi; **0 biner browser** yang diunduh |

### Kenapa ini relevan buat kita

1. **Sesi nyata tanpa setup** — logins, 2FA, cookie, wallet, tab yang sudah terbuka. Persis kasus
   yang kita hadapi saat Threads/Instagram memblokir scraping (403 + "content isn't available"):
   browser sungguhan lolos, bukan karena menyamar, tapi karena memang sesi manusia.
2. **Multi-profil** — beberapa profil terhubung sekaligus (`browser_instances`), berguna kalau
   suatu saat perlu memisahkan akun riset dari akun utama.
3. **Tanpa CDP** — pengurangan jejak otomasi; **tapi jujur: ini bukan penyamaran.** Halaman tetap
   tahu ada otomasi. Klaim repo sendiri menyatakan itu apa adanya.
4. **Biaya konteks kecil** — 10k token untuk 32 alat, dibanding `@playwright/mcp` yang lebih besar.

### Batas yang dinyatakan repo itu sendiri **[verified]**

- **Tidak bisa membuka dialog file OS** (ekstensi memang tidak bisa) — unggah file dengan
  menyetel `input[type=file]` secara programatik, maks 25 MB/berkas.
- **Tidak bisa headless / tidak bisa meluncurkan browser** — hanya mengendalikan yang sudah jalan.
- `browser_network` hanya mengamati; **tidak bisa memblokir/mengubah** permintaan. Header
  `Authorization`/`Cookie`/`Set-Cookie` tidak diambil; buffer 200 permintaan/tab.
- Screenshot PNG raster (bukan vektor).

### Putusan

**Layak dicoba sebagai jalur cadangan**, bukan pengganti. Kita sudah punya `agent-browser` +
`botasaurus`; keunggulan uniknya adalah **memakai sesi login yang sudah ada tanpa menyalin profil**.
Reponya jujur soal keterbatasannya (mengakui Playwright menang untuk alur besar berskrip) — itu
tanda bagus. **Belum dipasang**; menunggu keputusan pemilik.

---

## 2. `t.me/awsnumsignal` — agregator sinyal memecoin **[verified]**

Pratinjau publik: **359 anggota, 61 online**.

> **AWSnum Signals** — "Sinyal memecoin dari empat sumber, satu tempat.
> 🌊 Pumpfun · 🪐 Jup · 🟢 Robinhood · 📈 Stonkfun
> Tiap bot punya topiknya sendiri. **Data mentah, bukan rekomendasi.**"

### Kenapa ini menarik

1. **Dua dari empat sumbernya persis rantai yang kita kerjakan**: `Robinhood` (LP probe kita sudah
   jalan di sana — 1.112 baris ledger) dan `Pumpfun` (memecoin Solana).
2. **Posisi "data mentah, bukan rekomendasi" itu jujur** — sama seperti label `LABEL_JUJUR` kita.
   Itu jarang; sebagian besar kanal sinyal mengabarkan seolah sudah terbukti.
3. **Topik per bot** = model distribusi yang sama dengan `signal-sync` yang baru kita bangun.

### Batasnya

- Isi pesan **tidak bisa dibaca** dari pratinjau web (kanal terkunci / perlu Telegram). Jadi
  **tidak ada klaim hasil yang bisa diuji** — dan itu justru lebih baik daripada kanal yang
  memasang tangkapan layar PnL.
- Track record: **tidak ada** yang bisa diverifikasi dari luar. Jangan diperlakukan sebagai bukti.

### Putusan

**Berguna sebagai daftar sumber, bukan sebagai sinyal.** Yang layak ditiru bukan sinyalnya, tapi
**formatnya**: satu tempat, beberapa sumber, topik terpisah, label "data mentah". Sumber-sumbernya
(Pumpfun/Jup/Robinhood/Stonkfun) adalah kandidat feed yang bisa kita sambungkan ke `signal-sync`.

---

## 3. `@ihsgscreener` — screener IDX "KRAKEN FLOW / ORCA" **[verified]**

Pratinjau publik profilnya (16,9K pengikut): sistem mencari emiten dari **Order Flow & Reversal**,
dengan parameter yang mereka sebutkan sendiri:

| Parameter (klaim mereka) | Bisa kita replikasi? | Dari mana |
|---|---|---|
| Top Volume | ✅ | TradingView scanner (`volume`) |
| Frequency | ✅ | Arjum `broker_summary` (`bfrq` + `sfrq`) |
| Foreign | ✅ | Arjum `broker_summary` (`flow`) |
| **High ATS** (Average Trade Size) | ✅ | **`Σbval ÷ Σbfrq`** — diturunkan, bukan field langsung |
| **No Sell** | ✅ | `sfrq ÷ bfrq` pada akumulator teratas (< 20%) |
| Close High | ✅ | TradingView (`close` vs rentang) |
| **High Bid/Offer** | ❌ | butuh **antrean order book** — tidak ada di Arjum maupun TradingView |
| **High Non-Regular** | ❌ | butuh **transaksi negosiasi/non-reguler** — tidak ada di keduanya |

**6 dari 8 bisa, 2 tidak.** Dan yang tidak itu justru yang paling sering mereka tonjolkan
("High Non-Regular → sering sinyal bandar").

### Yang dibangun: `collectors/bandarmologi.py`

| Fungsi | Guna |
|---|---|
| `ringkas_broker(payload)` | Dari satu `broker_summary` Arjum: ATS beli/jual, porsi frekuensi beli, net nilai, `no_sell`, akumulator & distributor teratas |
| `skor_heuristik(r)` | Skor 0–100 dengan **bobot transparan**: porsi frekuensi 40 · net beli 30 · ATS beli > jual 20 · no_sell 10 |
| `skrining(kode, state_dir, maks_ticker, ambil)` | Ambil → ukur → urutkan. **Cache 6 jam** + batas ticker keras |

**Disiplin kuota:** Arjum 6000 panggilan/hari untuk **seluruh** pemakaian. Satu siklus = 1
(screener) + 4 (ticker) = 5 panggilan, di-cache 6 jam → **±20 panggilan/hari**. Cache-nya bukan
optimasi, itu bagian dari disiplin kuota.

### Bug yang ketemu saat menulis tesnya

**Broker dengan nilai rusak tetap menyumbang frekuensinya** → penyebut ATS membengkak → ATS
terlalu rendah, **tanpa error apa pun**. Diperbaiki dengan `_total_berpasangan()`: hanya broker
yang **nilai dan frekuensinya sama-sama terbaca** yang ikut dihitung. Dikunci tes.

### Keluaran nyata (4 Okt, dari job snapshot — bukan manual)

```
WOOD  skor 89,2 | ATS beli Rp2.391.071 vs jual Rp1.520.566 | net +1.639,1 jt | no_sell True
      akumulator: CC MANDIRI SEKURITAS +0,30 M
DSSA  skor 86,6 | ATS beli Rp15.287.124 vs jual Rp10.353.603 | net +105.778,3 jt | no_sell True
      akumulator: SS SUPRA SEKURITAS INDONESIA +44,28 M
ARCI  skor 77,9 | net +11.176,6 jt | no_sell False
SAPX  skor 72,3 | net +650,9 jt | no_sell False
```

Halaman baru **`/bandar`** + nav `🜲 Bandarmologi`, plus `bandarmologi` masuk kunci area IDX.

### Aturan kejujuran yang dipegang

> **Skor ini heuristik.** Mereplikasi **cara mengukur** bukan bukti bahwa strateginya
> menguntungkan. Tidak ada label "win rate" atau "akurasi" di halaman ini — dan itu ditulis di
> setiap keluaran.

---

## Verifikasi

| Uji | Hasil |
|---|---|
| Suite | **524 lulus** · ruff **All checks passed** |
| Snapshot dari **job** | ✅ **11 bagian** — `bandarmologi` masuk |
| Fakta di DB | ✅ `...,macro,...,bandarmologi,overextended` |
| Halaman | ✅ `/` `/bandar` `/lp` `/overextended` `/bukti` `/idx` semua **200** |
| Layanan | 4 active · publik 200 · api 401 · **0 unit failed** |
| Kuota Arjum | 5.948 / 6.000 sisa setelah pengujian |

## Langkah berikutnya

1. **Uji apakah skor broker-flow benar-benar berguna** — jalankan ke riwayat (bukan hanya hari ini)
   dan bandingkan dengan hasil forward. Tanpa itu, skor tetap heuristik.
2. **Sambungkan sumber AWSnumSignal** (Pumpfun/Jup/Robinhood/Stonkfun) ke `signal-sync` sebagai
   feed tambahan — dengan label yang sama.
3. **Putuskan `fastmcp-browser`** — pasang atau tidak; belum diubah apa pun.
