# UI tahap 2–3 + integritas data — 6 Okt 2026

Lanjutan redesign beebots (commit `3281bec`, `7584640`). Commit ini: **`58358aa`**.
Semua klaim di bawah dijalankan dan diverifikasi di host ini.

## Ringkas

| # | Item | Status | Bukti |
|---|---|---|---|
| 1 | Kelas mati (teks jatuh ke body 15px) | **selesai** | `--text-10/14/16/20` + `--color-canvas` ditambahkan; 0 sisa kelas tak terdefinisi |
| 2 | 12 baris data KARANGAN di UI | **selesai** | DecisionFeed & StrategyLeaderboard disambung ke ledger nyata |
| 3 | Label BSJP salah (bersumber disebut "proksi") | **selesai** | 3 mode dibedakan benar + legenda STRONG/ARA |
| 4 | 37 warna di luar palet | **selesai** | dipetakan ke token terukur |
| 5 | A11y: 4 warning + target sentuh <44px | **selesai** | svelte-check 0 warning; rail 44px |
| 6 | Bug: `live` tanpa impor di `/sistem` | **selesai** | tab Event & Audit tidak lagi error runtime |
| 7 | Home tanpa heading | **selesai** | H1 + H2 per section |

## 1. Kelas mati — akar masalahnya

Proyek memakai utilitas Tailwind `text-NN` yang dipetakan ke token `--text-NN`, tapi
tangganya **bolong**. Terukur sebelum perbaikan:

```
dipakai:   text-10 (117x)  text-14 (56x)  text-9 (12x)  text-16 (5x)  text-20 (3x)
didefinisi: --text-11/12/13/15/19/26/34      -> 9, 10, 14, 16, 20 TIDAK ADA
```

Kelas yang tidak menghasilkan CSS apa pun membuat teks **jatuh ke ukuran body (15px)** —
label mikro tampil sebesar paragraf, hierarki visual hilang di tempat yang paling padat.
`bg-canvas` (14x) juga tanpa token → latar transparan.

**Perbaikan:** tambah `--text-10/14/16/20` + `--color-canvas`; `text-9` (di bawah ambang
baca) dinormalkan ke `text-10`. Diverifikasi di CSS live: `.text-10{font-size:10px}` dst.

## 2. Data karangan — pelanggaran aturan inti produk

Aturan produk: *"UI tidak boleh mengarang angka."* Dua komponen melanggarnya:

**DecisionFeed** — punya `DEFAULT_DECISIONS`: 7 keputusan **karangan** (BTCUSDT veto,
UBI IL -9.01%, LINK +0.844R, dst) dan dirender `<DecisionFeed />` tanpa data, dengan
badge **"Live Feed"**. Jadi angka & narasi palsu tampil sebagai aktivitas nyata.

**StrategyLeaderboard** — punya `DEFAULT_STRATEGIES`: 5 strategi karangan
(winrate 80%, +3.844R) tampil sebagai "Papan Peringkat Strategi".

**Perbaikan:** default dihapus; komponen menyatakan kekosongan beserta alasannya.
- DecisionFeed kini menerima `items` dari **ledger nyata** (`snapshot.ledger.terakhir`):
  status → jenis, note → alasan. Saat ini 3 keputusan asli (SOL expired, LINK manual, SUI SL).
- Home membangun leaderboard dari fakta nyata: `equity` crypto (6 trade, WR 66,7%, +3,84R)
  + 4 arm Polymarket dari `poly_paper.arms`. PnL arm dilabeli **USD, bukan R**.

## 3. BSJP — label kebalikan dari kenyataan

`bsjpObj.mode` bisa `"terukur"` / `"bersumber"` / `"proksi"` (lihat `signals/bsjp.py:121`),
tapi UI membandingkan dengan `"jendela"` — yang tidak pernah ada. Akibatnya mode
`bersumber` (edge **sudah terukur** di sumber: STRONG +0,86%, ARA +1,06%) diberi label
**"PROKSI — BELUM TERUKUR"** — kebalikan dari kenyataan.

Diperbaiki: 3 mode dibedakan, badge + catatan jujur memakai kriteria yang sama, plus
legenda tier STRONG/ARA beserta peringatan bahwa **filter ARA di sumber tidak memeriksa
SMA10** (bercampur saham menguat & yang bangkit dari penurunan) — temuan dari sesi 5 Okt.

## 4. Warna di luar palet

37 kelas Tailwind mentah (`cyan/amber/rose/slate/purple`) dipetakan ke token yang sudah
diukur kontrasnya: `--accent`, `--accent-2`, `--warn`, `--neg`. Rank badge: 1=accent,
2=accent-2, 3=warn (menghindari makna "baik/buruk" palsu). RailNav: `border-l-2` (pola
paling khas UI hasil AI) dibuang.

## 5. A11y

| Temuan | Perbaikan |
|---|---|
| `nav[role=tablist]` (peran interaktif di elemen non-interaktif) | `tablist` dipindah ke `<div>` dalam |
| `<circle>` dengan handler tanpa peran | `role="presentation"` |
| RailNav target 36/38px (11/14 elemen <44px) | 44px |
| EventFeed `state_referenced_locally` | salinan prop dibaca sekali |

Sisa 1 warning EventFeed = **pola lama yang sudah ada di HEAD** (props dibaca sekali saat
mount adalah perilaku yang disengaja), bukan regresi.

## 6. Bug runtime ditemukan sambil mengerjakan

`routes/sistem/+page.svelte` memakai `live.kejadian` / `live.berdasarkanTopik` **tanpa
impor** → tab **Event** dan **Audit** akan error begitu dibuka. Impor ditambahkan.

## 7. Heading

Home tidak punya satu pun heading. Kini: H1 (logo WarRoom) + H2 per section (sr-only,
karena `<section>`/`<nav>` sudah punya `aria-label`). Urutan terverifikasi: `H1,H2,H3,H3…`.

## Verifikasi (dijalankan)

```
impeccable detect --json apps/web/src          -> [] (0 pelanggaran)
svelte-check                                    -> 0 error, 0 warning baru
npm run test                                    -> 44 lulus
uv run pytest                                   -> 658 lulus
bash ops/deploy-web.sh                          -> web ok (aset build baru tersaji)
```

Diverifikasi di browser **sebagai owner** (sesi dibuat lewat `issue_session`, sandi tidak
pernah dipakai):
- 6 pasar berganti benar; rail urut skor; `?pasar=` bisa di-bookmark
- Kinerja → 5 strategi dari data nyata (bukan karangan)
- DecisionFeed → 3 keputusan dari ledger nyata, badge "3 tercatat" (bukan "Live Feed")
- `fs text-10 = 10px`, `text-14 = 14px` (dulu 15px)
- 390px: **tanpa overflow**; rail pindah ke atas; bottom-nav muncul
- `interaktifTanpaNama: 0`

## Kuota Arjum (track C)

Lihat `tencent-akses-dan-bsjp-2026-10-05.md`. Ringkas temuan baru:
- `idx_scalp_watch.py` = **satu-satunya** pengirim ticker ber-sufiks `.JK` yang jatuh ke
  fallback Arjum → 1.447 dari 1.474 panggilan (99%).
- Tuas read-only paling efektif: **hitung job ENABLED**, bukan status pause. Sisa 6 job
  enabled menyentuh IDX (paling rajin "Coordinator Live Monitor", tiap 15 menit).
- Perbaikan yang benar = normalisasi di boundary ticker (buang `.JK` sekali) + kunci API
  terpisah per host; **kode Tencent tidak disentuh**.
