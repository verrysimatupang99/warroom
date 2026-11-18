# War Room — Cetak Biru dari Nol (v1)

Dokumen ini **menggantikan** `v0-warroom.md`, `prd-warroom-202611.md`, dan
`erd-warroom-202611.md`. Acuan tunggal. Sistem lama tetap jalan sampai gelombang
pertama terbukti — tapi desainnya tidak mewarisi satu keputusan pun dari yang lama.

---

## 1. Produk

**War Room adalah satu tempat untuk menjalankan strategi di lima market, dengan jejak
yang bisa diaudit.**

Satu lingkaran, tujuh langkah, berlaku untuk semua market:

| # | Langkah | Entitas | Halaman |
|---|---|---|---|
| 1 | **Feed** data masuk | `feed`, `feed_check`, `candle`, `quote` | `/sistem` |
| 2 | **Signal** strategi memutuskan | `signal` | `/sinyal` |
| 3 | **Decision** gate risiko | `risk_rule`, `signal.gate_json` | `/risiko` |
| 4 | **Order** perintah | `order` | `/posisi` |
| 5 | **Position** dikelola | `position` | `/posisi` |
| 6 | **Ledger** uang tercatat | `ledger_entry`, `account_snapshot` | `/ledger` |
| 7 | **Review** jurnal → verdict | `journal`, `verdict`, `proposal` | `/jurnal`, `/riset` |

Tidak ada halaman ke-8. Kalau sebuah fitur tidak melayani salah satu langkah ini,
fitur itu tidak dibangun.

---

## 2. Lima market, semuanya kelas satu

Bukan "forex dulu, sisanya nanti". Kelimanya dirancang sekarang; pembangunan bergelombang,
tapi tiap market selesai utuh (semua halaman) sebelum pindah ke market berikutnya.

### Definisi "sempurna" per market

| Market | Yang wajib benar | Bukti diterima |
|---|---|---|
| **FOREX** | dua akun (live + demo) terpisah, status EA terbaca, alasan tolak sinyal terlihat, posisi dengan SL/TP dan R berjalan, ledger memuat swap & commission | Buka `/forex` dari HP: equity live vs demo, PnL hari ini, posisi, alasan "DI_LUAR_SESI" — tanpa SSH |
| **CRYPTO** | paper vs live berdampingan, TP1/TP2 + BE, fee & funding di ledger, scan sinyal 20+ koin dengan alasan approve/reject | `/crypto` menjawab "hari ini engine ambil apa dan kenapa" dalam satu layar |
| **POLYMARKET** | event → outcome, harga 0–1, exposure per event, payout saat settlement masuk ledger | `/polymarket` menunjukkan exposure + potensi payout + tanggal settlement, dan PnL-nya cocok dengan ledger |
| **IDX** | jam bursa, IHSG, per emiten, T+2 di ledger, freshness ≤ 15 menit | `/idx` menampilkan watchlist + perubahan harian; angka tidak pernah "segar" saat bursa tutup |
| **ONCHAIN** | token baru, likuiditas, holder, tanda risiko (LP lock/burn), swap fill tanpa SL/TP | `/onchain` memberi label risiko di setiap baris dan tidak punya tombol beli |

Aturan lintas market: **satu bentuk halaman, satu bentuk angka.** Yang berbeda hanya
semantik (settlement vs SL/TP vs swap) — bukan tata letaknya.

---

## 3. Model domain: inti + ekstensi

Prinsip: **satu bentuk untuk semua market.** Perbedaan disimpan di tabel ekstensi,
bukan di tabel terpisah per market.

### Inti (dipakai kelima market)

```
venue(id, code, kind[broker|exchange|prediction|equity|chain], name, timezone, active)
account(id, venue_id, label, login_ext, currency, mode[live|demo|paper],
        kind[broker|exchange|wallet|prediction], status, vault_credential_id)
instrument(id, venue_id, market[forex|crypto|equity|prediction|onchain],
           symbol, kind[spot|perp|stock|binary|token], quote_ccy, tick_size,
           contract_size, digits, active)
strategy(id, code, name, market, version, repo_ref, status)
strategy_run(id, strategy_id, account_id, instrument_id, magic, params_json,
             host, unit, started_at, status, last_heartbeat_at)
signal(id, strategy_run_id, instrument_id, ts, side, decision[approved|rejected|expired],
       reason_code, gate_json, entry, sl, tp1, tp2, rr, confidence)
order(id, account_id, instrument_id, strategy_run_id, ext_id, type, side, qty,
      price, sl, tp, status, placed_at)
fill(id, order_id, ext_id, ts, price, qty, fee, swap, position_id)
position(id, account_id, instrument_id, strategy_run_id, side, qty_open, qty_closed,
         entry_price, exit_price, sl, tp1, tp2, be_active, opened_at, closed_at,
         realized_pnl, fee_total, r_multiple, close_reason)
ledger_entry(id, account_id, ts, kind[trade|fee|swap|funding|settlement|deposit|
             withdrawal|adjustment], amount, currency, ref_table, ref_id, balance_after)
account_snapshot(account_id, ts, balance, equity, margin, free_margin, floating_pnl)
candle(instrument_id, tf, ts, o,h,l,c,v, source_id)
quote(instrument_id, ts, bid, ask, last, spread, source_id)
feed(id, code, provider, market, owner_host, sla_seconds, status, last_ok_at, last_error)
feed_check(id, feed_id, ts, latency_ms, ok, detail)
event(id, ts, actor, action, target_table, target_id, before_json, after_json)
user(id, email, name, role, active) / role(id, code, permissions_json)
vault_credential(id, label, provider, kind, cipher_blob, rotated_at)
journal(id, ts, market, instrument_id, position_id, tag, note, evidence_uri)
```

### Ekstensi per market (tipis, hanya yang memang beda)

```
prediction_event(id, venue_id, slug, title, category, close_at, resolve_at, resolution)
prediction_outcome(instrument_id PK, event_id, outcome[yes|no|multi], payout_ratio)
equity_profile(instrument_id PK, sector, board, market_cap, eps, pe, div_yield)
token_profile(instrument_id PK, chain, contract, liquidity_usd, holders,
              lp_locked, lp_burned, rug_flags_json)
```

### Pemetaan konsep antar market (biar tidak ada interpretasi ganda)

| Konsep | FOREX | CRYPTO | PREDICTION | EQUITY | ONCHAIN |
|---|---|---|---|---|---|
| harga masuk | entry price | entry | harga 0–1 | harga saham | harga swap |
| keluar paksa | SL/TP | SL/TP/BE | settlement | SL/TP | tidak ada |
| biaya | commission + swap | fee + funding | fee platform | fee broker + pajak | gas + slippage |
| hasil akhir | PnL akun | PnL akun | payout | PnL akun | PnL wallet |
| satuan | lot | qty koin | share outcome | lembar | token |

---

## 4. Peta halaman lengkap

### Lintas market
| Route | Isi | Kenapa |
|---|---|---|
| `/` | 5 kartu market + status sistem | satu layar "hari ini bagaimana" |
| `/sinyal` | semua keputusan, semua market, dengan alasan | menjawab "kenapa kosong" |
| `/posisi` | semua posisi terbuka lintas market | exposure nyata, bukan per aplikasi |
| `/ledger` | mutasi uang semua akun | satu sumber angka |
| `/jurnal` | catatan + tag + tautan posisi | bahan review |
| `/risiko` | batas global & per market | satu tempat mengubah batas |
| `/akun` | koneksi: broker, exchange, wallet, prediksi | tahu apa yang tersambung |
| `/sistem` | feed + service + job + disk | pengganti SSH |
| `/jejak` | audit: siapa mengubah apa | syarat uang nyata |
| `/riset` | hypothesis → run → verdict → proposal | ide diuji sebelum live |
| `/pengaturan` | user, peran, retensi, token | kontrol |
| `/masuk`, `/vault` | auth & kredensial | tidak ada plaintext |

### Per market (bentuk identik, isi menyesuaikan)
`/forex`, `/crypto`, `/polymarket`, `/idx`, `/onchain` — masing-masing:
`ringkasan · posisi · sinyal · jurnal · riset · pengaturan`
(contoh: `/forex/posisi`, `/crypto/sinyal`, `/polymarket/riset`)

### Publik (tanpa login, tanpa data akun)
`/publik/leaderboard`, `/publik/kurs`, `/publik/status`

**Aturan navigasi:** setiap halaman market punya dua tautan tetap — **`/sinyal`** (kalau
tidak ada trade) dan **`/sistem`** (kalau data berhenti). Ini bukan opsional.

---

## 5. Sumber data & pemiliknya

| Feed | Market | Pemilik host | SLA | Fallback |
|---|---|---|---|---|
| MT5 live + demo (status JSON) | forex | webdock | 10 s | baca file langsung |
| OKX (tick + saldo) | crypto | **cyber1** | 15 s | cache Postgres |
| Binance (referensi harga) | crypto | **cyber1** | 30 s | pakai OKX |
| GMGN / RPC chain | onchain | **cyber1** | 60 s | tandai stale |
| Polymarket Gamma | prediction | **cyber1** | 5 mnt | cache |
| IDX / Yahoo | equity | **cyber1** | 15 mnt | cache |
| Telegram (Telethon) | notifikasi | webdock (perlu sesi) | realtime | notifier |
| R2 | artefak | Cloudflare | — | disk 7 hari |

Aturan: **tidak ada collector di webdock** kecuali yang butuh sesi lokal. Webdock menerima
ringkasan, bukan tick mentah.

---

## 6. Operasi

- **Dua proses** di webdock: `web` (UI + API) dan `engine` (jadwal, ingest ringkas, sinyal).
  Plus eksekusi: `mt5-live`, `mt5-demo`, `bridge`.
- Semua job punya heartbeat; mati → merah di `/sistem` + alert Telegram.
- Backup Postgres harian ke R2; restore diuji tiap kuartal (RPO 24 j, RTO 2 j).
- Disk & RAM dipantau; webdock target CPU < 40%.
- Data plane di cyber1 punya watchdog sendiri; kalau cyber1 mati, webdock tetap menyajikan
  data terakhir dengan label **stale** — tidak boleh menampilkan angka lama seolah segar.

## 7. Keamanan & audit

- Session HttpOnly; token EA rotatable; kredensial hanya di `vault_credential`.
- Semua aksi tulis → `event` dengan before/after. Tidak ada pengecualian.
- Halaman publik tidak pernah memuat login, saldo, posisi, jurnal.
- Arm → Confirm untuk semua aksi yang menyentuh uang atau parameter.
- Perubahan parameter hanya lewat `proposal` + `verdict` (go), tidak boleh edit langsung.

---

## 8. Urutan pembangunan (semua market, tanpa menunda)

Tiap gelombang selesai **utuh**: skema + ingest + semua halaman market itu + uji.

| Gelombang | Isi | Selesai kalau |
|---|---|---|
| **W1 — Fondasi** | skema inti + `ledger_entry` + `feed` + `event` + `/`, `/sistem`, `/ledger`, `/jejak` | angka uang bisa ditelusuri ke deal asal; `/sistem` jujur soal freshness |
| **W2 — FOREX utuh** | `/forex/*` lengkap + MT5 live/demo + `bridge` | syarat tabel FOREX di §2 terpenuhi |
| **W3 — CRYPTO + ONCHAIN** | `/crypto/*`, `/onchain/*`, feed OKX/Binance/GMGN | syarat CRYPTO & ONCHAIN terpenuhi |
| **W4 — PREDICTION + EQUITY** | `/polymarket/*`, `/idx/*`, feed Gamma & IDX | syarat POLYMARKET & IDX terpenuhi |
| **W5 — Riset & publik** | `/riset`, `verdict`, `proposal`, `/publik/*`, multi-user | 100% perubahan parameter punya jejak |

Tidak ada gelombang yang boleh dilewati, dan **tidak ada market yang "menumpang"** di
gelombang lain.

## 9. Definisi selesai (berlaku semua gelombang)

1. Bisa dijawab dari HP tanpa SSH.
2. Angka yang tampil bisa ditelusuri ke baris asal (deal/tick/ledger).
3. Data basi kelihatan basi.
4. Setiap aksi punya jejak.
5. Tidak ada kredensial di kode, log, atau tabel domain.
6. Kalau sebuah service mati, halaman tetap terbuka dan memberi tahu apa yang mati.

## 10. Yang gue butuh dari lu (3 hal, bukan 10)

1. **Akses data:** konfirmasi bahwa feed OKX, Gamma (Polymarket), IDX, dan GMGN boleh
   diambil dari cyber1 (butuh kredensial/rate-limit info kalau ada).
2. **Akun live:** pindah ke investor password sampai W2 lulus, atau tetap master?
   (Ini menentukan apakah W2 boleh menyentuh uang nyata.)
3. **Batas risiko default** per market: angka awal yang lu nyaman (mis. forex 0,5%/trade,
   crypto 0,5%, prediction maks 2% per event) — gue pakai sebagai seed `risk_rule`.
