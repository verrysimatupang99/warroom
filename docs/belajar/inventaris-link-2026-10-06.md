# Inventaris link yang pernah dikirim + temuan baru — 6 Okt 2026

Pemilik mengirim ulang 26 tautan (Threads/Instagram/YouTube/GitHub/situs) tanpa instruksi.
Kebiasaan yang berlaku: **uji klaim terhadap data nyata, bangun yang berguna, jangan ringkas
mentah**. Dokumen ini mencatat mana yang **sudah pernah digarap**, mana yang **baru**, dan apa
yang layak dikerjakan. Tidak ada tautan yang diuji ulang dari nol kalau sudah ada dokumennya —
di situ cukup ditunjuk.

## 1. Inventaris — sudah pernah digarap

| Tautan | Topik | Di mana |
|---|---|---|
| `threads/_oL5NhMLJ` + 6 Threads & 2 Instagram lain (BAGSPAY-SOL DAMM v2 +122%) | Klaim LP Solana | `analisa-klaim-lp-solana-2026-10-04.md` — **+122,36% tidak reproducible** (angka asli +86,12%; 122% itu pertumbuhan kaki SOL, bukan posisi). Modal ~$6 = demo. |
| `github/omkarcloud/botasaurus` | Framework scraping anti-deteksi | Sudah terpasang (`~/.hermes/skills/botasaurus`). Relevan ke scraper IDX yang diblokir Cloudflare. |
| `algentis.xyz` | Kompetitor (dashboard trading) | `kompetitor/algentis-2026-10-04.md` + `aksi-teardown-algentis.md` |
| `github/rayss868/fastmcp-browser` | Browser MCP | `tiga-kiriman-mcp-browser-sinyal-idx-2026-10-04.md` + `audit-uiux-2026-10-04.md` (terpasang, headless jalan) |
| `github/septianbyk/idx-financial-scraper` | Fundamental IDX | Ditangani 5 Okt: scraper **diblokir Cloudflare** (403); rute lebih baik = `financial_statements` Arjum (sudah dipakai, `22ad7a0`) |
| `github/pbakaus/impeccable` | Alat desain | **Terpasang**; dipakai sesi ini (0 pelanggaran) |
| `youtu.be/eIbL_pQeLnY` | Video memecoin "3 strategi" | Dinilai 5 Okt: channel 1.460 subs + link afiliasi → sampingkan |
| `github/imikerussell/beebots` | Design system | **Diterapkan penuh** (commit `3281bec`, `7584640`, `58358aa`) |
| `threads/@meteoraidn`, `threads/BAfCiWHXwd`, `BAORhFMqXX`, `instagram/DeGQQ1ymg7f` | Sinyal/klaim LP | Bagian dari analisa LP 4 Okt |

## 2. Temuan BARU

### 2a. `stock.arjum.com/api-docs#mcp` — MCP server resmi Arjum ⭐

**Ini yang paling berguna dari tumpukan ini**, dan belum pernah masuk dokumen mana pun
(0 kemunculan di riwayat sesi).

| Fakta (diverifikasi langsung) | Nilai |
|---|---|
| URL | `https://stock.arjum.com/mcp` |
| Transport | **Streamable HTTP** (bukan stdio) |
| Autentikasi | header `X-API-Key` |
| Tool | **15, read-only** |
| Handshake tanpa auth | **HTTP 200** (server hidup); tool butuh key |
| Harness yang disebut | Claude Code, Cursor, Codex, **Hermes Agent**, opencode |

**15 tool** (nama → endpoint REST, peta 1:1): `screener_saham_terkini` `/api/screener/latest` ·
`analisa_saham` `/api/analysis/{code}` · `broker_summary` `/api/broker-summary/{code}` ·
`akumulasi_broker_historis` `/api/broker-accumulation/{code}` · `riwayat_harga` `/api/history/{code}` ·
`seasonality_bulanan` `/api/seasonal/{code}` · `market_cap` `/api/market-cap` · `cari_saham` `/api/search` ·
`status_server` · `done_details` `/api/done-details` · + `analisa_batch`, `harga_batch` (2 tool batch).

**BATAS YANG HARUS DIBACA SEBELUM DIPAKAI — dan ini yang menentukan:**

> *"Kuota dipotong dari API key yang sama seperti REST API."* — dokumentasi Arjum, verbatim.

Jadi MCP **bukan jalan bebas kuota**. 15 tool itu memetakan 1:1 ke 13 endpoint REST yang
sudah kita pakai. Memasang MCP **tidak** menghemat satu panggilan pun; ia hanya mengubah
bentuk pemanggilan (tool-call vs HTTP). Nilainya:

- **Positif:** Hermes Agent bisa memanggil data IDX sebagai tool langsung (tanpa kode HTTP),
  berguna untuk sesi orkestrasi ad-hoc.
- **Negatif:** menambah jalan ke kuota yang sama — **kebalikan** dari tujuan kita menghentikan
  pendarahan. `fields` di MCP hanya memfilter di sisi MCP (hemat token konteks), **bukan kuota**.

**Keputusan:** **JANGAN pasang dulu.** War Room sudah punya `collectors/idx.py` +
`bandarmologi.py` yang menutup tool yang sama. Memasang MCP sekarang = menambah permukaan
pemakaian kuota tanpa manfaat yang belum kita punya. Kalau nanti mau, pasang dengan key
**terpisah** dan pantau lewat `/metrics`.

### 2b. `t.me/awsnumsignal` — "AWSnum Signals" (357 member)

Sinyal memecoin dari **empat sumber**: Pumpfun · Jup · Robinhood · Stonkfun.
Deskripsinya jujur: *"Data mentah, bukan rekomendasi."*

- **Beririsan dengan area GMGN** War Room (memecoin multi-chain). Bukan hal baru secara
  arsitektur — `collectors/dexscreen.py` + `gmgn` sudah menangani ini.
- **Yang layak diserap:** konfirmasi bahwa **Robinhood chain** memang venue memecoin yang
  dipantau orang — konsisten dengan temuan F4 (`lp_chain="robinhood"` sudah dikonfigurasi).
- **Tidak bisa diverifikasi:** channel Telegram tidak mengekspos isi pesan lewat preview
  (0 pesan terbaca tanpa login). Jadi tidak ada angka yang bisa diuji — **jangan dipakai
  sebagai sumber sinyal** sampai ada track record yang bisa diperiksa.

### 2c. `threads/@ihsgscreener` — screener emiten liquid

Postingan: *"Emiten Liquid apa yang menarik untuk Besok? Btw ini baru 1 Fitur"*.

- Ini **screener IDX** — sudah dicakup War Room (`collectors/idx_tv.py` + `idx.py`
  `/api/screener/latest`). Tidak ada yang perlu dibangun.
- Tidak ada angka/metodologi yang bisa diuji di postingannya → **sampingkan**.

### 2d. `threads/@stravonlab` — klaim long BTC

Isinya opini/sentimen ("temen Minvon udah diajakin cicil long BTC sejak listing Futures
Binance"), **tanpa angka, tanpa bukti yang bisa diperiksa**. Kelas yang sama dengan klaim
"+228R" yang sudah kita tolak: narasi tanpa dasar terukur → **sampingkan**.

## 3. Ringkasan keputusan

| Tautan | Putusan |
|---|---|
| Arjum MCP | **Tunda** — kuota sama, tidak menghemat; pasang hanya dengan key terpisah bila perlu |
| awsnumsignal | Catat sebagai konteks pasar; **jangan** sumber sinyal (tak terverifikasi) |
| ihsgscreener | Sudah dicakup; sampingkan |
| stravonlab | Tanpa bukti; sampingkan |
| 22 tautan lain | Sudah ada dokumennya — tidak diuji ulang |

**Satu pelajaran yang berulang dan sudah tiga kali muncul:** tautan yang dikirim biasanya
berisi **satu** hal berguna yang dikubur dalam framing berlebihan. Di tumpukan ini, yang
berguna bukan klaimnya — melainkan **fakta bahwa MCP Arjum berbagi kuota yang sama**, dan
itu justru alasan untuk **tidak** memakainya.
