# Verifikasi website produksi — 31 Okt 2026

Target: `https://0xgunsl1ng3r.xyz` (nginx → web :3100 + API :8800), sesi e2e nyata.
Spec: `apps/web/e2e/cek_verifikasi-website.spec.ts` → **3 passed**.

## Rute yang diperiksa

`/`, `/forex`, `/forex?sub=sinyal`, `/jurnal?market=forex`,
`/jurnal?market=crypto`, `/crypto?sub=sinyal`, `/sistem?sub=kebijakan`, `/idx`,
`/gmgn`, `/polymarket`.

Untuk setiap rute:
- HTTP < 400; tidak ada `GAGAL MEMUAT`/`Application error`;
- tidak ada overflow horizontal (desktop 1440 dan mobile 390);
- panel kunci tampil: Status mesin Reaper + Riwayat evaluasi EA (forex), Kinerja
  ekuitas + Drawdown maks + kurva (jurnal), Jurnal sinyal + Bootstrap (crypto),
  Gate + Parameter aktif (sistem), status standby (Polymarket).

## API yang diperiksa

| Endpoint | Hasil |
|---|---|
| `GET /api/v1/journal/signals` | 200; `ringkas.n_terkirim=450`; `montecarlo.n_simulasi=10000`; `per_versi` ada |
| `GET /api/v1/journal/scanlog?market=forex` | 200; `market=forex`; daftar evaluasi |
| `GET /api/v1/journal/scanlog?market=crypto` | 200; `market=crypto` |
| `GET /api/v1/journal/performance?market=forex` | 200; `n_titik=377`; `markers` + `drawdown_max_pct` |
| `GET /api/v1/params` | 200 (ber-auth) |

## 503 yang diharapkan (bukan kegagalan)

- `journal/edge` — `fills.csv` masih kosong.
- `journal/performance?market=crypto` — crypto belum punya deret waktu.
- `idx/ledger` + `idx/signals` — sumber node scanner lama sudah tidak ada; UI
  menampilkan empty state, bukan halaman error.

Spec memisahkan 503 ini dari kegagalan tak terduga; 4xx/5xx lain akan menggagalkan tes.

## Error & request

- `pageerror`: 0.
- `console.error`: 0 (setelah 503 state kosong yang memang ditangani UI dikeluarkan).
- `requestfailed`: 0 (SSE `/api/v1/stream` yang ditutup saat navigasi diabaikan).

## Screenshot

`artifacts/verifikasi-web-20261031/` (di-ignore git, bukti lokal):
- `1440-_forex_sub_sinyal.png`
- `1440-_crypto_sub_sinyal.png`
- `1440-_jurnal_market_forex.png`
- `390-crypto-sinyal.png`

Screenshot mobile menunggu panel jurnal terisi (bukan skeleton).
