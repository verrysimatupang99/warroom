# Strategi per market — murni formula, tanpa AI

Keputusan pemilik 3 Nov 2026: seluruh worker LLM (orchestrator + sub-agent,
job `llm-brief-*`, `prompts-sync`, endpoint `/api/v1/ai/*` kecuali status)
DIBUANG. Sinyal dihitung dari rumus + data. Laya AI nonaktif (bisa dihidupkan
di /sistem → Pengaturan, owner saja).

| Market | Sumber data | Rumus | Kode |
|---|---|---|---|
| Crypto | OKX publik (fallback MEXC berlabel) | harga OKX + fakta `okx.account`; jurnal/bench di `live_trading` | `routers/lokal.py`, `ops/live-trading`, `worker/jobs/signal-sync` |
| IDX | idx-edge stock.arjum.com (+ IHSG Yahoo publik, cache) | cache TTL; tanpa AI | `routers/idx.py`, `apps/web/src/routes/idx` |
| Forex | MT5 (telemetri EA, via tencent) | EMA+RSI di EA; verdict lama diganti rumus | `routers/tencent.py`, `apps/web/src/routes/forex` |
| Polymarket | — | under construction, fakta klaim-uang dijaga | `StandbyPasar` di `/polymarket` |
| GMGN/meme | — | under construction | `StandbyPasar` di `/gmgn` |
| LP Agent | — | pihak ketiga, jalur uang terkunci | `/lp` → 308 |

Lavensi/liveness: job `denyut` (tiap 6 jam) mengirim ringkasan ke Telegram
sebagai bukti worker hidup. Alert palsu tidak dibuat: tidak ada data →
tulis `unavailable` + alasan, bukan angka karangan.

## Live feed sinyal dari Telegram (AKTIF, 3 Nov 2026)

Sumber: 24 channel terverifikasi milik akun pemilik (daftar:
`ops/tg_channels.json`). Jembatan `ops/telegram_bridge.py` jalan di webdock
tiap 15 menit (cron), sesi Telethon read-only di `/etc/warroom/tg-feed/`.

Kondisi jujur saat audit: sebagian besar channel berisi promo/airdrop/spam
atau sudah sepi; 2 channel forex juga sepi sejak Okt. Parser REGEX KETAT
(butuh ARAH + SIMBOL + entry/SL, tanpa AI) — uji perdana 40 pesan terbaru:
0 cocok, 0 dikirim. Tidak ada sinyal karangan.

Alur: pesan cocok → `POST /api/v1/sinyal/telegram` (user layanan
`feed-telegram`, peran operator) → fakta `signal` status `kandidat`, source
`telegram-feed:feed-telegram`. Yang BELUM ada: consumer `kandidat`→proposal;
jangan eksekusi langsung dari feed.

Catatan keamanan: API_ID/HASH + nomor telepon tertulis plaintext di script
lama testing — kredensial akun pemilik, JANGAN disebar; sesi di webdock
disimpan 600.

Contoh kirim manual bila perlu:

```bash
curl -s -X POST "$WARROOM_API/api/v1/sinyal/telegram" \
  -H "Cookie: $WARROOM_SESSION" \
  -H 'content-type: application/json' \
  -d '{"pasar":"crypto","simbol":"BTCUSDT","arah":"LONG",
       "entry":97000.5,"sl":96000,"tp1":99000,
       "catatan":"break-retest M5 @grup-XYZ"}'
```

2. Sinyal masuk sebagai fakta `signal` status `kandidat`, source
   `telegram-feed:feed-telegram` — SELALU berlabel feed, belum lolos gate
   statistik War Room.
3. Yang BELUM ada dan masih harus dibangun: consumer yang mengubah fakta
   `kandidat` menjadi proposal/eksekusi setelah lolos gate. Jangan
   eksekusi langsung dari feed.
