# Riset: Dashboard Live Market Tencent — apa yang ditampilkan, sumbernya, dan perbandingan dengan War Room

Tanggal: 14 Okt 2026.
Sumber bukti (staged captures, TIDAK diubah):
`/tmp/tencent_markets.html` · `/tmp/tencent_mp.json` · `/tmp/tencent_xau.json`.
Pembanding kode: `packages/live-trading/src/live_trading/dashboard/` dan
`services/api/src/warroom_api/`.

Kesimpulan singkat: dashboard Tencent adalah **shell "satu pintu, tiga market"** yang
memuat tiga dashboard terpisah via `<iframe>` + **badge notifikasi** di tab. Isinya adalah
**jurnal sinyal/posisi paper ala trading-desk** (entry/SL/TP1/TP2/R-multiple per baris),
bukan sistem keputusan. War Room **lebih dalam di kebenaran angka & keselamatan eksekusi**,
tetapi **kalah di kecepatan baca lapangan** (terminal harga, badge posisi terbuka, pindah
market 1 tombol). Yang warroom sudah punya: **mirror Tencent IDX 616** lewat
`collectors/idx616.py` (baca-saja). Yang layak dipinjam: pola shell/badge/tab (UX), bukan
kode.

---

## 1. Apa yang ditampilkan dashboard live market Tencent

### 1.1 Kerangka: "Trading Command Center — Forex · Crypto · IDX"

`/tmp/tencent_markets.html` bukan dashboard itu sendiri, melainkan **shell pemilih market**.

- Judul: `🎛️ Trading Command Center — Forex · Crypto · IDX`
  (`tencent_markets.html:6`).
- Brand + subjudul: `satu pintu, tiga market — pisah lewat tombol`
  (`tencent_markets.html:45`).
- Tiga tab, tiap tab adalah **nama market + deskripsi sumber**, plus slot badge:
  ```html
  <button class="tab" data-market="forex"  data-src="/xau/index.html">📈 Forex <span style="opacity:.7">XAU · NAS · EUR</span><span class="pill" id="badge-forex"></span></button>
  <button class="tab" data-market="crypto" data-src="/crypto/index.html">₿ Crypto <span style="opacity:.7">perp · MEXC</span><span class="pill" id="badge-crypto"></span></button>
  <button class="tab" data-market="idx"    data-src="/idx616/">🇮🇩 IDX <span style="opacity:.7">saham</span></button>
  ```
  (`tencent_markets.html:47-49`)
- Market aktif dimuat di sebuah `<iframe id="frame">` (`:54`, `:67-68`), jadi **satu tab =
  satu dashboard penuh**, bukan grid semua market.
- Navigasi: klik tab, tombol `1`/`2`/`3`, dan `ArrowLeft/ArrowRight` untuk ganti market
  (`:126-136`).
- Persistensi pilihan terakhir di `localStorage('cc_market')` (`:72`, `:141`); query `?m=`
  menang atas localStorage (`:138-143`).
- Baris hint bawah: `Satu-satunya pintu masuk — buka dashboard terpisah akan dilempar balik
  ke sini · pilihan market tersimpan otomatis · tombol 1 / 2 / 3 & panah kiri-kanan`
  (`:55`).
- Meta kanan header: `Aktif: <label> · HH:MM` diperbarui tiap detik (`:145-149`).

### 1.2 Badge notifikasi lintas-market (bagian paling "hidup")

Shell secara berkala (tiap **90 detik**, `:124`) menarik endpoint tiap market untuk menghitung
badge:

- **Forex** (`:94-109`) — `GET /xau/api/trades` → jumlah `open` (posisi terbuka) sebagai
  angka badge; lalu `GET /xau/api/scanlog`, dan badge diberi tanda **"hot"** (pulse) bila
  ada pair yang `last.status` ∈ `{SIGNAL, WATCH}` dan umurnya ≤ `NEW_SIGNAL_MIN = 90` menit
  (`:76`, `:102-104`).
- **Crypto** (`:110-121`) — `GET /crypto/api/summary` → jumlah posisi MEXC (`s.mexc.positions`
  atau `s.stats.open`); lalu `GET /crypto/api/scanlog` → `counts.kandidat` (koin kandidat)
  yang membuat badge "warn"/hot. **Klik badge = pindah tab**, karena badge ada di dalam
  `<button class="tab">`.
- **IDX** tidak punya badge — tab IDX hanya teks (`:49`).

CSS badge mendukung dua keadaan: `.pill.hot` (kuning, `animation:pulse`) dan `.pill.warn`
(merah) (`:29-34`). Artinya konsep "ada yang baru & perlu dilihat" itu eksplisit: **jumlah
posisi + penanda sinyal baru**.

### 1.3 Isi dashboard per-market (dari dua capture JSON)

**A. Forex (tab `forex` → `/xau/index.html`) — capture `/tmp/tencent_xau.json`**

Bentuk: objek `{ "trades": [...], "meta": {...} }` (`tencent_xau.json:1`, `:227`).
Satu baris trade memuat field sinyal trading yang lengkap
(`tencent_xau.json:3-32` contoh pertama):

- `id`, `created_utc`, `date_wib` (jam WIB),
- `side` (`BUY`/`SELL`), `entry`, `sl`, `tp1`, `tp2`, `be`,
- `price_at_signal`, `risk_points`, `rr_tp1`, `rr_tp2`,
- `bias` (narasi HTF, mis. `"Bullish OB bounce, signal 22 Sep 17:00"`),
- `poi` (Point of Interest — zona presisi, mis. `"Bullish OB 1H 4338.6-4345.24 overlap EQL 4339.45 ..."`),
- `session` (`london`, `Asia`…), `style` (`intraday`, `intraday SMC`),
- `status` (`CLOSED`), `filled_utc`, `resolved_utc`, `outcome` (`SL`/`TP2`/`NO FILL`/`CANCELLED`),
- `r_multiple`, `max_favorable_r`, `be_armed`,
- `notes[]` (jurnal manusiawi, mis. `"TP1 hit 09-25 15:45 WIB — partial 50% close (++0.50R), sisa jalan ke TP2"`),
- `tp1_hit`, `confirmed_by_user`, `filled_wib`.

`meta` (`tencent_xau.json:227-236`) menyimpan:
```json
"meta": { "created": "2026-09-21T12:10:00+07:00",
  "note": "Strategy reset v2 (21 Sep 2026). Rule: gate 5/6, BE trigger 1.2R, TP1 partial 50%, sesi 13:00-19:30 WIB. ...",
  "previous_stats": { "signals": 9, "win_rate_pct": 20, "total_r": 0.32, "buy_record": "0W/4L" } }
```
Kuncinya: dashboard Forex **menampilkan riwayat sinyal + hasil nyata (R) + statistik lama**
— bukan sekadar harga.

**B. Crypto (tab `crypto` → `/crypto/index.html`) — capture `/tmp/tencent_mp.json`**

Bentuk: **array sinyal** (bukan wrapper objek). Tiap entri = satu setup
(`tencent_mp.json:2-21` contoh):

- `pair` (`EURUSD`, `NAS100`), `date_wib`, `side`, `entry`, `sl`, `tp1`, `tp2`,
- `risk_points`, `zone_kind` (`bearish FVG`, `bullish iFVG`, `bearish OB`, `SR support`,
  `flipped bearish OB`), `zone_tf` (`1H`), `zone_low`, `zone_high`,
- `confluence` (jumlah konfluensi),
- `status` (`CANCELLED`/`CLOSED`), `outcome` (`INVALID`/`SL`/`TP1`/`CANCELLED`),
- `order_type` (`LIMIT`), `r_multiple`, `exit_price_est`, `exit_note`,
- `market_result` — objek hasil feed pasar dengan `state` (`TP1`/`SL`), `log[]`
  (mis. `["terisi 30601.8 (23:00 WIB)","TP1 30478.1 (02:45 WIB)"]`), `checked_wib`
  (`tencent_mp.json:224-231`),
- `notes[]` — jurnal manusiawi, mis. `"User SKIP (1 Oct 07:0x WIB) — sinyal 30 Sep 23:00
  WIB kelewat (di luar jam aktif user). Feed: fill 30601.8 → TP1 30478.1 kena 02:45 WIB →
  profit tidak terambil. NO TRADE."` (`tencent_mp.json:232-234`).

Catatan penting: entri ini memuat **konsep "no-trade/verdict"** dan **alasan pembatalan**
(mis. `"Dua signal berlawanan sekaligus = straddle, dibuang via 1-setup-per-pair rule."`
`tencent_mp.json:19`). Jadi tab crypto bukan order book, tapi **log keputusan setup**.

### 1.4 Ciri desain dashboard Tencent (yang membedakannya)

1. **Multi-market dengan isolasi via iframe** — tiap market punya app sendiri (`/xau/`,
   `/crypto/`, `/idx616/`), shell hanya "menempelkan" dan memberi badge.
2. **Badge notifikasi adalah warga kelas satu** — posisi terbuka + sinyal baru < 90 menit,
   auto-refresh 90 dtk, klik = lompat ke market itu.
3. **Bahasa manusia & jurnal** — hampir tiap baris punya `notes[]` naratif ("kenapa
   dibatalkan", "user skip", "TP1 hit").
4. **Fokus trading-desk, bukan keputusan** — menampilkan entry/SL/TP/R dan hasil, **tanpa
   gate signifikansi statistik, tanpa label bukti/promosi**.

---

## 2. Sumber data dashboard Tencent

Dari capture + jejak endpoint di shell, sumber datanya adalah **API internal tiap app**:

| Market | Endpoint yang dibaca | Bentuk data |
|---|---|---|
| Forex | `/xau/api/trades` dan `/xau/api/scanlog` (`tencent_markets.html:95,99`) | daftar trade + status scan pair (SIGNAL/WATCH) |
| Crypto | `/crypto/api/summary` dan `/crypto/api/scanlog` (`tencent_markets.html:112,117`) | ringkas posisi MEXC + `counts.kandidat` |
| IDX | `/idx616/` (`tencent_markets.html:49`) | dashboard IDX 616 |

Capture JSON memperlihatkan **skema sumber** persis:

- `/tmp/tencent_xau.json` = respons bergaya `/xau/api/trades` (`{trades[], meta}`) — data
  berasal dari **feed harga + eksekusi paper manual** yang dicatat user (mis. `filled_utc`,
  `outcome`, `r_multiple` dihitung dari feed pasca-sinyal). Ini **bukan** feed exchange
  langsung: harga masuk lewat verifikasi feed (lihat `exit_note` `tencent_mp.json:111`
  "Verifikasi feed: peak NAS100 sejak fill = 30714.6 ... beda 4 pt (offset feed)").
- `/tmp/tencent_mp.json` = respons bergaya `/crypto/api/scanlog` — daftar sinyal/setup
  per pair, dihasilkan mesin scan (zona SMC: FVG/OB/iFVG/SR) dan diberi verdict.

**Host IDX 616 Tencent (terkonfirmasi dari kode warroom):**
`packages/live-trading/src/live_trading/collectors/idx616.py` menargetkan
`BASE = "http://43.155.219.37/idx616/api"` dan menarik `GET /events` (sinyal terstruktur:
CREATED/CLOSED, `net_r`) serta `GET /journal` (hasil), menyimpannya ke
`state/idx616_mirror.json` dengan `TTL_S = 900`. Jadi **IDX 616 adalah sumber Tencent yang
sama** yang sudah di-mirror warroom — dashboard warroom menampilkannya di kartu `idx616`
(`page_parts.py:1242-1315`).

Kesimpulan sumber: Tencent = **app mandiri per market**, tiap app membuka **API JSON
internal sendiri** (trades/scanlog/summary), disatukan oleh shell iframe. Tidak ada
PostgreSQL/`facts` kanonik, tidak ada TTL-freshness terpusat — kesegaran hanya lewat badge
"< 90 menit" di sisi klien.

---

## 3. Perbandingan: War Room vs dashboard Tencent

### 3.1 Arsitektur server & penyajian

War Room (`dashboard/server.py`) memakai **`http.server`** + shell HTML sendiri, dengan
`<meta http-equiv="refresh" content="60">` (`server.py:34`). `render()` merakit
`_SHELL.format(css=_css(), header=_kepala(snap, page), body=_rakit(snap, page))`
(`server.py:28-29`). Sisi lain: ada **API FastAPI** (`services/api/src/warroom_api/`) yang
menyajikan `/api/v1/*` dengan auth, RBAC, rate-limit, dan SSE.

Perbandingan singkat:

| Aspek | Tencent (capture) | War Room (kode) |
|---|---|---|
| Model multi-market | Shell iframe + tabel per app | 5 rute halaman: `/`, `/terminal`, `/uang`, `/bukti`, `/pasar`, `/proyek` (`page_parts.py:1353-1360`; `server.py:134-141`) |
| Auto-refresh | Badge 90 dtk (`tencent_markets.html:124`) | Halaman 60 dtk (`server.py:34`); snapshot dibangun ulang **15 menit** (`page_parts.py:1368-1369`) |
| Navigasi cepat market | Tombol 1/2/3 + panah (`:129-136`) | Nav link statis (`_nav`, `page_parts.py:522-535`) — **tidak ada hotkey** |
| Badge lintas-market | Ada, angka posisi + "hot" sinyal (`:84-90`) | Hanya badge status teks per halaman (`_status_halaman`, `page_parts.py:649-667`) |
| Terminal harga live | (di app per market, di luar capture) | Ada: `/terminal` dengan klines Binance + tape 24h, canvas, EMA20, overlay zona paper (`_TERMINAL`, `page_parts.py:83-249`) |
| Sumber angka | API internal per app (JSON) | Snapshot dari berkas state + kolektor + tabel `facts` (ADR-005, `app.py:6-7`) |
| Jurnal naratif | Kaya, `notes[]` per baris trade | Ada `_arti(...)` penjelasan per kartu (mis. `page_parts.py:739`) |
| Stream waktu-nyata | polling badge | SSE `/api/v1/stream` topic-filter (`app.py:100-112`; `stream.py`) |

### 3.2 Kekuatan yang sudah dimiliki War Room (di mana Tencent lebih lemah)

1. **Gate & bukti statistik.** Tencent tidak punya gate; War Room punya
   `POST /api/v1/gate/evaluate` dengan Wilson CI, `deff`, `pakem`, `n_efektif`
   (`routers/pasar.py:66-137`) dan kartu Backtest (`page_parts.py:1112-1184`).
2. **Verdict kanonik terpusat.** `GET /api/v1/verdict` mengeluarkan verdict per pasar agar
   UI tidak menyusun verdict sendiri (`routers/pasar.py:170-190`). Tencent: verdict
   tersebar di `notes[]` tiap baris.
3. **Keselamatan eksekusi.** Arming live 3-sumber + heartbeat (`live.py:90-173`), grant
   ber-scope (`live.py:176-246`), dry-run allowlist (`SUBPERINTAH_DRY_RUN_DIIZINKAN =
   frozenset({"depth"})`, `live.py:255`). Tencent: tidak ada konsep armed/live.
4. **Observability & freshness.** `/api/v1/freshness` (umur fakta vs TTL,
   `routers/sistem.py:174-206`), `/metrics` Prometheus (`metrics.py:184-236`), readiness
   (`metrics.py:36-106`). Tencent: kesegaran hanya badge klien.
5. **Stream per-topik.** `TOPICS` (`stream.py:23-32`) memfilter `signals/verdicts/trades/...`
   di SQL — lebih kaya dari polling `/api/scanlog`.
6. **Antarmuka terminal candlestick.** `_TERMINAL` menggambar 120 candle + volume + EMA20 +
   overlay entry/SL/TP/zona paper (`page_parts.py:158-235`). Capture Tencent **tidak**
   memperlihatkan chart seperti ini.

### 3.3 Di mana Tencent lebih unggul (celah War Room)

1. **Satu pintu, pindah market instan.** Tencent punya satu shell + hotkey 1/2/3 + panah
   (`tencent_markets.html:129-136`). War Room punya 6 rute, tapi perpindahan via klik nav;
   mengawasi kripto+IDX+forex bergantian lebih lambat.
2. **Badge notifikasi portofolio.** Tencent menunjukkan **jumlah posisi terbuka** dan
   **penanda "sinyal baru < 90 mnt"** yang menarik perhatian tanpa membuka tab. War Room
   hanya punya badge status (mis. "WAR ROOM", "KONTEKS: BUKAN PERINTAH") yang tidak
   menunjukkan "ada X posisi / ada sinyal baru".
3. **Jurnal naratif per baris.** `notes[]` di kedua JSON adalah narasi keputusan ("kenapa
   dibatalkan", "user skip", "straddle dibuang"). War Room punya `_arti()` di level kartu,
   tapi baris trade individual tidak membawa catatan keputusan sepanjang itu.
4. **Skema trade seragam & bisa dibandingkan.** Baris Tencent konsisten
   (entry/sl/tp1/tp2/be/risk_points/rr_tp1/rr_tp2/outcome/r_multiple/max_favorable_r).
   War Room punya `ledger`/`posisi` tapi field tidak sekaya itu per baris (lihat
   `page_parts.py:793-800` untuk `posisi`).

---

## 4. Peluang peningkatan konkret untuk dashboard War Room

Aturan pengikat (ikut `openstock-2026-10-14.md`): **pinjam pola, jangan salin kode**;
angka tetap dari `facts`/snapshot, ketiadaan data = `n/a`/`—`, bukan `0`.

1. **Shell "satu pintu" + hotkey market di atas navigasi yang ada.**
   Tambah di `_nav` (`page_parts.py:522-535`) handler hotkey (`1`=terminal/kripto,
   `2`=pasar, `3`=proyek…) meniru `tencent_markets.html:129-136`, dan simpan halaman
   terakhir di `localStorage` (pola `:72`). Biaya kecil, manfaat besar untuk operasi
   multi-market. Bisa berupa fragmen kecil yang disuntik ke `_SHELL` (`server.py:32-37`).

2. **Badge posisi + "sinyal baru" pada tiap nav.**
   Bikin endpoint ringan (sudah ada bahan: `snap["posisi"]` di `panels.py:577-581`,
   `snap["crypto_sinyal"]/["forex_sinyal"]/["idx_sinyal"]` di `panels.py:666-668`) yang
   mengembalikan `{open_positions, fresh_signals}` per area, lalu render `<span class='pill'>`
   di nav — persis pola `setBadge`/`NEW_SIGNAL_MIN` (`tencent_markets.html:84-90`, `:76`).
   Implementasi paling bersih: fragmen `/frag/<nama>` yang sudah ada (`server.py:93-111`).

3. **Jurnal napas-manusia per baris trade di kartu Posisi/Ledger.**
   Tambah kolom/expand `notes` pada tabel `posisi` (`page_parts.py:791-808`) dan
   `ledger` (`page_parts.py:811-844`) — sumbernya sudah ada di
   `state/paper_positions.json`/ledger dan di `paper_positions.json` (`panels.py:577-581`).
   Ini mengadopsi kekuatan `notes[]` Tencent tanpa mengubah mesin angka.

4. **Skema trade seragam & kaya untuk perbandingan antar-market.**
   Normalisasi baris posisi ke satu bentuk (`pair, side, entry, sl, tp1, tp2, be,
   risk_points, rr_tp1, rr_tp2, outcome, r_multiple, max_favorable_r`) seperti
   `tencent_xau.json:3-32`, agar kartu papan skor bisa memakai kolom yang sama. Simpan
   sebagai fungsi format di `format.py` (sudah ada `fharga`, `_persen`, `format.py:18-33`).

5. **Panel "Verdict / no-trade" ringkas per market (bukan hanya hasil).**
   Tencent menyimpan alasan pembatalan (`tencent_mp.json:19` "straddle, dibuang via
   1-setup-per-pair rule"). War Room sudah punya `verdict` kanonik
   (`routers/pasar.py:170-190`) dan `bandarmologi_skor`/`kandidat` — tampilkan **alasan
   blokir** dalam satu baris di kartu Pasar, selaras prinsip "UI tidak menyusun verdict
   sendiri" (`routers/pasar.py:173-177`).

6. **Perluas mirror Tencent IDX 616 menjadi pola resmi "sumber eksternal".**
   `collectors/idx616.py` sudah jadi contoh bagus: baca-saja, TTL 900 s, fallback ke
   cache + label `dari_cache` (`page_parts.py:1304-1308`). Karena capture Tencent
   menunjukkan app per-market dengan API sendiri, pola ini bisa digeneralisasi menjadi
   helper "external mirror" agar tidak ada penyalinan manual tiap market.

7. **Tape/ticker ringkas di header halaman Pasar.**
   `_TERMINAL` sudah punya tape 24h (`page_parts.py:119-133`). Angkat **tape ringkas**
   (harga + %chg) ke header halaman `/pasar` agar konteks cepat terlihat, meniru kecepatan
   baca badge Tencent tanpa membuka `/terminal`.

8. **Indikator kesegaran per-panel yang seragam (sudah hampir ada, dibuat konsisten).**
   Pola badge `segar/basi` sudah dipakai (radar: `page_parts.py:895-902`; poly:
   `:982-986`). Terapkan badge yang sama ke **setiap** kartu pasar (crypto/forex/idx/hl)
   memakai endpoint `/api/v1/freshness` (`routers/sistem.py:174-206`) supaya "segar vs
   basi" terbaca sekilas — keunggulan yang tak dimiliki Tencent, jangan hilang.

### Prioritas yang disarankan

| Prioritas | Item | Alasan |
|---|---|---|
| Tinggi | #1 shell+hotkey, #2 badge posisi/sinyal | Celah UX terbesar vs Tencent; bahan data sudah ada |
| Sedang | #3 jurnal per baris, #4 skema seragam | Menaikkan keterbacaan & perbandingan antar-market |
| Sedang | #5 panel verdict/no-trade | Menyempurnakan yang sudah jadi keunggulan War Room |
| Rendah | #6 generalisasi mirror, #7 tape header, #8 badge freshness konsisten | Perapian & konsistensi |

---

## Lampiran: rujukan kode yang dikutip

- Shell Tencent: `/tmp/tencent_markets.html:6,45,47-49,54,55,63-73,76,84-124,126-149`.
- Capture Forex (XAU): `/tmp/tencent_xau.json:1,3-32,227-236`.
- Capture Crypto/MP: `/tmp/tencent_mp.json:2-21,19,111,224-234`.
- War Room server: `dashboard/server.py:28-29,32-37,93-111,134-141,160-201`.
- War Room fragmen: `dashboard/page_parts.py:83-249` (terminal), `:522-535` (nav),
  `:649-667` (status halaman), `:791-844` (posisi/ledger), `:895-902,982-986` (badge segar/basi),
  `:1242-1315` (idx616), `:1353-1360` (rute).
- War Room panel data: `dashboard/panels.py:395-737` (build_snapshot), `:577-581` (posisi),
  `:666-668` (sinyal per pasar).
- War Room format & helper: `dashboard/format.py:18-40`, `dashboard/html_parts.py:15-34`.
- API: `services/api/src/warroom_api/app.py:6-7,55-126`; `routers/pasar.py:66-137,145-260`;
  `routers/live.py`; `live.py:90-173,176-246,255`; `stream.py:23-32,115-169`;
  `routers/sistem.py:174-206`; `metrics.py:36-106,184-236`.
- Mirror Tencent IDX: `packages/live-trading/src/live_trading/collectors/idx616.py`
  (`BASE="http://43.155.219.37/idx616/api"`, `/events`, `/journal`, `TTL_S=900`).
