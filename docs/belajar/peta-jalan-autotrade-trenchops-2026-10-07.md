# Peta jalan dari teardown Algentis → War Room (7 Okt 2026)

Pemilik melampirkan halaman produk **Algentis** (kompetitor yang sedang kami teardown).
Dua blok yang mereka tawarkan sebagai *Coming soon*:

- **Auto-Trade** — eksekusi tanpa tangan di akun bursa milik pengguna sendiri: API key
  trade-only, setelan risiko milik pengguna, laporan PnL, dan chat langsung dengan agen AI
  di Telegram. Ada *waitlist*; anggota sinyal aktif dapat prioritas.
- **TrenchOps** — toolkit on-chain: sniper buy pada pair Solana & EVM yang baru lahir
  dengan *safety gate* ketat, pelacakan smart wallet, panggilan token trending, dan
  peringatan smart-money Arkham.

Dokumen ini memetakan: **apa yang sudah kita punya**, **apa yang belum**, dan **apa yang
berbahaya** — supaya tidak ada yang menjanjikan hal yang belum ada.

## Auto-Trade

| Bagian Algentis | Status War Room | Bukti / letak |
|---|---|---|
| Eksekusi paper dengan jalur keputusan sama seperti live | **Ada** | `packages/live-trading` (`PaperBroker`), ledger R, halaman Eksekusi |
| Gate risiko (batas rugi harian, maks posisi, kuota) | **Ada** | `RiskGate`, fakta `risiko`, `RiskMeter` di UI |
| Statistik & pakem bukti (tidak mengklaim sebelum matang) | **Ada** | `pasar_akurasi`, pakem INSUFFICIENT→TUNING |
| Arming 3-way untuk uang nyata | **Ada kode, belum menyala** | `services/api/src/warroom_api/live.py` (`arming_status`) |
| API key trade-only di akun pengguna | **Belum** | butuh desain kustodi kunci — belum ada |
| Agen AI chat di Telegram | **Sebagian** | notifier Telegram ada; *chat dua arah dengan agen* belum |
| Waitlist & langganan | **Belum** | belum ada halaman/CRM |

**Batas yang harus disebut bila Autotrade ditawarkan:** kunci API pengguna adalah permukaan
serang paling berbahaya di seluruh sistem. Sebelum itu ada, wajiib: kunci hanya-izin-trade
(tanpa penarikan), penyimpanan terenkripsi (bukan di repo/log), batas posisi ganda
(per-akun + per-pasar), kill switch, dan audit trail tiap perintah. Arming saja sekarang pun
belum dinyalakan — jadi jangan pernah menulis "otomatis trading di bursa Anda".

## TrenchOps

| Bagian Algentis | Status War Room | Bukti / letak |
|---|---|---|
| Sniper buy + **safety gate** ketat | **Sebagian** | Safety gate ADA (bundler ≤0,25 · dev hold ≤0,05 · entrapment ≤0,95 · liq ≥$100k · mcap ≥$500k · skor ≥60). "Sniper" (order otomatis) belum ada — sekarang **paper**. |
| Smart-wallet tracking | **Ada (jurnal)** | fakta `gmgn.signals` (shadow 31 sinyal smartmoney) |
| Trending token calls | **Ada** | radar multi-chain + Pumpfun listings (DexScreener) |
| Peringatan smart-money (Arkham) | **Belum** | kita belum pakai Arkham |
| Multi-chain (Solana + EVM) | **Ada** | chains: sol, bsc, base, eth, robinhood, arc, stable |

**Catatan penting:** safety gate kita **sudah** menutup celah yang Algentis jual sebagai fitur
(bundler/dev-hold/entrapment) — dan kita jalankan lewat `gmgn-cli` read-only. Yang belum:
sniper otomatis (order sungguhan) dan integrasi Arkham. Dua-duanya harus lewat jalur uang
nyata yang statusnya masih **paper**.

## Prinsip yang tidak berubah

1. **Paper dulu, live belakangan** — jalur keputusan sama, sakelar yang berbeda.
2. **Angka tidak dikarang** — kalau belum ada, tulis belum ada; kalau rusak, tulis rusak.
3. **Gate statistik** — tidak ada klaim profit sebelum pakem mengizinkan.
4. **Kunci tidak pernah masuk repo/log/percakapan.**
