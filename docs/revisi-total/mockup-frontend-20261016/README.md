# Mockup Stitch - Revisi Total Frontend (2026-10-16)

14 layar mockup (mobile 390px) via Google Stitch, proyek dipakai ulang:
**"War Room Modern Financial Terminal"** (projectId `14655604709134052956`).
Arah gayanya di [DESIGN-USULAN.md](DESIGN-USULAN.md).

## Cara melihat

- **Referensi penuh:** buka `unduhan/<id>.html` di browser (lebar ~390px).
- **Sekilas:** `unduhan/<id>.png` = strip full-page skala tinggi-512px, sekadar pindai cepat.

## Indeks 14 halaman (route lama sebagai patokan)

| Route | Id | Judul layar Stitch | Screen id |
|---|---|---|---|
| `/` | home | War Room Mobile Home - 5-Second Answer | `510404a1cf4b4c41afd6d618809c2555` |
| `/crypto` | crypto | War Room Mobile - Crypto Detail | `250d8558a38d4a08a14dce7edbf3b223` |
| `/polymarket` | polymarket | War Room Mobile - Polymarket Watch | `82dc0afada8f41549b6bc8bf02c9a5d5` |
| `/gmgn` | gmgn | War Room Mobile - Meme Coin Scan (GMGN) | `9b70ed1a6a8e4680aa0a5a35fd6b8058` |
| `/idx` | idx | War Room Mobile - IDX BSJP Detail | `1dd4da058e3e483cb9d83c097b0c5fe4` |
| `/forex` | forex | War Room Mobile - Forex & Agenda Makro | `07606c01fd3d40649d81f88683e4d608` |
| `/berita` | berita | War Room Mobile - Berita & Intel | `2ba2b7c50fd24893a422f4a67d04b899` |
| `/sistem` | sistem | War Room Mobile - Sistem & AI (Operations Health) | `6a09851d11ac430a9aa46b717c5b2792` |
| `/leaderboard` | leaderboard | War Room Mobile - Leaderboard Strategi | `1ce1536f4b0a4d05b8edf1439529ecbd` |
| `/riset` | riset | War Room Mobile - Riset | `3586fbf2ab3b460497437db001611047` |
| `/catatan` | catatan | War Room Mobile - Catatan Jurnal Keputusan | `895b5e0f1bbc4953a1cf4e3e28cb79cd` |
| `/masuk` | masuk | War Room Mobile - Masuk (Login) | `34aaff39ce3f4afbabbd227c096c3357` |
| `/cara-kerja` | cara-kerja | War Room Mobile - Panduan Cara Kerja | `37ff38d94aab4f26a62f2f5e17fc1846` |
| `/bantuan` | bantuan | War Room Mobile - Bantuan | `d3ca3210b212444c85bfb04153c4f5cb` |

## Hasil audit (audit_html.py)

- **14/14 OK**: konten wajib ada; tag kejujuran (`TERUKUR` / `BELUM TERVERIFIKASI`) ada;
  bahasa Indonesia; nol emoji dekoratif, gradient, glow, pill, font default trio,
  statistik karangan. Pembenahan satu kaus: marker `[✓]` di gmgn diganti `[OK]`/`[!]`
  via `edit_screens` (screen id baru).
- Angka hanya dari PRODUCT.md: +0,86% / +1,06% (edge BSJP, walk-forward), 10,0/11,9 bps
  (fee+slippage BTC/FET), 14,8% vs 62,6% (win-rate layak-dagang vs campuran menyesatkan),
  arsip tick 24,9 jt baris, kuota Arjum 99%. Selebihnya `-` + alasan.

## Skrip

- `generate.py` - generate ulang 14 layar (paralel 3 jalur, >3 mnt/layar).
- `download_screens.py` - unduh PNG+HTML dari screens/*.json (gmgn: unduh manual id baru).
- `audit_html.py` - audit inspeksi-kode HTML.
- Catatan Stitch: `edit_screens` MEMBUAT screen id baru (id lama tidak berubah).
