# War Room

**Satu layar untuk melihat dan mengoperasikan seluruh sistem trading**: crypto, IDX, forex,
Polymarket, meme coin, dan Sistem & AI. Tujuannya sederhana — saat kamu membuka Home, kamu
tahu dalam beberapa detik pasar mana yang punya sinyal, seberapa layak, dan apa risikonya,
tanpa berpindah alat.

Pembeda yang dipegang sistem ini:

- **Satu kartu sinyal terbaik per pasar di Home.** Bukan dinding widget, bukan grid grafik.
- **Kejujuran angka.** Sistem menandai mana angka **terukur** dan mana yang **belum
  terverifikasi**, dan tidak menampilkan `0` ketika artinya "tidak ada data" (kosong = `—`).

Detail produk: `PRODUCT.md`.

## Cara buka demo

**https://0xgunsl1ng3r.xyz** — buka di peramban, lalu masuk di `/masuk`.

Halaman utama bisa dilihat sebagian tanpa login; area yang butuh data (dan semua `/api/*`)
memerlukan sesi. Kredensial **tidak pernah** dibagikan di repo ini.

## Pakai dalam 4 langkah

1. **Buka** https://0xgunsl1ng3r.xyz dan **masuk** di `/masuk`.
2. **Mulai dari Home** — lihat mana pasar yang punya sinyal paling layak saat ini.
3. **Telusuri satu pasar** (crypto / IDX / forex / Polymarket / GMGN / Sistem) untuk melihat
   **kenapa**: angka, status kesegaran data, dan `catatan_kejujuran` di tiap angka.
4. **Tindak lanjuti** ke paper trade untuk menyiapkan keputusan sebelum uang nyata; live hanya
   dengan izin eksplisit owner.

> Angka di layar datang dari snapshot yang dihitung worker; halaman **menampilkan** kebenaran
> yang sudah dihitung, bukan menghitung sendiri di UI.

## Aturan yang tidak boleh dilanggar

Lihat `AGENTS.md`. Ringkasnya: `/opt/polymarket` baca-saja, Tencent baca-saja
(Azure sudah dilepas 6 Okt — radar rantai kini lokal di host ini),
gate live tidak pernah disentuh, kredensial tidak pernah masuk repo/log/percakapan,
angka tidak boleh dikarang, dan ambang gate & rumus BE hanya boleh diubah manusia (owner).

## Untuk pengembang

Panduan teknis (stack, struktur folder, perintah harian, environment, deploy nginx/systemd)
ada di **[`docs/pengembangan.md`](docs/pengembangan.md)**. Aturan kerja & keselamatan ada di
`AGENTS.md`. Dilarang push langsung ke `main` — semua perubahan lewat branch → PR
(lihat `.github/pull_request_template.md`).

### Dokumentasi Paket & Layanan

- [`packages/core`](packages/core/README.md) — Model DB, evaluasi gate statistik, data splits, retensi
- [`packages/live-trading`](packages/live-trading/README.md) — Mesin analisis multi-pasar, CLI `lt`, kalkulator risiko & dompet
- [`services/api`](services/api/README.md) — FastAPI :8800 REST & stream SSE, auth cookie & RBAC
- [`services/worker`](services/worker/README.md) — Job runner latar belakang & penerbit fakta
- [`services/notifier`](services/notifier/README.md) — Notifikasi Telegram Hermes & webhook retry
- [`services/llm`](services/llm/README.md) — Gateway LLM ber-grounding fakta dengan circuit breaker
- [`apps/web`](apps/web/README.md) — Antarmuka SvelteKit 2, desain Serene Capital

Catatan perubahan seluruh sektor terdokumentasi di [**`CHANGELOG.md`**](CHANGELOG.md).
